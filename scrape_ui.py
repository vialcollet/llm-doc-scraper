import os
import streamlit as st
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify
from openai import OpenAI
from dotenv import load_dotenv
import pyperclip
from urllib.parse import urlparse
import sqlite3
from datetime import datetime
import re
import time
import asyncio
import tiktoken

# Load environment variables
load_dotenv()

# Create docs directory if it doesn't exist
if not os.path.exists('docs'):
    os.makedirs('docs')

def get_db_version():
    """Get the current database version."""
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS db_version
                    (version INTEGER PRIMARY KEY)''')
        c.execute('SELECT version FROM db_version')
        result = c.fetchone()
        if result is None:
            c.execute('INSERT INTO db_version VALUES (0)')
            conn.commit()
            return 0
        return result[0]
    finally:
        conn.close()

def update_db_version(version):
    """Update the database version."""
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        c.execute('UPDATE db_version SET version = ?', (version,))
        conn.commit()
    finally:
        conn.close()

def migrate_db():
    """Run database migrations."""
    current_version = get_db_version()
    
    # List of migrations to run
    migrations = [
        # Version 1: Add settings table
        '''CREATE TABLE IF NOT EXISTS settings
           (key TEXT PRIMARY KEY,
            value TEXT)''',
            
        # Version 2: Add models table
        '''CREATE TABLE IF NOT EXISTS models
           (id TEXT PRIMARY KEY,
            last_updated TIMESTAMP)''',
            
        # Version 3: Update crawled_urls table
        '''CREATE TABLE IF NOT EXISTS crawled_urls_new
           (url TEXT PRIMARY KEY,
            title TEXT,
            filename TEXT,
            last_crawled TIMESTAMP);
           INSERT OR IGNORE INTO crawled_urls_new (url, title, last_crawled)
           SELECT url, title, last_crawled FROM crawled_urls;
           DROP TABLE IF EXISTS crawled_urls;
           ALTER TABLE crawled_urls_new RENAME TO crawled_urls;'''
    ]
    
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    
    try:
        # Run each migration that hasn't been applied yet
        for version, migration in enumerate(migrations, start=1):
            if current_version < version:
                try:
                    # Split migration into separate statements
                    statements = migration.split(';')
                    for statement in statements:
                        if statement.strip():
                            c.execute(statement)
                    conn.commit()
                    update_db_version(version)
                    st.success(f"Applied migration {version}")
                except Exception as e:
                    st.error(f"Failed to apply migration {version}: {e}")
                    conn.rollback()
                    break
    finally:
        conn.close()

def init_db():
    """Initialize or migrate the database."""
    migrate_db()

def save_setting(key, value):
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        c.execute(
            'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )
        conn.commit()
    finally:
        conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        c.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = c.fetchone()
        return result[0] if result else default
    finally:
        conn.close()

async def get_available_models():
    """Get available models from OpenAI API."""
    try:
        client = OpenAI()
        models = await client.models.list()
        # Filter for GPT models
        gpt_models = [model.id for model in models if 'gpt' in model.id.lower()]
        return sorted(gpt_models)
    except Exception as e:
        print(f"Failed to fetch models: {e}")
        return ["gpt-4", "gpt-4-turbo-preview", "gpt-3.5-turbo"]  # Fallback models

def save_url_to_db(url, title=None, filename=None):
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        c.execute(
            'INSERT OR REPLACE INTO crawled_urls (url, title, filename, last_crawled) VALUES (?, ?, ?, ?)',
            (url, title or url, filename, datetime.now())
        )
        conn.commit()
    finally:
        conn.close()

def get_crawled_urls():
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        c.execute('SELECT url, title, filename FROM crawled_urls ORDER BY last_crawled DESC')
        return c.fetchall()
    finally:
        conn.close()

def get_saved_filename(url):
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        c.execute('SELECT filename FROM crawled_urls WHERE url = ?', (url,))
        result = c.fetchone()
        return result[0] if result else None
    finally:
        conn.close()

def save_models_to_db(models):
    """Save available models to database."""
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        # First clear existing models
        c.execute('DELETE FROM models')
        # Then insert new ones
        for model in models:
            c.execute(
                'INSERT INTO models (id, last_updated) VALUES (?, ?)',
                (model, datetime.now())
            )
        conn.commit()
    finally:
        conn.close()

def get_models_from_db():
    """Get available models from database."""
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        c.execute('SELECT id FROM models ORDER BY id')
        return [row[0] for row in c.fetchall()]
    finally:
        conn.close()

# Default models to use when no models are available
DEFAULT_MODELS = ["gpt-4-turbo-preview", "gpt-4", "gpt-3.5-turbo"]

# Initialize the database
init_db()

def fetch_pages(base_url):
    """Fetch all pages from the base URL."""
    try:
        response = requests.get(base_url)
        response.raise_for_status()
    except requests.RequestException as e:
        st.error(f"Failed to fetch pages: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a', href=True)
    pages = []
    for link in links:
        href = link['href']
        full_url = requests.compat.urljoin(base_url, href)
        pages.append({"title": link.text.strip() or full_url, "url": full_url})
    return pages

def summarize_content(content):
    try:
        # Read the prompt from prompt.md
        with open('prompt.md', 'r') as f:
            system_prompt = f.read().strip()
        
        response = client.chat.completions.create(
            model=get_setting('model', "gpt-4-turbo-preview"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            max_tokens=6000,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Failed to summarize content: {e}")
        return content

def get_filename_from_title(title):
    """Generate a safe filename from the page title."""
    # Remove any special characters and spaces, keep only alphanumeric and dashes
    safe_title = re.sub(r'[^\w\s-]', '', title)
    # Replace spaces with dashes
    safe_title = re.sub(r'\s+', '-', safe_title).strip('-')
    # Convert to lowercase
    safe_title = safe_title.lower()
    # Ensure the filename is not too long (max 50 chars)
    safe_title = safe_title[:50]
    return f"{safe_title}.md"

def count_tokens(text, model="gpt-4"):
    """Count the number of tokens in a text string."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        print(f"Error counting tokens: {e}")
        # Fallback to approximate count (1 token ≈ 4 characters)
        return len(text) // 4

def format_duration(seconds):
    """Format duration in seconds to minutes and seconds."""
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"

def format_number(num):
    """Format number with thousand separators."""
    return f"{num:,}"

def scrape_and_summarize(selected_pages):
    """Scrape and summarize selected pages."""
    combined_markdown = []
    start_time = time.time()
    
    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for index, page in enumerate(selected_pages):
        # Update progress bar and status
        progress = (index + 1) / len(selected_pages)
        progress_bar.progress(progress)
        status_text.text(f"Processing page {index + 1} of {len(selected_pages)}: {page}")
        
        try:
            response = requests.get(page)
            response.raise_for_status()
        except requests.RequestException as e:
            st.warning(f"Failed to fetch {page}: {e}")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        markdown_content = markdownify(response.text).strip()
        summarized_content = summarize_content(markdown_content)
        
        # Only remove the outer markdown wrapper if it exists
        cleaned_content = summarized_content
        if cleaned_content.startswith('```markdown\n'):
            cleaned_content = cleaned_content[len('```markdown\n'):]
        if cleaned_content.endswith('\n```'):
            cleaned_content = cleaned_content[:-4]
        
        combined_markdown.append(cleaned_content.strip())

    # Clear the progress bar and status text when done
    progress_bar.empty()
    status_text.empty()
    
    final_content = '\n\n---\n\n'.join(combined_markdown)  # Add separator between documents
    
    # Calculate metrics
    duration = time.time() - start_time
    formatted_duration = format_duration(duration)
    token_count = count_tokens(final_content, get_setting('model', "gpt-4-turbo-preview"))
    formatted_tokens = format_number(token_count)
    
    # Use the custom filename from session state
    filename = st.session_state["final_filename"]
    filepath = os.path.join('docs', filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        # Display formatted success message
        st.success(
            "Document saved:\n"
            f"- Path: {filepath}\n"
            f"- Duration: {formatted_duration}\n"
            f"- Tokens: {formatted_tokens}"
        )
    except Exception as e:
        st.error(f"Failed to save document: {e}")
    
    return final_content

# Streamlit UI
st.title("Documentation Scraper")

# Settings section in sidebar
with st.sidebar:
    st.header("Settings")
    
    # API Key input
    saved_api_key = get_setting('openai_api_key', os.getenv("API_KEY", ""))
    displayed_key = "••••" + saved_api_key[-4:] if saved_api_key else ""
    
    api_key = st.text_input(
        "OpenAI API Key",
        value=displayed_key,
        type="password",
        help="Enter your OpenAI API key"
    )
    
    if st.button("Save API Key"):
        if api_key and api_key != displayed_key:  # Only save if changed
            save_setting('openai_api_key', api_key)
            st.success("API Key saved successfully!")
    
    # Model selection
    st.subheader("Model Selection")
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        if st.button("Fetch Models"):
            try:
                with st.spinner("Fetching available models..."):
                    client = OpenAI(api_key=get_setting('openai_api_key', os.getenv("API_KEY")))
                    models = client.models.list()
                    # Filter for GPT models and store in session state and database
                    available_models = [
                        model.id for model in models 
                        if 'gpt' in model.id.lower()
                    ]
                    available_models.sort()
                    save_models_to_db(available_models)
                    st.session_state.available_models = available_models
                    st.success("Models fetched and saved successfully!")
            except Exception as e:
                st.error(f"Failed to fetch models: {str(e)}")
                # Try to load models from database
                db_models = get_models_from_db()
                if db_models:
                    st.session_state.available_models = db_models
                else:
                    # Fallback to default models
                    st.session_state.available_models = DEFAULT_MODELS
    
    with col1:
        # Try to get models in this order:
        # 1. Session state (from fetch)
        # 2. Database
        # 3. Default models
        if 'available_models' not in st.session_state:
            db_models = get_models_from_db()
            st.session_state.available_models = db_models if db_models else DEFAULT_MODELS
        
        # Get the saved model preference
        default_model = get_setting('model', "gpt-4-turbo-preview")
        
        # Find the index of the default model, or 0 if not found
        default_index = (st.session_state.available_models.index(default_model) 
                        if default_model in st.session_state.available_models else 0)
        
        model = st.selectbox(
            "Select Model",
            options=st.session_state.available_models,
            index=default_index,
            help="Select the OpenAI model to use for summarization"
        )
        
        if model != default_model:
            save_setting('model', model)

# Initialize OpenAI client with the saved API key
client = OpenAI(api_key=get_setting('openai_api_key', os.getenv("API_KEY")))

# Get previously crawled URLs for the dropdown
previous_urls = get_crawled_urls()
url_options = [""] + [url[0] for url in previous_urls]

# Create two columns for the URL input
col1, col2 = st.columns([2, 1])

with col1:
    base_url = st.text_input("Enter URL:")

with col2:
    selected_previous_url = st.selectbox(
        "Or select previous URL:",
        options=url_options,
        format_func=lambda x: x if x else "Select previous URL"
    )

# Update base_url if a previous URL is selected
if selected_previous_url:
    base_url = selected_previous_url

if st.button("Fetch Pages"):
    if not base_url:
        st.error("Please enter a URL.")
    else:
        pages = fetch_pages(base_url)
        if pages:
            # Get initial filename from the first page title
            initial_filename = get_filename_from_title(pages[0]["title"])
            # Check if we have a saved filename
            saved_filename = get_saved_filename(base_url)
            # Use saved filename if it exists, otherwise use the generated one
            st.session_state["proposed_filename"] = saved_filename or initial_filename
            st.session_state["pages"] = pages
            st.success(f"Fetched {len(pages)} pages.")

if "pages" in st.session_state:
    st.subheader("Select Pages to Include")
    
    # Add filename input after fetching pages
    filename_no_ext = st.text_input(
        "Document filename (without extension):",
        value=st.session_state.get("proposed_filename", "").replace(".md", "")
    )
    st.session_state["final_filename"] = f"{filename_no_ext}.md"
    
    selected_pages = st.multiselect(
        "Choose pages:",
        options=[page['url'] for page in st.session_state["pages"]],
        default=[page['url'] for page in st.session_state["pages"]],
        format_func=lambda url: next((p['title'] for p in st.session_state["pages"] if p['url'] == url), url)
    )

    if st.button("Scrape and Generate Document"):
        if not selected_pages:
            st.error("Please select at least one page.")
        else:
            # Save the filename to the database
            save_url_to_db(
                base_url,
                next((p['title'] for p in st.session_state["pages"] if p['url'] == base_url), base_url),
                st.session_state["final_filename"]
            )
            st.session_state.result = scrape_and_summarize(selected_pages)
            st.session_state.show_output = True

    # Show the output section if we have results
    if "show_output" in st.session_state and st.session_state.show_output:
        st.subheader("Generated Document")
        result_container = st.text_area("Markdown Output", value=st.session_state.result, height=300)
        
        if st.button("Copy to clipboard", key="copy_markdown"):
            pyperclip.copy(st.session_state.result)
            st.success('Text copied successfully! ✅')

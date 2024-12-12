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

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("API_KEY"))

# Create docs directory if it doesn't exist
if not os.path.exists('docs'):
    os.makedirs('docs')

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS crawled_urls
        (url TEXT PRIMARY KEY, 
         title TEXT,
         last_crawled TIMESTAMP)
    ''')
    conn.commit()
    conn.close()

def save_url_to_db(url, title=None):
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        c.execute(
            'INSERT OR REPLACE INTO crawled_urls (url, title, last_crawled) VALUES (?, ?, ?)',
            (url, title or url, datetime.now())
        )
        conn.commit()
    finally:
        conn.close()

def get_crawled_urls():
    conn = sqlite3.connect('scraper.db')
    c = conn.cursor()
    try:
        c.execute('SELECT url, title FROM crawled_urls ORDER BY last_crawled DESC')
        return c.fetchall()
    finally:
        conn.close()

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
                model="gpt-4o-mini",
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

def scrape_and_summarize(selected_pages):
    """Scrape and summarize selected pages."""
    combined_markdown = []
    
    # Get the page name for the first selected page from the session state
    page_name = None
    if "pages" in st.session_state:
        # Find the matching page info from the stored pages
        for page in st.session_state["pages"]:
            if page["url"] == selected_pages[0]:  # Match the first selected page
                page_name = page["title"]
                break
    
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
    
    # Save the content to a file in the docs directory
    filename = get_filename_from_title(page_name or "untitled")
    filepath = os.path.join('docs', filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_content)
        st.success(f"Document saved to {filepath}")
    except Exception as e:
        st.error(f"Failed to save document: {e}")
    
    return final_content

# Streamlit UI
st.title("Documentation Scraper")

# Get previously crawled URLs for the dropdown
previous_urls = get_crawled_urls()
url_options = [""] + [url[0] for url in previous_urls]
url_titles = {url[0]: url[1] for url in previous_urls}

# Create two columns for the URL input
col1, col2 = st.columns([2, 1])

with col1:
    base_url = st.text_input("Enter URL:")

with col2:
    selected_previous_url = st.selectbox(
        "Or select previous URL:",
        options=url_options,
        format_func=lambda x: url_titles.get(x, x) if x else "Select previous URL"
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
            # Save the URL to database
            save_url_to_db(base_url, pages[0]["title"] if pages else None)
            st.session_state["pages"] = pages
            st.success(f"Fetched {len(pages)} pages.")

if "pages" in st.session_state:
    st.subheader("Select Pages to Include")
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
            st.session_state.result = scrape_and_summarize(selected_pages)
            st.session_state.show_output = True

    # Show the output section if we have results
    if "show_output" in st.session_state and st.session_state.show_output:
        st.subheader("Generated Document")
        result_container = st.text_area("Markdown Output", value=st.session_state.result, height=300)
        
        if st.button("Copy to clipboard", key="copy_markdown"):
            pyperclip.copy(st.session_state.result)
            st.success('Text copied successfully! ✅')

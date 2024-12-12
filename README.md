# LLM Doc Scraper

A powerful documentation scraper that uses LLM (Large Language Models) to intelligently process and summarize web documentation. Built with Streamlit for an easy-to-use interface, it allows you to scrape documentation from websites and get AI-enhanced summaries.

## Features

- 🌐 Web scraping with intelligent link detection
- 🤖 LLM-powered content summarization
- 📝 Markdown output format
- 💾 SQLite-based URL history
- 📁 Automatic file organization
- 🎯 Smart page title detection
- 🖥️ User-friendly Streamlit interface

## Prerequisites

- Python 3.8+
- [just](https://github.com/casey/just) command runner
- OpenAI API key

## Setup

1. Clone the repository:
   ```bash
   git clone git@github.com:vialcollet/llm-doc-scraper.git
   cd llm-doc-scraper
   ```

2. Create a `.env` file with your OpenAI API key:
   ```bash
   echo "API_KEY=your-openai-api-key" > .env
   ```

3. Run the complete setup using just:
   ```bash
   just setup
   ```

   This will:
   - Create a virtual environment
   - Install required packages
   - Start the Streamlit application

## Usage

1. Start the application:
   ```bash
   just run
   ```

2. Enter a documentation URL in the interface
3. Select the pages you want to scrape
4. Click "Scrape and Generate Document"
5. Find your processed documentation in the `docs` directory

## Available Commands

- `just run` - Start the Streamlit application
- `just install` - Install required packages
- `just setup` - Complete setup (venv, install, run)
- `just init-db` - Initialize/reset the database schema
- `just clean-db` - Remove the URL history database
- `just reset` - Reset everything (database, docs, venv)

## Output

The scraped documentation is:
- Saved in Markdown format
- Organized by page title
- Stored in the `docs` directory
- Cleaned of navigation elements and non-documentation content
- Enhanced with AI-powered summarization

## Contributing

Feel free to open issues or submit pull requests if you have suggestions for improvements.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

This means you can freely use, modify, and distribute this software, but any modifications must also be released under the GPL-3.0 license. For more information, visit [GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.en.html). 
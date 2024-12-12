# List available commands
default:
    @just --list

# Create and activate virtual environment
venv:
    python -m venv venv
    @echo "Virtual environment created. Activate it with 'source venv/bin/activate' (Unix) or 'venv\\Scripts\\activate' (Windows)"

# Install required packages (run after activating venv)
install:
    pip install -r requirements.txt

# Run the Streamlit application
run:
    streamlit run scrape_ui.py

# Verify all required files exist
verify:
    @echo "Checking required files..."
    @test -f prompt.md || (echo "prompt.md is missing" && exit 1)
    @test -f requirements.txt || (echo "requirements.txt is missing" && exit 1)
    @echo "All required files present"

# Complete setup: create venv, install packages, and run
setup: verify venv install run

# Initialize or reset the database schema
init-db:
    @echo "Initializing database schema..."
    @python -c "from scrape_ui import init_db; init_db()"

# Clean the database (removes all stored URLs)
clean-db:
    @echo "Cleaning the database..."
    @rm -f scraper.db

# Reset everything (database, docs directory, and venv)
reset: clean-db
    @echo "Removing docs directory..."
    @rm -rf docs
    @echo "Removing virtual environment..."
    @rm -rf venv
    @echo "Reset complete. Run 'just setup' to start fresh."

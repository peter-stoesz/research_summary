# AI Podcast Agent

A command-line tool for automatically generating AI news briefings by scraping RSS feeds and creating narration-ready scripts.

## Features

- 📰 Scrapes AI-related news from curated RSS sources
- 🔍 De-duplicates and clusters related articles
- 📊 Ranks stories based on recency, relevance, and preferences
- 📝 Generates structured show notes in Markdown
- 🎙️ Creates narration-ready scripts for TTS processing

## Installation

1. Ensure you have Python 3.11+ and PostgreSQL installed

2. Install the package:
```bash
pip install -e .
```

3. Initialize the configuration and database:
```bash
aipod init
```

4. Set required environment variables:
```bash
export AIPOD_DB_PASSWORD=your_postgres_password
export OPENAI_API_KEY=your_openai_api_key
```

## Usage

### Basic Commands

```bash
# Initialize configuration and database
aipod init

# Run pipeline to generate show notes and script
aipod run --minutes 12

# Open latest run output in Finder
aipod open latest

# Manage sources
aipod sources list
aipod sources add --name "New Source" --url "https://example.com/feed"
aipod sources test
```

### Run Options

- `--date YYYY-MM-DD`: Specify run date (default: today)
- `--minutes N`: Target script length in minutes (default: 12)
- `--max-items N`: Maximum RSS items to process (default: 150)
- `--max-stories N`: Maximum stories in output (default: 20)

## Configuration

Configuration files are stored in `~/.config/aipod/`:
- `config.yaml`: Main configuration
- `sources.yaml`: RSS feed sources

Output workspace is at `~/AI-Podcast/`

## Database Setup

The tool requires PostgreSQL. Create a database and user:

```sql
CREATE DATABASE aipod;
CREATE USER aipod_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE aipod TO aipod_user;
```

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black aipod
ruff check aipod
```
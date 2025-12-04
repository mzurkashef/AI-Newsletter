# AI Newsletter System

An automated content aggregation and delivery system that collects AI-related articles from multiple newsletter sources and YouTube channels, processes them for quality, and delivers curated daily updates via Telegram.

<img width="2752" height="1536" alt="AINL" src="https://github.com/user-attachments/assets/721461f2-1e51-4000-88ea-afefbeb08d9c" />


## Overview

The AI Newsletter System is a fully automated pipeline that:
1. **Collects** articles from 3 AI newsletters and 2 YouTube channels
2. **Filters** for genuine content (removes blocked pages and errors)
3. **Deduplicates** identical articles
4. **Summarizes** YouTube video transcripts to 1-2 lines
5. **Delivers** formatted newsletters daily via Telegram
6. **Schedules** automatically using Windows Task Scheduler

### Key Features

- **Automated Content Collection**: Fetches from RSS feeds and YouTube channels
- **Smart Filtering**: Removes blocked pages, error messages, and duplicates
- **YouTube Integration**: Extracts and summarizes video transcripts automatically
- **Telegram Delivery**: Direct message delivery with proper formatting
- **Windows Scheduling**: Fully integrated with Windows Task Scheduler for daily execution
- **Comprehensive Logging**: Detailed logs for monitoring and troubleshooting

## Requirements

- **Python**: 3.9 or higher
- **Operating System**: Windows, macOS, or Linux
- **Internet Connection**: Required for content collection and delivery

### Python Version Check

To verify your Python version:

```bash
python --version
# or
python3 --version
```

You should see Python 3.9.x or higher. If not, please install Python 3.9+ from [python.org](https://www.python.org/downloads/).

## Setup Instructions

### 1. Clone Repository

```bash
git clone <repository-url>
cd ai-newsletter
```

### 2. Create Virtual Environment

Create and activate a Python virtual environment:

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

Install all required packages:

```bash
pip install -r requirements.txt
```

This will install:
- Core dependencies: requests, beautifulsoup4, yt-dlp, python-telegram-bot, python-dotenv, tenacity, fuzzywuzzy, PyYAML
- Development dependencies: pytest, black, pylint

**Note**: `sqlite3` is a built-in Python module and does not need to be installed separately.

### 4. Configure Environment Variables

Copy the example environment file and configure it:

```bash
# Copy .env.example to .env
cp .env.example .env
```

Edit `.env` and fill in your configuration:

- **TELEGRAM_BOT_TOKEN**: Get your bot token from [@BotFather](https://t.me/BotFather) on Telegram
- **TELEGRAM_CHAT_ID**: Your Telegram channel or chat ID where newsletters will be delivered
- **AI_SERVICE_TYPE**: Choose `ollama` (self-hosted), `huggingface` (free tier), `groq` (free tier), or `local`
- **AI_API_KEY**: Only needed for Hugging Face or Groq (optional for Ollama/local)
- **AI_MODEL_PATH**: Model name or path depending on your AI service choice

### 5. Create Configuration Files

Create the following YAML configuration files:

**`config/sources.yaml`** - Define your content sources:

```yaml
newsletters:
  - name: "Superhuman AI"
    url: "https://superhuman.ai/newsletter"
  - name: "The Rundown AI"
    url: "https://www.therundown.ai"
  - name: "DeepLearning.AI The Batch"
    url: "https://www.deeplearning.ai/the-batch"

youtube_channels:
  - name: "Lev Selector"
    channel_id: "UC..."
  - name: "IndyDevDan"
    channel_id: "UC..."
```

**`config/settings.yaml`** - Application settings:

```yaml
schedule:
  delivery_day: 0  # 0=Monday, 6=Sunday
  delivery_time: "09:00"

content:
  window_days: 7  # Collect content from past 7 days
  min_items_per_category: 1

ai:
  filter_threshold: 0.7  # Relevance threshold for filtering
  max_categories: 4
```

## Quick Start

### Manual Execution (One-Time Run)

```bash
# 1. Navigate to project directory
cd C:\Users\Kashef\root.bmad\ai-newsletter

# 2. Activate virtual environment
.\venv\Scripts\activate

# 3. Run the newsletter pipeline
python -m src.main --log-level INFO

# Result: Telegram message delivered within 10 seconds
```

### Automatic Daily Scheduling

```bash
# 1. Open Command Prompt as Administrator
# 2. Navigate to project directory
cd C:\Users\Kashef\root.bmad\ai-newsletter

# 3. Run the scheduling setup script
scripts\setup-task-scheduler.bat daily

# Result: Newsletter runs automatically every day at 9:00 AM
```

## Command-Line Options

```bash
python -m src.main [OPTIONS]

Options:
  --config-dir PATH        Directory containing configuration files (default: config)
  --db-path PATH           Path to SQLite database (default: data/newsletter.db)
  --log-level LEVEL        Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
  --output-format FORMAT   Newsletter format: html, markdown (default: html)
```

### Examples

```bash
# Run with verbose logging
python -m src.main --log-level DEBUG

# Run with custom database path
python -m src.main --db-path "backups/newsletter.db"

# Run with markdown output
python -m src.main --output-format markdown
```

## Project Structure

```
ai-newsletter/
├── src/
│   ├── collectors/      # Newsletter and YouTube content collection
│   ├── processors/      # AI filtering, categorization, formatting
│   ├── delivery/        # Telegram delivery and message assembly
│   ├── database/        # SQLite schema and storage operations
│   ├── config/          # Configuration management
│   └── utils/           # Logging, error handling, date utilities
├── config/              # YAML configuration files
├── data/                # SQLite database (gitignored)
├── logs/                # Log files (gitignored)
├── tests/               # Test files
├── .env.example         # Example environment variables
├── .gitignore           # Git ignore rules
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Zero-Cost Architecture

This project is designed to operate at **ZERO cost**:

- **AI Processing**: Self-hosted models (Ollama) or free-tier APIs (Hugging Face, Groq)
- **Hosting**: GitHub Actions free tier, local execution, or self-hosted infrastructure
- **Storage**: SQLite (file-based, no server needed)
- **Messaging**: Telegram Bot API (free)
- **YouTube**: Free transcript extraction libraries (yt-dlp)

## Development

### Adding New Features

1. Create feature branch: `git checkout -b feature/your-feature-name`
2. Make changes following the project structure and coding standards
3. Write tests for new functionality
4. Run tests: `pytest`
5. Format code: `black src/ tests/`
6. Submit pull request

### Testing Standards

- Use `pytest` for all tests
- Test structure mirrors source structure
- Write unit tests for business logic
- Include integration tests for component interactions
- Cover edge cases and error handling

## Troubleshooting

### Common Issues

**Python version error:**
- Ensure Python 3.9+ is installed and in your PATH
- Use `python --version` to verify

**Import errors:**
- Activate virtual environment: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
- Reinstall dependencies: `pip install -r requirements.txt`

**Telegram bot not working:**
- Verify `TELEGRAM_BOT_TOKEN` in `.env` is correct
- Check `TELEGRAM_CHAT_ID` is valid
- Ensure bot has permission to send messages to the channel/chat

**Database errors:**
- Ensure `data/` directory exists and is writable
- Check file permissions on `data/newsletter.db`

## Documentation

For detailed information and guides, see:

### Quick References
- **[QUICK_REFERENCE.txt](QUICK_REFERENCE.txt)** - Quick command reference and troubleshooting guide
- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Complete setup guide with step-by-step instructions
- **[PRD.md](PRD.md)** - Full product requirements and specifications

### Key Documentation Files
- **Configuration**: See `config/sources.yaml` and `config/settings.yaml`
- **Logs**: Check `logs/newsletter.log` and `logs/task-scheduler.log`
- **Architecture**: Project structure documented in README.md

## Troubleshooting

### Common Issues

**No articles collected (0 articles)**
```bash
# Run with debug logging to diagnose
python -m src.main --log-level DEBUG

# Check configuration
type config\sources.yaml
type .env
```

**Telegram message not received**
```bash
# Verify credentials
findstr "TELEGRAM" .env

# Check logs for errors
findstr /I "ERROR" logs\newsletter.log
```

**Task Scheduler task failed**
```bash
# Open Task Scheduler
taskschd.msc

# Check task history and logs
type logs\task-scheduler.log
```

For more troubleshooting help, see [GETTING_STARTED.md Troubleshooting Section](GETTING_STARTED.md#troubleshooting).

## Pipeline Phases

The newsletter system processes content through 5 phases:

1. **Content Collection** (10-30s)
   - Fetches from newsletter sources
   - Extracts YouTube videos and transcripts
   - Returns 15-20 articles

2. **Duplicate Filtering** (<1s)
   - Removes identical articles
   - Filters blocked/error pages
   - Returns ~15 unique articles

3. **AI Processing** (<1s)
   - Future: AI-powered filtering and categorization
   - Current: Placeholder for expansion

4. **Newsletter Generation** (<1s)
   - Formats articles and videos
   - Applies markdown styling
   - Prepares message for delivery

5. **Telegram Delivery** (<5s)
   - Sends message to Telegram API
   - Logs delivery status
   - Returns message ID or error

**Total Time**: ~30-40 seconds per run

## Configuration Sources

**Newsletters** (Pre-configured):
- Superhuman AI (https://superhuman.ai/newsletter)
- The Rundown AI (https://www.therundown.ai)
- DeepLearning.AI The Batch (https://www.deeplearning.ai/the-batch)

**YouTube Channels** (Pre-configured):
- Lev Selector
- IndyDevDan

Edit `config/sources.yaml` to add or remove sources.

## Technology Stack

- **Language**: Python 3.8+
- **Web Scraping**: feedparser, BeautifulSoup4
- **YouTube**: yt-dlp, youtube-transcript-api
- **Messaging**: requests (Direct Telegram API)
- **Database**: SQLite3
- **Configuration**: PyYAML
- **Logging**: Python logging module
- **Scheduling**: Windows Task Scheduler

## License

This project is open source. See LICENSE file for details.

## Support & Contributing

For issues, questions, or suggestions:
1. Check [GETTING_STARTED.md](GETTING_STARTED.md) for detailed guides
2. Review logs in `logs/newsletter.log` for error messages
3. Check [QUICK_REFERENCE.txt](QUICK_REFERENCE.txt) for common commands

## Project Status

✅ **Production Ready**

Current version includes:
- ✅ Multi-source content collection
- ✅ Smart error and blocked page filtering
- ✅ YouTube transcript extraction and summarization
- ✅ Deduplication of identical articles
- ✅ Telegram message delivery
- ✅ Windows Task Scheduler integration
- ✅ Comprehensive logging and error handling

**Version**: 1.0
**Last Updated**: 2025-11-24







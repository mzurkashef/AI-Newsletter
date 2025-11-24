# AI Newsletter System - Getting Started Guide

## Table of Contents
1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [Scheduling with Task Scheduler](#scheduling-with-task-scheduler)
7. [Troubleshooting](#troubleshooting)
8. [Log Monitoring](#log-monitoring)

---

## Quick Start

### Fastest Path to First Newsletter (5 minutes)

```bash
# 1. Open Command Prompt in the project directory
cd C:\Users\Kashef\root.bmad\ai-newsletter

# 2. Activate virtual environment
.\venv\Scripts\activate

# 3. Run the newsletter pipeline
python -m src.main --log-level INFO

# 4. Check your Telegram for the newsletter message
```

✅ You should receive a message on Telegram within 10 seconds.

---

## Prerequisites

### Required Software
- **Windows 10 or later**
- **Python 3.8 or higher**
  - Download from: https://www.python.org/downloads/
  - ✅ Add Python to PATH during installation
- **Telegram Account and Bot**
  - Create bot: Talk to [@BotFather](https://t.me/botfather) on Telegram
  - Note your Bot Token (format: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
  - Create/find a Telegram chat and get its Chat ID

### Accounts & API Keys Required

**Telegram Bot Token**
1. Open Telegram and search for @BotFather
2. Send `/newbot` command
3. Follow instructions to create a new bot
4. Copy the token (e.g., `7238568429:AAFyFW1y5YHvpCKA_qo9VwoPrMJLQXuTv70`)

**Telegram Chat ID**
1. Create a Telegram chat/channel or use existing one
2. Get the Chat ID:
   - Option A: Forward a message to @userinfobot and note the Chat ID
   - Option B: Send a message to your bot, then visit:
     ```
     https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
     ```
   - Look for `"chat":{"id":<YOUR_CHAT_ID>}` in the JSON response

---

## Installation

### Step 1: Extract/Download the Project

```bash
# Navigate to project directory
cd C:\Users\Kashef\root.bmad\ai-newsletter
```

### Step 2: Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows Command Prompt:
.\venv\Scripts\activate

# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
```

You should see `(venv)` prefix in your terminal when activated.

### Step 3: Install Dependencies

```bash
# Install required Python packages
pip install -r requirements.txt
```

**Dependencies installed**:
- feedparser - RSS feed parsing
- requests - HTTP requests
- beautifulsoup4 - HTML scraping
- yt-dlp - YouTube video fetching
- youtube-transcript-api - Video transcript extraction
- PyYAML - Configuration file parsing
- python-telegram-bot - Telegram integration
- python-dotenv - Environment variable loading

### Step 4: Verify Installation

```bash
# Check if all packages are installed
pip list

# You should see versions for: feedparser, requests, beautifulsoup4, yt-dlp, etc.
```

---

## Configuration

### Step 1: Set Up Environment Variables (`.env`)

The `.env` file stores your sensitive credentials.

**Location**: `C:\Users\Kashef\root.bmad\ai-newsletter\.env`

**Template**:
```env
# Telegram Configuration (REQUIRED)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# AI Configuration (Optional for Phase 3)
AI_SERVICE_TYPE=ollama
AI_MODEL_PATH=llama2

# Application Paths
DATABASE_PATH=data/newsletter.db
LOG_DIR=logs

# Scheduling
DELIVERY_DAY=0
CONTENT_WINDOW_DAYS=7
```

**How to fill it**:
1. Replace `your_bot_token_here` with your Telegram bot token
2. Replace `your_chat_id_here` with your Telegram chat ID
3. Keep other values as default (or customize as needed)

**Example filled `.env`**:
```env
TELEGRAM_BOT_TOKEN=7238568429:AAFyFW1y5YHvpCKA_qo9VwoPrMJLQXuTv70
TELEGRAM_CHAT_ID=8383179289
AI_SERVICE_TYPE=ollama
AI_MODEL_PATH=llama2
DATABASE_PATH=data/newsletter.db
LOG_DIR=logs
DELIVERY_DAY=0
CONTENT_WINDOW_DAYS=7
```

### Step 2: Configure Content Sources (`config/sources.yaml`)

**Location**: `C:\Users\Kashef\root.bmad\ai-newsletter\config\sources.yaml`

**Current Configuration** (Pre-configured):
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
    channel_id: "UCA4GfsgbI09cLzonTKryC6g"
  - name: "IndyDevDan"
    channel_id: "UC_x36zCEGilGpB1m-V4gmjg"
```

**To Add a New Newsletter Source**:
```yaml
newsletters:
  - name: "Your Source Name"
    url: "https://example.com/newsletter"
```

**To Add a New YouTube Channel**:
```yaml
youtube_channels:
  - name: "Your Channel Name"
    channel_id: "UCxxxxxxxxx"  # 24-character channel ID
```

**How to find YouTube Channel ID**:
1. Visit the channel page
2. Click "About" tab
3. Copy the channel ID shown in the URL or about section
4. Alternative: Use https://www.channelid.com/

### Step 3: Configure Settings (`config/settings.yaml`)

**Location**: `C:\Users\Kashef\root.bmad\ai-newsletter\config\settings.yaml`

**Default Configuration**:
```yaml
schedule:
  delivery_day: 0          # 0=Monday, 1=Tuesday, ..., 6=Sunday
  delivery_time: "09:00"   # 24-hour format (HH:MM)

content:
  window_days: 7           # Days to look back for content
  min_items_per_category: 1  # Minimum articles per category

ai:
  filter_threshold: 0.7    # Relevance threshold (0.0-1.0)
  max_categories: 4        # Maximum topic categories
```

**Common Customizations**:
- Change delivery time: Set `delivery_time: "14:30"` for 2:30 PM
- Change delivery day: Set `delivery_day: 5` for Saturday
- Adjust content window: Set `window_days: 30` for last 30 days

---

## Running the Application

### Option 1: Manual Execution (One-Time Run)

```bash
# Activate virtual environment (if not already active)
.\venv\Scripts\activate

# Run with INFO logging (recommended for first time)
python -m src.main --log-level INFO

# Alternative: Run with DEBUG logging (verbose output)
python -m src.main --log-level DEBUG

# Alternative: Run with WARNING logging (errors only)
python -m src.main --log-level WARNING
```

**Expected Output**:
```
================================================================================
AI Newsletter Pipeline Starting
Timestamp: 2025-11-24T03:18:09.237517
================================================================================
PHASE 1: Content Collection - Starting
  - Collected 15 articles from configured sources
PHASE 1: Content Collection - Complete
PHASE 2: Duplicate Filtering - Starting
  - After deduplication: 15 unique articles
PHASE 2: Duplicate Filtering - Complete
PHASE 3: AI Processing and Categorization - Starting
  - Processing 15 articles for importance
PHASE 3: AI Processing and Categorization - Complete
PHASE 4: Newsletter Generation - Starting
  - Generated newsletter message (1923 chars)
PHASE 4: Newsletter Generation - Complete
PHASE 5: Newsletter Delivery - Starting
  - Message sent successfully (Message ID: 19)
PHASE 5: Newsletter Delivery - Complete
================================================================================
Status: SUCCESS
All pipeline phases completed successfully
================================================================================
```

### Option 2: Run with Custom Configuration

```bash
# Run with custom database path
python -m src.main --db-path "data/custom.db" --log-level INFO

# Run with custom config directory
python -m src.main --config-dir "custom_config" --log-level INFO

# Run with custom output format
python -m src.main --output-format markdown --log-level INFO
```

### Option 3: Run in Background (Non-Blocking)

```bash
# Run in background using start command
start "" python -m src.main --log-level INFO

# Check logs later (see "Log Monitoring" section)
type logs\newsletter.log
```

---

## Scheduling with Task Scheduler

### Automatic Daily Scheduling (Recommended)

**Step 1: Open Command Prompt as Administrator**

1. Press `Win + R`
2. Type `cmd` and press `Ctrl + Shift + Enter` (for Admin)
3. Click "Yes" to allow administrator access

**Step 2: Navigate to Project Directory**

```bash
cd C:\Users\Kashef\root.bmad\ai-newsletter
```

**Step 3: Run the Setup Script**

```bash
# For daily execution at 9:00 AM
scripts\setup-task-scheduler.bat daily

# Alternative: For weekly execution (Mondays at 9:00 AM)
scripts\setup-task-scheduler.bat monday

# Alternative: For every 12 hours
scripts\setup-task-scheduler.bat 12hourly
```

**Expected Output**:
```
=== AI Newsletter Task Scheduler Setup ===
Project directory: C:\Users\Kashef\root.bmad\ai-newsletter
Python executable: C:\Python311\python.exe
Schedule: daily
Schedule: Every day at 9:00 AM

Checking for existing task...
No existing task found

Creating new scheduled task...

=== Setup Complete ===
Task created successfully!
```

### Verify Task Was Created

**Method 1: Using Command Prompt**
```bash
# List the task
schtasks /query /tn "AI Newsletter" /v

# You should see:
# TaskName:  \AI Newsletter
# Status:    Ready
# Schedule:  Every day at 9:00 AM
```

**Method 2: Using Windows Task Scheduler GUI**
1. Press `Win + R`
2. Type `taskschd.msc` and press Enter
3. Expand "Task Scheduler Library"
4. Look for "AI Newsletter" task
5. Right-click → Properties to view/modify schedule

### Modify Task Schedule

**Change execution time to 2:00 PM**:
```bash
# Delete old task
schtasks /delete /tn "AI Newsletter" /f

# Run setup script again with new time
# (Currently uses hardcoded 9:00 AM, edit script to change)
scripts\setup-task-scheduler.bat daily
```

**Manual modification via GUI**:
1. Open Task Scheduler
2. Find "AI Newsletter" task
3. Right-click → Properties
4. Go to "Triggers" tab
5. Click the trigger and select "Edit"
6. Change time under "Start at"

### Remove Task

```bash
# Delete the scheduled task
schtasks /delete /tn "AI Newsletter" /f
```

---

## Troubleshooting

### Issue 1: "Module not found" or Import Errors

**Error**:
```
ModuleNotFoundError: No module named 'feedparser'
```

**Solution**:
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Verify installation
pip list | find "feedparser"
```

### Issue 2: Telegram Bot Token Rejected

**Error**:
```
API Error: Unauthorized
```

**Solution**:
1. Verify token in `.env` file is correct
2. Copy token directly from @BotFather without spaces
3. Ensure token is not expired or revoked
4. Recreate bot via @BotFather if needed

### Issue 3: Newsletter Not Received

**Diagnose**:
```bash
# Run with DEBUG logging
python -m src.main --log-level DEBUG

# Look for these log lines:
# - "Message sent successfully (Message ID: XX)"
# - "API Error:" or "HTTP Error:"
```

**Common Causes**:
- Bot token incorrect → Fix in `.env`
- Chat ID incorrect → Verify in Telegram
- Telegram API temporarily down → Wait and retry
- Firewall blocking Telegram → Check firewall settings

### Issue 4: No Articles Collected

**Error**:
```
Collected 0 articles from configured sources
```

**Solution**:
```bash
# Run with DEBUG logging to see what failed
python -m src.main --log-level DEBUG

# Check if URLs in config/sources.yaml are correct
# Verify internet connection
# Try accessing URLs in browser to confirm they work
```

### Issue 5: Task Scheduler Task Failed

**Check logs**:
```bash
# Open Windows Task Scheduler
taskschd.msc

# Find "AI Newsletter" task
# Right-click → View History
# Look for errors in "Last Run Result"

# Check log file
type logs\task-scheduler.log
```

**Common Causes**:
- Python not in PATH → Add Python to system PATH
- Virtual environment not activated → Script handles this automatically
- Insufficient permissions → Run Command Prompt as Administrator

### Issue 6: Event Loop Error on Windows

**Error**:
```
RuntimeError: Event loop is closed
```

**Solution**:
This is already fixed in the current version. If you see this:
1. Ensure you're using the latest code
2. Verify `src/main.py` uses direct HTTP requests to Telegram API
3. No async/await calls should be made

---

## Log Monitoring

### Log Files Location

```
C:\Users\Kashef\root.bmad\ai-newsletter\logs\
├── newsletter.log          # Main application logs
└── task-scheduler.log      # Task Scheduler execution logs
```

### Viewing Logs

**Real-time logs (Command Prompt)**:
```bash
# View last 50 lines
type logs\newsletter.log | more

# Search for errors
findstr /I "ERROR" logs\newsletter.log

# Search for specific date
findstr "2025-11-24" logs\newsletter.log
```

**PowerShell (More Powerful)**:
```powershell
# Real-time tail (follow new entries)
Get-Content logs\newsletter.log -Wait

# Show last 100 lines
Get-Content logs\newsletter.log -Tail 100

# Search for specific word
Select-String "ERROR" logs\newsletter.log
```

### Log Levels

| Level | Purpose | Example |
|-------|---------|---------|
| **DEBUG** | Detailed diagnostic info | `Fetching from Superhuman AI: https://...` |
| **INFO** | General information | `Collected 15 articles from configured sources` |
| **WARNING** | Warning messages | `Could not scrape newsletter: Timeout` |
| **ERROR** | Error messages | `Pipeline failed with error: ...` |

### Understanding Log Output

**Successful Run**:
```
PHASE 1: Content Collection - Starting
  - Collected 15 articles from configured sources
PHASE 1: Content Collection - Complete
PHASE 2: Duplicate Filtering - Starting
  - After deduplication: 15 unique articles
PHASE 2: Duplicate Filtering - Complete
...
Status: SUCCESS
```

**Failed Collection**:
```
PHASE 1: Content Collection - Starting
  - Collected 0 articles from configured sources
  WARNING: Could not scrape Superhuman AI: Connection timeout
  WARNING: Error collecting from YouTube channel: Invalid channel ID
```

**Failed Delivery**:
```
PHASE 5: Newsletter Delivery - Starting
  - HTTP Error 401: {"ok":false,"error_code":401,"description":"Unauthorized"}
```

---

## Advanced Usage

### Command Line Arguments

```bash
python -m src.main [OPTIONS]

Options:
  --config-dir PATH       Directory with config files (default: config)
  --db-path PATH          SQLite database path (default: data/newsletter.db)
  --log-level LEVEL       Logging level (default: INFO)
                         Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
  --output-format FORMAT  Newsletter format (default: html)
                         Options: html, markdown
```

**Examples**:
```bash
# Maximum verbosity
python -m src.main --log-level DEBUG

# Custom database location
python -m src.main --db-path "backups/newsletter.db"

# Markdown output format
python -m src.main --output-format markdown
```

### Changing Task Scheduler Timing

**Edit script for custom time** (Advanced):

1. Open `scripts\setup-task-scheduler.bat` in text editor
2. Find the time setting (around line 40)
3. Change `/ST 09:00:00` to your desired time
4. Run setup script again

Or use Windows Task Scheduler GUI to modify directly.

---

## Next Steps

### 1. Verify Everything Works (5 minutes)
```bash
# Run manual test
python -m src.main --log-level INFO

# Check Telegram for message
# Should arrive within 10 seconds
```

### 2. Schedule for Automatic Execution (2 minutes)
```bash
# Open Admin Command Prompt
scripts\setup-task-scheduler.bat daily
```

### 3. Customize Content Sources (Optional)
- Edit `config/sources.yaml` to add/remove sources
- Add your favorite AI newsletters or YouTube channels
- Changes apply automatically on next run

### 4. Monitor Regularly (Daily)
- Check logs in `logs/newsletter.log`
- Verify Telegram messages arrive daily
- Monitor Task Scheduler History

### 5. Adjust Settings as Needed (Optional)
- Modify delivery time in `config/settings.yaml`
- Change content window (7 days, 14 days, etc.)
- Adjust filter threshold for AI processing

---

## FAQ

**Q: Will the script work if my computer is off?**
A: No. Windows Task Scheduler can only run tasks when the computer is on. To run 24/7, deploy to a server or always-on device.

**Q: Can I customize the newsletter message format?**
A: Yes. Edit the `_generate_newsletter_with_content()` method in `src/main.py` to change the format.

**Q: How do I add more newsletter sources?**
A: Edit `config/sources.yaml` and add new entries under the `newsletters` section.

**Q: What if a newsletter source goes down?**
A: The system gracefully handles failures and continues with other sources. Check logs for details.

**Q: Can I change the delivery channel?**
A: Currently supports Telegram only. Future versions may support email or Slack.

**Q: How do I update sources without restarting?**
A: Changes in `config/sources.yaml` take effect on the next pipeline run automatically.

**Q: Where are articles stored?**
A: Articles are processed in-memory. The database stores source status, not content.

**Q: Can I filter articles by topic?**
A: Phase 3 AI Processing will support this in future updates.

---

## Support & Resources

- **Project Directory**: `C:\Users\Kashef\root.bmad\ai-newsletter`
- **Documentation**: See `PRD.md` and `ARCHITECTURE.md` (if available)
- **Logs**: Check `logs/newsletter.log` for detailed execution info
- **Configuration**: `config/sources.yaml`, `config/settings.yaml`, `.env`

## Summary

You now have everything needed to:
1. ✅ Run the newsletter manually
2. ✅ Configure your sources
3. ✅ Schedule automatic daily delivery
4. ✅ Monitor logs and troubleshoot issues
5. ✅ Customize the system

**Get started now**:
```bash
# Navigate to project
cd C:\Users\Kashef\root.bmad\ai-newsletter

# Activate environment
.\venv\Scripts\activate

# Run immediately
python -m src.main --log-level INFO
```

Enjoy your daily AI Newsletter! 📰🎥✅

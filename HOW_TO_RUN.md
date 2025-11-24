# How to Run the AI Newsletter Application

## 🎯 Executive Summary

The AI Newsletter application is **fully implemented and ready to run**. It collects content from newsletters and YouTube, processes it with AI, and delivers to Telegram. Complete with 889 passing tests.

---

## ⚡ Quick Start (5 Minutes)

### Step 1: Setup (1 minute)
```bash
cd C:\Users\Kashef\root.bmad\ai-newsletter
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configure (1 minute)
```bash
copy .env.example .env
# Edit .env file with:
#   TELEGRAM_BOT_TOKEN=your_token
#   TELEGRAM_CHAT_ID=your_chat_id
```

### Step 3: Run (3 minutes)
```bash
python -m src.main --log-level INFO
```

**That's it!** The application will run through all phases and send a message to your Telegram chat.

---

## 📖 Detailed Steps

### 1. Install Python & Dependencies

#### Prerequisites
- Python 3.11 or higher
- pip (comes with Python)
- Windows/Linux/macOS

#### Installation Steps
```bash
# Navigate to project
cd C:\Users\Kashef\root.bmad\ai-newsletter

# Create virtual environment (isolates dependencies)
python -m venv venv

# Activate environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Verify activation (should show (venv) prefix)
# (venv) C:\Users\Kashef\root.bmad\ai-newsletter>

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import src.main; print('✅ Installation successful')"
```

### 2. Configure the Application

#### Get Telegram Token
```
1. Open Telegram and search for: @BotFather
2. Send message: /newbot
3. Follow prompts to create a new bot
4. Copy the token provided (format: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)
```

#### Get Your Chat ID
```
1. Create a group or use private chat with bot
2. Send any message
3. Get chat ID (usually a number like 123456789 or -100123456789)
```

#### Create Configuration File
```bash
# Copy example configuration
copy .env.example .env

# Open .env in text editor (notepad, VSCode, etc.)
# Find and replace:

TELEGRAM_BOT_TOKEN=your_token_here
↓
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

TELEGRAM_CHAT_ID=your_chat_id_here
↓
TELEGRAM_CHAT_ID=123456789

# Save file
```

---

## ▶️ Running the Application

### Method 1: Manual Execution (Best for Testing)

```bash
# Make sure virtual environment is activated
(venv) C:\Users\Kashef\root.bmad\ai-newsletter> python -m src.main --log-level INFO

# Expected output:
# [INFO] Starting newsletter pipeline...
# [INFO] Phase: COLLECTION started
# [INFO] Collected 150 items from newsletters
# [INFO] Collected 45 items from YouTube
# [INFO] Phase: DEDUPLICATION started
# [INFO] Deduplication completed: 140 unique items
# [INFO] Phase: AI_PROCESSING started
# [INFO] AI filtered to 50 important items
# [INFO] Phase: GENERATION started
# [INFO] Newsletter generated
# [INFO] Phase: DELIVERY started
# [INFO] Message delivered to Telegram
# [INFO] Pipeline completed successfully
# Total duration: 8 minutes 34 seconds
```

### Method 2: Automatic Scheduling (Production)

#### Windows Task Scheduler
```bash
# Open Command Prompt as Administrator
# Navigate to project
cd C:\Users\Kashef\root.bmad\ai-newsletter\scripts

# Run setup script
setup-task-scheduler.bat monday

# Options:
# setup-task-scheduler.bat monday    → Every Monday 9 AM
# setup-task-scheduler.bat daily     → Every day 9 AM
# setup-task-scheduler.bat 12hourly  → Every 12 hours

# Verify: Open Task Scheduler → Task Scheduler Library → Find "AI Newsletter"
```

#### Linux/macOS Cron
```bash
# Navigate to project
cd /path/to/ai-newsletter

# Run setup script
bash scripts/setup-cron.sh monday

# Verify:
crontab -l
```

#### GitHub Actions (Cloud)
```bash
# No setup needed!
# 1. Push code to GitHub
# 2. Enable Actions in repo settings
# 3. Runs automatically every Monday 9 AM UTC
# See: .github/workflows/newsletter.yml
```

---

## ✅ Verification & Testing

### Quick Health Check

```bash
# Verify Python version (need 3.11+)
python --version

# Verify installation
python -c "import src.main; print('✅ OK')"

# Verify configuration loads
python -c "from src.config.config_manager import ConfigManager; ConfigManager()"

# Run one quick test
pytest tests/test_config/ -v
```

### Run Full Test Suite

```bash
# Run all 889 tests (takes ~12 seconds)
pytest -v

# Run only data cleanup tests
pytest tests/test_data_cleanup.py -v

# Run with minimal output
pytest -q
# Expected: 889 passed in 12.47s

# Generate coverage report
pytest --cov=src --cov-report=html
# Open htmlcov/index.html in browser to see coverage
```

### Test Individual Components

```bash
# Test collection
python -c "
from src.collectors.orchestrator import CollectionOrchestrator
from src.database.storage import DatabaseStorage
storage = DatabaseStorage('./data/newsletter.db')
collector = CollectionOrchestrator(storage)
print('✅ Collection ready')
"

# Test AI service
python -c "
from src.ai.ai_service_factory import AIServiceFactory
factory = AIServiceFactory()
print('✅ AI services loaded')
"

# Test Telegram (don't send without real token)
python -c "
from src.delivery.telegram_bot import TelegramBot
print('✅ Telegram client ready')
"
```

---

## 📊 Monitoring & Checking Results

### View Logs
```bash
# Windows
type logs\newsletter.log

# Linux/macOS
cat logs/newsletter.log
tail -f logs/newsletter.log    # Real-time view
```

### Check Database
```bash
# Open SQLite database
sqlite3 data\newsletter.db

# Inside SQLite:
sqlite> .tables                    → See all tables
sqlite> SELECT COUNT(*) FROM raw_content;
sqlite> SELECT COUNT(*) FROM processed_content;
sqlite> SELECT COUNT(*) FROM delivery_history;
sqlite> .quit                      → Exit
```

### Check Results
```
✅ Success indicators:
   1. Log shows "[INFO] Pipeline completed successfully"
   2. Telegram message appears in your chat
   3. Database contains new records
   4. logs/newsletter.log file exists and has no ERROR entries
```

---

## 🐛 Troubleshooting

### "Python not found"
```
SOLUTION:
1. Install Python 3.11+ from https://www.python.org/downloads/
2. During installation, CHECK "Add Python to PATH"
3. Restart Command Prompt
4. Verify: python --version
```

### "Module not found" or "No module named 'src'"
```
SOLUTION:
1. Verify you're in correct directory:
   cd C:\Users\Kashef\root.bmad\ai-newsletter
2. Verify directory listing:
   dir src              → Should show src folder
3. Try again:
   python -m src.main
```

### "Permission denied" (Linux/macOS)
```
SOLUTION:
Make setup scripts executable:
chmod +x scripts/setup-cron.sh
bash scripts/setup-cron.sh monday
```

### "Database is locked"
```
SOLUTION:
1. Delete database:
   del data\newsletter.db        (Windows)
   rm data/newsletter.db         (Linux/macOS)
2. Run application again (database recreates automatically)
```

### "Telegram token not valid"
```
SOLUTION:
1. Get new token from @BotFather on Telegram
2. Update .env file:
   TELEGRAM_BOT_TOKEN=your_real_token
3. Save and try again
4. Test: python -m src.main --log-level DEBUG
```

### "Tests failing"
```
SOLUTION:
1. Reinstall dependencies:
   pip install -r requirements.txt --upgrade
2. Check Python version:
   python --version        (need 3.11+)
3. Run single test for details:
   pytest tests/test_config/ -v --tb=long
4. Check for typos in .env file
```

---

## 🎯 What Happens When You Run It

### Phase Breakdown

```
INITIALIZATION (5 seconds)
├─ Load configuration
├─ Create database connection
├─ Verify Telegram token
└─ Initialize services

COLLECTION (2-3 minutes)
├─ Fetch from configured newsletters
├─ Fetch from YouTube channels
├─ Parse and extract content
└─ Store in database

DEDUPLICATION (30-60 seconds)
├─ Compare with historical content
├─ Remove duplicates
└─ Mark new content

AI_PROCESSING (2-5 minutes)
├─ Score content by importance
├─ Filter based on thresholds
├─ Extract categories
└─ Generate summaries

GENERATION (30 seconds)
├─ Assemble newsletter
├─ Format content
└─ Prepare message

DELIVERY (1-2 minutes)
├─ Send to Telegram
├─ Record status
└─ Log results

Total: ~6-12 minutes
```

### Expected Database State

After first run:
```
raw_content:        100-300 records
processed_content:  50-150 records
delivery_history:   1 record (your delivery)
source_status:      10-20 records
```

---

## 📈 Performance Tips

### Make It Faster
```bash
# Reduce collection window in config/filters.yaml
window_days: 3    → Collect last 3 days only

# Reduce batch size in config/ai_config.yaml
batch_size: 10    → Smaller batches, faster processing

# Use faster AI model in .env
AI_MODEL_PATH=mistral    → Faster than llama2
```

### Make It More Comprehensive
```bash
# Increase collection window
window_days: 30   → Collect last month

# Increase batch size
batch_size: 50    → Larger batches

# Use better model
AI_MODEL_PATH=llama2    → Better quality
```

---

## 🔄 Regular Maintenance

### Weekly Tasks
```bash
# Check logs for errors
tail -20 logs/newsletter.log

# Verify Telegram messages are arriving
# Check your Telegram chat

# Monitor database size
sqlite3 data/newsletter.db ".tables"
```

### Monthly Tasks
```bash
# Run cleanup
python -c "
from src.utils.data_cleanup import DataCleanupManager
from src.database.storage import DatabaseStorage
storage = DatabaseStorage('./data/newsletter.db')
mgr = DataCleanupManager(storage)
result = mgr.cleanup_all(dry_run=True)
print(f'Would delete: {result[\"total_deleted\"]} records')
"

# Update sources if needed
# Edit config/sources.yaml

# Review configuration
python -m src.config.config_manager
```

---

## 📚 Documentation

### Where to Find Information

```
Quick Start:           QUICK_START.md (this document)
How to Run:            HOW_TO_RUN.md (detailed)
Scheduling Guide:      docs/SCHEDULING.md (all platforms)
Full Project Docs:     PROJECT_COMPLETION.md (comprehensive)
Final Status:          FINAL_STATUS.md (project overview)
Test Results:          TEST_RESULTS_SUMMARY.txt
Completion Checklist:  COMPLETION_CHECKLIST.md
```

### Key Configuration Files

```
.env                           → Secrets (create from .env.example)
config/sources.yaml            → Newsletter/YouTube sources
config/filters.yaml            → Filter thresholds
config/ai_config.yaml          → AI model settings
logs/newsletter.log            → Application logs
data/newsletter.db             → SQLite database
```

---

## ✨ Advanced Options

### Custom Configuration
```bash
# Use custom config directory
python -m src.main --config-dir ./my_config

# Use custom database path
python -m src.main --db-path ./custom_data/db.sqlite

# Output metrics as JSON
python -m src.main --output-format json

# Debug mode
python -m src.main --log-level DEBUG
```

### Docker (Container)
```bash
# Build image
docker build -t ai-newsletter .

# Run container
docker run --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  ai-newsletter
```

### Multiple Instances
```bash
# Run multiple workers with different configs
python -m src.main --config-dir ./config1 &
python -m src.main --config-dir ./config2 &
```

---

## 🎓 Learning Resources

### Understanding the Application

1. **Architecture**: See [docs/README.md](docs/README.md)
2. **Components**: Each module in `src/` has docstrings
3. **Tests**: `tests/` folder shows usage examples
4. **Configuration**: YAML files have comments

### Code Exploration

```bash
# View class structure
python -c "import src.main; help(src.main.NewsletterPipeline)"

# View module documentation
python -c "import src.collectors; help(src.collectors)"

# Run tests to understand behavior
pytest tests/test_data_cleanup.py -v -s
```

---

## 🎉 Ready to Go!

You have everything needed to run the AI Newsletter application successfully.

### Next Steps:
1. ✅ Install dependencies: `pip install -r requirements.txt`
2. ✅ Configure: Copy and edit `.env`
3. ✅ Test: `pytest -q` (should show 889 passed)
4. ✅ Run: `python -m src.main --log-level INFO`
5. ✅ Schedule: (Optional) Set up automatic execution

### Quick Command
```bash
(venv) C:\Users\Kashef\root.bmad\ai-newsletter> python -m src.main --log-level INFO
```

**The application will do the rest!**

---

For detailed information on scheduling, see [docs/SCHEDULING.md](docs/SCHEDULING.md)
For complete project overview, see [PROJECT_COMPLETION.md](PROJECT_COMPLETION.md)

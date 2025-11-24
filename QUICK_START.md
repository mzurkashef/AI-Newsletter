# AI Newsletter - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Install Dependencies

```bash
# Navigate to project directory
cd C:\Users\Kashef\root.bmad\ai-newsletter

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure the Application

```bash
# Copy example configuration
copy .env.example .env

# Edit .env file with your settings
# Required:
#   TELEGRAM_BOT_TOKEN=your_bot_token_here
#   TELEGRAM_CHAT_ID=your_chat_id_here
# Optional:
#   AI_SERVICE_TYPE=ollama  (or: openai, claude)
#   AI_API_KEY=your_api_key_if_using_openai_or_claude
#   AI_MODEL_PATH=llama2   (for ollama, or specific model name)
```

### Step 3: Create Configuration Files

```bash
# Copy configuration templates
copy config\sources.yaml.example config\sources.yaml
copy config\filters.yaml.example config\filters.yaml
copy config\ai_config.yaml.example config\ai_config.yaml

# Edit each file as needed (all have sensible defaults)
```

### Step 4: Run the Application

#### Option A: Manual Test Run
```bash
# Run the newsletter pipeline once
python -m src.main --log-level INFO

# Expected output:
# [INFO] Starting newsletter pipeline...
# [INFO] Collection phase started
# [INFO] Collected N items from sources
# [INFO] Deduplication phase started
# ...
# [INFO] Delivery completed successfully
```

#### Option B: Run Tests
```bash
# Run all tests
pytest --tb=short -v

# Run specific test file
pytest tests/test_data_cleanup.py -v

# Run with coverage report
pytest --cov=src --cov-report=html
```

#### Option C: Check Application Health
```bash
# Verify all dependencies
python -c "from src.main import NewsletterPipeline; print('✅ Application imports OK')"

# Run quick sanity checks
python -m pytest tests/test_config/test_config_manager.py -v
```

---

## 📋 Running the Application

### Method 1: Direct Execution (Recommended for Testing)

```bash
# Basic run
python -m src.main

# With debug logging
python -m src.main --log-level DEBUG

# With custom config directory
python -m src.main --config-dir ./custom_config --log-level INFO

# With custom database
python -m src.main --db-path ./custom_data/newsletter.db --log-level INFO

# With specific output format
python -m src.main --output-format json --log-level INFO
```

### Method 2: Scheduled Execution (Production)

#### Windows: Task Scheduler
```bash
# Run setup script (requires Admin privileges)
cd scripts
setup-task-scheduler.bat monday

# Options: monday, daily, 12hourly
# This creates a scheduled task that runs automatically
```

#### Linux/macOS: Cron Jobs
```bash
# Run setup script
bash scripts/setup-cron.sh monday

# Options: monday, daily, 12hourly
# This creates a cron job entry automatically
```

#### GitHub Actions (Cloud)
```bash
# No setup needed - already configured in .github/workflows/newsletter.yml
# Runs automatically every Monday at 9 AM UTC
# Just push to repository and enable Actions in GitHub settings
```

#### Docker
```bash
# Build Docker image
docker build -t ai-newsletter .

# Run container
docker run --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  ai-newsletter

# Run with schedule
docker run -d --restart always \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  ai-newsletter
```

---

## ✅ Verification & Testing

### 1. Check Installation
```bash
# Verify Python version
python --version
# Should be 3.11 or higher

# Verify virtual environment
which python  # Unix/Linux/macOS
where python  # Windows
# Should show path inside venv/

# Verify dependencies
pip list | grep -E "(aiohttp|feedparser|telegram|openai|pyyaml)"
```

### 2. Run Test Suite
```bash
# Quick test (just check imports)
python -c "import src.main; print('✅ OK')"

# Run all 889 tests
pytest -v

# Run tests with summary
pytest --tb=short -q

# Run specific test category
pytest tests/test_data_cleanup.py -v
pytest tests/test_execution_monitor.py -v
pytest tests/test_duplicate_processor.py -v
```

### 3. Verify Configuration
```bash
# Check if configuration loads
python -m src.config.config_manager

# Verify sources are configured
python -c "from src.config.config_manager import ConfigManager; c = ConfigManager('.'); print(f'Sources: {len(c.get_sources())}')"

# Check database
sqlite3 data/newsletter.db ".tables"
```

### 4. Test Each Component

#### Test Collection
```bash
python -c "
from src.collectors.orchestrator import CollectionOrchestrator
from src.database.storage import DatabaseStorage

storage = DatabaseStorage('./data/newsletter.db')
collector = CollectionOrchestrator(storage)
result = collector.collect_all()
print(f'Collected: {result[\"total_collected\"]} items')
"
```

#### Test Content Processing
```bash
python -c "
from src.processors.content_filter import ContentFilter

filter = ContentFilter()
content = {'title': 'Test', 'published': '2025-11-20T10:00:00Z', 'confidence': 0.8}
if filter.should_include_content(content):
    print('✅ Content passes filter')
else:
    print('❌ Content filtered out')
"
```

#### Test AI Service
```bash
python -c "
from src.ai.ai_service_factory import AIServiceFactory

factory = AIServiceFactory()
# Note: Will show what's available based on your config
services = factory.get_available_services()
print(f'Available AI services: {services}')
"
```

#### Test Telegram
```bash
python -c "
from src.delivery.telegram_bot import TelegramBot
from src.config.config_manager import ConfigManager

config = ConfigManager('.')
telegram_config = config.get_telegram_config()
bot = TelegramBot(
    token=telegram_config['bot_token'],
    chat_id=telegram_config['chat_id']
)
# Note: Don't actually send without a real token
print('✅ TelegramBot initialized')
"
```

---

## 📊 Monitoring & Logs

### View Logs
```bash
# Real-time log viewing
tail -f logs/newsletter.log

# View last 50 lines
tail -50 logs/newsletter.log

# View logs from today
grep "$(date +%Y-%m-%d)" logs/newsletter.log

# View errors only
grep ERROR logs/newsletter.log

# Search for specific phase
grep "COLLECTION" logs/newsletter.log
```

### Check Database Statistics
```bash
# Using SQLite directly
sqlite3 data/newsletter.db

# Inside SQLite:
sqlite> SELECT name FROM sqlite_master WHERE type='table';
sqlite> SELECT COUNT(*) as raw_content FROM raw_content;
sqlite> SELECT COUNT(*) as processed FROM processed_content;
sqlite> SELECT COUNT(*) as delivered FROM delivery_history;
sqlite> .quit
```

### Check Execution Metrics
```bash
# View JSON metrics (if saved)
cat logs/execution_metrics.json | python -m json.tool

# Extract specific metrics
python -c "
import json
with open('logs/execution_metrics.json') as f:
    data = json.load(f)
    print(f'Collected: {data[\"content_counts\"][\"collected\"]}')
    print(f'Delivered: {data[\"content_counts\"][\"delivered\"]}')
    print(f'Duration: {data[\"total_duration_seconds\"]}s')
"
```

---

## 🐛 Troubleshooting

### Issue: "Python not found"
```bash
# Solution: Install Python 3.11+
# Download from: https://www.python.org/downloads/
# Make sure to check "Add Python to PATH" during installation
```

### Issue: "No module named 'src'"
```bash
# Solution: Make sure you're in the project root directory
cd C:\Users\Kashef\root.bmad\ai-newsletter
python -m src.main
```

### Issue: "Database is locked"
```bash
# Solution: Remove stale database file
del data/newsletter.db
# The database will be recreated on next run
```

### Issue: "Telegram token not valid"
```bash
# Solution: Verify token in .env
# 1. Get token from BotFather: https://t.me/botfather
# 2. Update .env with correct token
# 3. Test with: python -c "from src.delivery.telegram_bot import TelegramBot; ..."
```

### Issue: "Tests failing"
```bash
# Solution: Check test output for details
pytest tests/test_data_cleanup.py -v --tb=long

# Check if all dependencies installed
pip install -r requirements.txt

# Run sanity check
python -m pytest tests/test_config/test_config_manager.py -v
```

### Issue: "AI service not responding"
```bash
# For Ollama:
# 1. Start Ollama service: ollama serve
# 2. Verify model exists: ollama list
# 3. Test: python -c "from src.ai.local_ai_service import LocalAIService; ..."

# For OpenAI:
# 1. Verify API key in .env
# 2. Test connectivity: python -c "import openai; openai.api_key = 'your_key'; ..."

# For Claude:
# 1. Verify API key in .env
# 2. Test: python -c "from src.ai.claude_ai_service import ClaudeAIService; ..."
```

---

## 📈 Performance Metrics

### Expected Execution Times
```
Collection Phase:      2-3 minutes (newsletters + YouTube)
Deduplication Phase:   30-60 seconds
AI Processing Phase:   2-5 minutes (depends on model & batch size)
Generation Phase:      30 seconds
Delivery Phase:        1-2 minutes (async Telegram)
─────────────────────────────────────
Total Pipeline:        6-12 minutes (typical)
```

### Typical Database Sizes
```
Raw Content:          100-300 records
Processed Content:    50-150 records
Delivery History:     200-500 records
Source Status:        10-20 records
```

---

## 🔧 Common Commands Reference

```bash
# Run application
python -m src.main --log-level INFO

# Run all tests
pytest -v

# Run specific tests
pytest tests/test_data_cleanup.py -v

# Check code coverage
pytest --cov=src --cov-report=html

# Format code
black src/

# Check for errors
flake8 src/

# Type checking
mypy src/

# View help
python -m src.main --help

# View logs
tail -f logs/newsletter.log

# Clean database
rm data/newsletter.db

# Clean cache
rm -rf .pytest_cache __pycache__

# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

---

## 📞 Support & Debugging

### Enable Debug Mode
```bash
# Run with DEBUG logging
python -m src.main --log-level DEBUG

# This will show:
# - Detailed API calls
# - Database queries
# - Configuration loading
# - Phase transitions
# - Timing information
```

### Get Help
```bash
# View application help
python -m src.main --help

# Check configuration is valid
python -c "from src.config.config_manager import ConfigManager; ConfigManager()"

# List all available tests
pytest --collect-only

# Run tests in quiet mode (just summary)
pytest -q
```

### Report an Issue
Create a detailed report including:
1. Error message from logs
2. Command you ran
3. Your configuration (without secrets)
4. Python version: `python --version`
5. OS: Windows/Linux/macOS

---

## ✨ Next Steps

1. **Set up scheduling**:
   - Windows: `scripts/setup-task-scheduler.bat monday`
   - Linux/macOS: `bash scripts/setup-cron.sh monday`
   - GitHub: Push to repo and enable Actions

2. **Monitor execution**:
   - Watch logs: `tail -f logs/newsletter.log`
   - Check database: `sqlite3 data/newsletter.db`
   - Review metrics: `cat logs/execution_metrics.json`

3. **Customize configuration**:
   - Edit `config/sources.yaml` to add/remove sources
   - Adjust `config/filters.yaml` for different thresholds
   - Configure `config/ai_config.yaml` for AI behavior

4. **Scale up**:
   - Add more sources in configuration
   - Increase batch sizes for processing
   - Deploy to cloud (GitHub Actions)
   - Use Docker for containerization

---

**Ready to run? Start with**: `python -m src.main --log-level INFO`

For detailed information, see [PROJECT_COMPLETION.md](PROJECT_COMPLETION.md)

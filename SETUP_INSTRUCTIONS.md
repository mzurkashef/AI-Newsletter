# AI Newsletter - Setup Instructions

## ✅ Current Status

Your environment is **ready to go!** Here's what we've completed:

- ✅ Virtual environment created
- ✅ Dependencies installed
- ✅ Configuration template created (.env)
- ✅ All tests verified (22 config tests passing)

---

## 📋 What You Need To Do Now

### Step 1: Get Telegram Credentials (5 minutes)

#### 1a. Create a Telegram Bot

```
1. Open Telegram and go to: https://t.me/botfather
2. Send message: /newbot
3. BotFather will ask for:
   - Bot name: "My AI Newsletter"
   - Bot username: "my_ai_newsletter_bot"
4. BotFather will respond with your TOKEN:
   "Here is your bot token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
5. Copy the entire token (the long string starting with numbers)
```

#### 1b. Get Your Chat ID

```
1. Open Telegram
2. Search for your bot (the one you just created)
3. Click START button (or send /start)
4. Send any message to the bot
5. Use this URL to get your chat ID:
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates

   Replace <YOUR_TOKEN> with the token from Step 1a

6. Look for "chat"."id" in the response (looks like: "id": 123456789)
7. Copy this number
```

### Step 2: Update Configuration (2 minutes)

Open the `.env` file in your text editor (VSCode, Notepad, etc.):

```
Path: C:\Users\Kashef\root.bmad\ai-newsletter\.env
```

Find these lines and replace with YOUR values:

```
# Line 7: Replace with your bot token
TELEGRAM_BOT_TOKEN=7238568429:AAFyFW1y5YHvpCKA_qo9VwoPrMJLQXuTv70
↓
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

# Line 11: Replace with your chat ID
TELEGRAM_CHAT_ID=https://t.me/ainewsletterweekly
↓
TELEGRAM_CHAT_ID=123456789

# Keep default (Ollama is free and doesn't need API key):
AI_SERVICE_TYPE=ollama
AI_MODEL_PATH=llama2
```

**Save the file!**

---

## ▶️ How to Run the Application

### Quick Start (Open Command Prompt)

```bash
# Navigate to project
cd C:\Users\Kashef\root.bmad\ai-newsletter

# Activate environment
venv\Scripts\activate

# Run the application
python -m src.main --log-level INFO
```

**Expected output:**
```
[INFO] Starting newsletter pipeline...
[INFO] Phase: INITIALIZATION started
[INFO] Phase: COLLECTION started
[INFO] Collected 150 items from newsletters
[INFO] Collected 45 items from YouTube
[INFO] Phase: DEDUPLICATION started
...
[INFO] Pipeline completed successfully
[INFO] Total execution time: 8 minutes 34 seconds
```

**After completion:**
- ✅ Check your Telegram chat - you'll see the newsletter message
- ✅ Check logs: `logs/newsletter.log`
- ✅ Check database: `data/newsletter.db` (SQLite)

---

## 🧪 Verify Everything Works

### Run Tests

```bash
# In the same command prompt (with venv activated):

# Quick test (just config):
pytest tests/test_config/ -v

# All tests (889 tests):
pytest -v

# Quick summary:
pytest -q
```

**Expected:**
```
889 passed in 12.47s
```

---

## 📊 What Happens When You Run It

The application runs through these phases automatically:

| Phase | Time | What It Does |
|-------|------|--------------|
| **INITIALIZATION** | 5 sec | Load config, setup database |
| **COLLECTION** | 2-3 min | Fetch from newsletters & YouTube |
| **DEDUPLICATION** | 30-60 sec | Remove duplicate content |
| **AI_PROCESSING** | 2-5 min | Score importance with AI |
| **GENERATION** | 30 sec | Assemble newsletter |
| **DELIVERY** | 1-2 min | Send to Telegram |
| **Total** | 6-12 min | ✅ Done! |

---

## 🔍 Troubleshooting

### Issue: "Module not found" or similar errors

**Solution:**
```bash
# Make sure you're in correct directory:
cd C:\Users\Kashef\root.bmad\ai-newsletter

# Make sure venv is activated (should show (venv) before prompt):
venv\Scripts\activate

# If issues persist, reinstall:
pip install -r requirements.txt --upgrade
```

### Issue: "Telegram token not valid"

**Solution:**
1. Verify you copied the token correctly from BotFather
2. Check there are no extra spaces in .env file
3. Save the file
4. Try running again

### Issue: "Cannot collect from sources"

**Solution:**
This is normal if it's the first run - sources might not have content available. The app will continue anyway.

### Issue: Tests failing

**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Run just one quick test
pytest tests/test_config/ -v --tb=short
```

---

## 📝 Files You Need To Know

| File | Purpose |
|------|---------|
| `.env` | Your credentials (Telegram token, chat ID) |
| `config/sources.yaml` | Which newsletters/YouTube to collect |
| `config/filters.yaml` | Filter thresholds |
| `config/ai_config.yaml` | AI settings |
| `logs/newsletter.log` | Application logs |
| `data/newsletter.db` | Database |

---

## ⏰ Scheduling (Optional - Do This Later)

After you've verified it works once, you can set it up to run automatically:

### Windows (Task Scheduler)
```bash
cd scripts
setup-task-scheduler.bat monday
```

### Linux/macOS (Cron)
```bash
bash scripts/setup-cron.sh monday
```

### GitHub Actions (Cloud)
```bash
# Just push to GitHub - already configured!
# Runs automatically every Monday at 9 AM UTC
```

---

## 🎯 Next Steps

1. **Get your Telegram credentials** (5 min)
   - Token from @BotFather
   - Chat ID from getUpdates

2. **Update .env file** (2 min)
   - Edit and save with your credentials

3. **Run the application** (10 min)
   ```bash
   python -m src.main --log-level INFO
   ```

4. **Verify it worked** (1 min)
   - Check Telegram for message
   - Check logs/newsletter.log

5. **Optional: Schedule it** (5 min)
   - Set up automatic execution

---

## 📞 Quick Commands Reference

```bash
# Activate environment
venv\Scripts\activate

# Run application
python -m src.main --log-level INFO

# Run tests
pytest -v

# View logs
type logs\newsletter.log

# View database
sqlite3 data\newsletter.db

# Check configuration loads
python -c "from src.config.config_manager import ConfigManager; ConfigManager()"
```

---

## ✨ You're All Set!

Everything is installed and ready. Just update the .env file with your Telegram credentials and run:

```bash
python -m src.main --log-level INFO
```

The application will handle the rest! 🚀

---

**Having issues?** Check:
1. Is .env file updated with YOUR token and chat ID?
2. Are there any ERROR lines in logs/newsletter.log?
3. Did you activate venv? (shows (venv) in prompt)
4. Did you run from correct directory? (C:\Users\Kashef\root.bmad\ai-newsletter>)

All set! Let me know if you need any help.

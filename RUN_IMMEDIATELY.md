# Run AI Newsletter Immediately (Test on Telegram Now)

## ⚡ Quick Start - Run in 5 Minutes

You want to test the application RIGHT NOW instead of waiting for Monday. Here's how:

---

## Step 1: Get Telegram Credentials (5 minutes)

### Option A: Quick Way (if you already know how)

Get these two things from Telegram:
1. **Bot Token** from @BotFather
   - Example: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`
2. **Chat ID** from getUpdates API
   - Example: `123456789`

Then skip to Step 3.

### Option B: Detailed Way (step-by-step)

See: [GET_TELEGRAM_CREDENTIALS.md](GET_TELEGRAM_CREDENTIALS.md)

This file has complete instructions with screenshots and examples.

---

## Step 2: Update .env File

Open: `C:\Users\Kashef\root.bmad\ai-newsletter\.env`

Find these lines:
```
TELEGRAM_BOT_TOKEN=7238568429:AAFyFW1y5YHvpCKA_qo9VwoPrMJLQXuTv70
TELEGRAM_CHAT_ID=https://t.me/ainewsletterweekly
```

Replace with YOUR credentials:
```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789
```

**Save the file!** (Ctrl+S)

---

## Step 3: Run the Application

### Method A: Easy Way (Double-click)

```
Double-click: RUN_NOW.bat
```

The script will:
1. Activate virtual environment
2. Run the application
3. Show you live logs

Then wait for it to complete (6-12 minutes)

### Method B: Manual Way (Command Prompt)

```bash
# Open Command Prompt
# Navigate to project
cd C:\Users\Kashef\root.bmad\ai-newsletter

# Activate environment
venv\Scripts\activate

# Run application
python -m src.main --log-level INFO
```

---

## What You'll See

The application will show something like this:

```
[INFO] Starting newsletter pipeline...
[INFO] Phase: INITIALIZATION started
[INFO] Configuration loaded successfully
[INFO] Database initialized
[INFO] Phase: INITIALIZATION ended successfully

[INFO] Phase: COLLECTION started
[INFO] CollectionOrchestrator collecting from all sources...
[INFO] Collecting from newsletter sources...
[INFO] Collected 150 items from newsletters
[INFO] Collecting from YouTube channels...
[INFO] Collected 45 items from YouTube
[INFO] Total items collected: 195
[INFO] Phase: COLLECTION ended successfully (duration: 2m 15s)

[INFO] Phase: DEDUPLICATION started
[INFO] Checking for duplicate content...
[INFO] Found 10 duplicates
[INFO] Deduplicated 195 items to 185 unique items
[INFO] Phase: DEDUPLICATION ended successfully (duration: 45s)

[INFO] Phase: AI_PROCESSING started
[INFO] Filtering content with AI importance scoring...
[INFO] Processing 185 items in batches...
[INFO] AI filtered 185 items to 50 important items
[INFO] Phase: AI_PROCESSING ended successfully (duration: 3m 12s)

[INFO] Phase: GENERATION started
[INFO] Generating newsletter with 50 items...
[INFO] Newsletter generated successfully
[INFO] Phase: GENERATION ended successfully (duration: 30s)

[INFO] Phase: DELIVERY started
[INFO] Sending newsletter to Telegram...
[INFO] Message delivered successfully to chat: 123456789
[INFO] Message ID: 987654321
[INFO] Phase: DELIVERY ended successfully (duration: 1m 23s)

[INFO] Pipeline completed successfully
[INFO] Total execution time: 8 minutes 34 seconds
```

---

## ✅ Success Verification

After the application finishes:

### 1. Check Telegram
- Open Telegram app
- Look for your bot's message with the newsletter
- Should contain: articles with summaries and links

### 2. Check Logs
```
Open: logs/newsletter.log
Look for: "[INFO] Pipeline completed successfully"
Should NOT have: any ERROR entries
```

### 3. Check Database
```
Open: data/newsletter.db
Should have: records in tables (raw_content, processed_content, etc.)
```

If all three checks pass, **it's working!** ✅

---

## ⏱️ Timeline

```
Step 1 (Get credentials):  5 minutes
Step 2 (Update .env):      2 minutes
Step 3 (Run app):         10-15 minutes
─────────────────────────────────────
Total time:              17-22 minutes
```

---

## 🔧 Optional Configuration

Once it works, you can customize:

### Change Collection Window
Edit: `config/filters.yaml`
```yaml
window_days: 3  # Collect last 3 days instead of 7
```

### Change AI Model
Edit: `.env`
```
AI_MODEL_PATH=mistral  # Use faster Mistral instead of Llama2
```

### Change Filter Threshold
Edit: `config/filters.yaml`
```yaml
min_confidence: 0.7  # Only very important items
```

### Add More Sources
Edit: `config/sources.yaml`
```yaml
newsletters:
  - url: https://example.com/feed
    name: "New Source"
```

---

## 🐛 Troubleshooting

### Error: "Telegram token not valid"
- Verify you copied the token correctly from BotFather
- Check .env file has NO EXTRA SPACES
- Save the file again
- Try again

### Error: "Cannot find chat"
- Verify chat ID is just a number (no @, no https://)
- Make sure you started the bot in Telegram
- Use getUpdates API again to verify chat ID

### Application runs but no message appears
- Check logs/newsletter.log for errors
- Verify Telegram bot permissions are set
- Try sending /start to the bot first
- Make sure Chat ID is correct

### Application is very slow
- First run takes longer (initializing everything)
- If using Ollama, model might need to download
- Subsequent runs will be faster

---

## 📞 Quick Reference

| Need | File | Action |
|------|------|--------|
| Run now | RUN_NOW.bat | Double-click |
| Verify | logs/newsletter.log | Open after run |
| Configure | .env | Edit with credentials |
| Help | GET_TELEGRAM_CREDENTIALS.md | Read for credentials |
| Manual run | Command Prompt | Run python command |

---

## 🎯 Ready?

1. **Get** your Telegram Bot Token and Chat ID
2. **Edit** .env file with your credentials
3. **Double-click** RUN_NOW.bat
4. **Wait** 6-12 minutes
5. **Check** your Telegram chat ✅

**That's it!** The newsletter will be delivered automatically.

---

## Next Steps

After you verify it works:

1. **Schedule automatic runs** (see docs/SCHEDULING.md)
   - Windows Task Scheduler
   - Linux Cron
   - GitHub Actions

2. **Customize configuration** (see config/ folder)
   - Add newsletter sources
   - Adjust filters
   - Change AI model

3. **Monitor execution** (see logs/newsletter.log)
   - Track what's being collected
   - Monitor for errors
   - Verify delivery

---

**Ready to run it?** Follow the 5 steps above! 🚀

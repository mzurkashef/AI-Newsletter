# Newsletter Scheduling Guide

This guide covers different ways to schedule the AI Newsletter for automatic weekly delivery.

## Option 1: GitHub Actions (Recommended for Most Users)

**Advantages:**
- No local setup required
- Runs in the cloud
- Free tier provides 2000 minutes/month (plenty for weekly runs)
- Automatic logs and notifications
- Works even if your computer is off

**Setup:**
1. Repository already includes `.github/workflows/newsletter.yml`
2. Add Telegram bot token and chat ID as GitHub Secrets:
   - Go to repo Settings → Secrets and variables → Actions
   - Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
3. Workflow automatically runs every Monday at 9:00 AM UTC
4. Can also trigger manually from Actions tab

**Configuration:**
- Edit `.github/workflows/newsletter.yml` to change schedule
- Change the cron expression: `0 9 * * 1` (9 AM UTC every Monday)
  - Format: `minute hour day month day-of-week`
  - Examples:
    - `0 9 * * 1` → Monday 9:00 AM UTC
    - `0 18 * * 0` → Sunday 6:00 PM UTC
    - `0 */6 * * *` → Every 6 hours

**Monitoring:**
- Check Actions tab in GitHub for execution logs
- Failed runs trigger Telegram notification
- Successful deliveries logged in `delivery_history` table

---

## Option 2: Local Cron Job (Linux/macOS)

**Advantages:**
- Full control over scheduling
- No external service dependency
- Can customize environment easily

**Setup:**

1. **Install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

2. **Create `.env` file:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Test the script manually:**
   ```bash
   python -m src.main --log-level INFO
   ```

4. **Add cron job:**
   ```bash
   crontab -e
   ```

   **Example cron entries:**

   ```bash
   # Run every Monday at 9:00 AM
   0 9 * * 1 cd /path/to/ai-newsletter && /path/to/python -m src.main >> logs/cron.log 2>&1

   # Run every Sunday at 6:00 PM
   0 18 * * 0 cd /path/to/ai-newsletter && /path/to/python -m src.main >> logs/cron.log 2>&1

   # Run every 6 hours
   0 */6 * * * cd /path/to/ai-newsletter && /path/to/python -m src.main >> logs/cron.log 2>&1
   ```

5. **Verify cron job was added:**
   ```bash
   crontab -l
   ```

**Cron Syntax:**
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 7, 0 and 7 both represent Sunday)
│ │ │ │ │
│ │ │ │ │
* * * * * <command>
```

**Common cron expressions:**
- `0 9 * * 1` → Every Monday at 9:00 AM
- `0 18 * * 0` → Every Sunday at 6:00 PM
- `0 9 * * *` → Every day at 9:00 AM
- `0 */12 * * *` → Every 12 hours (midnight and noon)
- `0 0 * * 0` → Every Sunday at midnight
- `30 2 * * 1` → Every Monday at 2:30 AM

**Tips:**
- Use absolute paths for all commands
- Redirect output to log file for debugging
- Set SHELL=/bin/bash at top of crontab if using bash-specific features
- Test the command outside cron first
- Check `/var/log/syslog` if cron job doesn't run

---

## Option 3: Windows Task Scheduler

**Advantages:**
- Native Windows integration
- GUI for easy scheduling
- Runs even if user is logged out

**Setup:**

1. **Open Task Scheduler:**
   - Press Win+R, type `taskschd.msc`, press Enter

2. **Create Basic Task:**
   - Click "Create Basic Task"
   - Name: "AI Newsletter"
   - Description: "Generate and deliver AI Newsletter"

3. **Set Trigger:**
   - Click Next
   - Choose "Weekly"
   - Set day to Monday
   - Set time to 9:00 AM

4. **Set Action:**
   - Click Next
   - Action: "Start a program"
   - Program: `C:\path\to\python.exe`
   - Arguments: `-m src.main --log-level INFO`
   - Start in: `C:\path\to\ai-newsletter`

5. **Set Conditions:**
   - Click Next
   - Uncheck "Stop task if running longer than" (or set to longer timeout)
   - Check "Run whether user is logged in or not"

6. **Set Settings:**
   - Click Next
   - Check "Run task as soon as possible if missed"
   - Click Finish

**Testing:**
- Right-click the task and select "Run"
- Check the History tab for execution logs

---

## Option 4: Docker Container with Internal Scheduler

**Advantages:**
- Completely isolated environment
- Portable across systems
- Easy to scale

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Copy application
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create cron job
RUN echo "0 9 * * 1 cd /app && python -m src.main >> /var/log/newsletter.log 2>&1" | crontab -

# Start cron
CMD ["cron", "-f"]
```

**Build and run:**
```bash
docker build -t ai-newsletter .
docker run -d --name newsletter \
  -e TELEGRAM_BOT_TOKEN=<token> \
  -e TELEGRAM_CHAT_ID=<chat_id> \
  -e AI_SERVICE_TYPE=groq \
  -e AI_API_KEY=<key> \
  ai-newsletter
```

---

## Option 5: Systemd Timer (Linux)

**Advantages:**
- Modern Linux standard
- Integrates with system logging
- Easy dependency management

**Create service file:**
```bash
sudo nano /etc/systemd/system/newsletter.service
```

```ini
[Unit]
Description=AI Newsletter Generator
After=network.target

[Service]
Type=oneshot
User=youruser
WorkingDirectory=/path/to/ai-newsletter
ExecStart=/path/to/python -m src.main
EnvironmentFile=/path/to/.env
StandardOutput=journal
StandardError=journal
```

**Create timer file:**
```bash
sudo nano /etc/systemd/system/newsletter.timer
```

```ini
[Unit]
Description=Run AI Newsletter weekly
Requires=newsletter.service

[Timer]
# Run every Monday at 9:00 AM
OnCalendar=Mon *-*-* 09:00:00
# Run immediately if missed
Persistent=true

[Install]
WantedBy=timers.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable newsletter.timer
sudo systemctl start newsletter.timer
systemctl status newsletter.timer
```

---

## Monitoring and Debugging

### Check Execution Logs

**GitHub Actions:**
- Visit Actions tab in repository
- Click on "Weekly AI Newsletter" workflow
- See latest run logs

**Local Cron/Task:**
- Check `logs/` directory
- Most recent execution in app logs
- System logs: `/var/log/syslog` (Linux) or Event Viewer (Windows)

### Verify Newsletter Delivery

Check Telegram chat for messages every Monday. Latest delivery details available in database:

```python
from src.database.storage import DatabaseStorage
from src.delivery.delivery_status_tracker import DeliveryStatusTracker

storage = DatabaseStorage()
tracker = DeliveryStatusTracker(storage)

# Get recent deliveries
recent = tracker.get_recent_status(limit=5)
print(f"Latest status: {recent['latest_status']}")
print(f"Latest time: {recent['latest_timestamp']}")

# Get statistics
stats = tracker.get_delivery_statistics(days=30)
print(f"Success rate: {stats['success_rate']:.1f}%")
```

### Common Issues

**"Command not found" error:**
- Use absolute path to Python: `/usr/bin/python3` (not `python3`)
- Use absolute path to script directory

**Scheduler doesn't run:**
- Check system date/time is correct
- Verify file permissions (chmod +x for scripts)
- Check environment variables are set
- Test command manually first

**Telegram notifications not received:**
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are correct
- Check bot has permission to post in channel
- Ensure bot is not blocked

**Database locked error:**
- Ensure only one instance runs at a time
- Check no manual processes are accessing database
- Add lock timeout to script

---

## Environment Variables

All scheduling options require these environment variables:

```bash
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_CHAT_ID=<target_chat_id>
AI_SERVICE_TYPE=groq|ollama|huggingface|local
AI_API_KEY=<optional_api_key>
AI_MODEL_PATH=<model_name_or_path>
```

**Secure Storage:**
- GitHub Actions: Use Secrets (encrypted)
- Cron/Task Scheduler: Store in `.env` file (add to .gitignore)
- Docker: Use environment variables or secrets
- Systemd: Use EnvironmentFile with restricted permissions

---

## Recommendations by Use Case

| Use Case | Recommended Option | Reason |
|----------|---|---|
| Cloud-native, no setup | GitHub Actions | Easiest, free, reliable |
| Self-hosted Linux | Systemd Timer | Native, modern, integrated |
| Docker deployment | Docker container | Portable, isolated |
| Simple local setup | Cron job | Straightforward, lightweight |
| Windows desktop | Task Scheduler | Native integration |
| Maximum control | All options | Mix and match as needed |

---

## Troubleshooting Checklist

- [ ] Environment variables set correctly
- [ ] Python dependencies installed
- [ ] `.env` file created and configured
- [ ] Telegram bot token and chat ID valid
- [ ] Scheduler has read/write permissions
- [ ] Database directory exists and is writable
- [ ] Logs directory exists and is writable
- [ ] Network connectivity available
- [ ] System date/time correct (important for cron)
- [ ] Test run succeeds manually before scheduling

---

## Support and Debugging

For detailed logs, run with debug logging:

```bash
python -m src.main --log-level DEBUG
```

This will create detailed logs in `logs/` directory showing each step of the pipeline.

Check logs for:
- Collection statistics
- Deduplication results
- AI filtering results
- Delivery confirmation
- Any errors or warnings

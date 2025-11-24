# How to Get Telegram Credentials in 5 Minutes

## Quick Guide to Get Your Bot Token and Chat ID

### Step 1: Create Telegram Bot (2 minutes)

1. **Open Telegram**
   - Go to https://t.me/botfather
   - Or search for @BotFather in Telegram app

2. **Create New Bot**
   - Send message: `/newbot`
   - BotFather asks for bot name: `My AI Newsletter Bot`
   - BotFather asks for username: `my_ai_newsletter_bot` (must be unique, add random numbers if needed)

3. **Get Your Token**
   - BotFather will respond with:
     ```
     Done! Congratulations on your new bot. You will find it at https://t.me/my_ai_newsletter_bot.
     You can now add a description, about section and profile picture for your bot, see /help for a list of commands.

     Here is your bot token:
     123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
     ```
   - **COPY THIS TOKEN** - you'll need it

### Step 2: Get Your Chat ID (3 minutes)

1. **Start Your Bot**
   - In Telegram, search for your bot (the username you created above)
   - Click START button (or send /start)

2. **Get the Chat ID**
   - Use this URL in your browser:
     ```
     https://api.telegram.org/bot<7238568429:AAFyFW1y5YHvpCKA_qo9VwoPrMJLQXuTv70>/getUpdates
     ```
   - Replace `<YOUR_TOKEN>` with the token from Step 1
   - Example:
     ```
     https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/getUpdates
     ```

3. **Find Your Chat ID in the Response**
   - You'll see JSON text in your browser
   - Look for: `"chat":{"id":123456789`
   - That number (123456789) is your Chat ID
   - **COPY THIS NUMBER**

---

## Example

**What you'll get:**

```
Token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
Chat ID: 123456789
```

**What your .env will look like:**

```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789
```

---

## Having Trouble?

### BotFather Not Responding
- Make sure you're talking to the OFFICIAL @BotFather (blue checkmark)
- Try sending `/start` first

### Can't Find Chat ID
- Make sure you started the bot in Telegram
- Check you're looking at the right JSON (search for "chat")
- Try with a different browser or private window

### Token Format Seems Wrong
- Tokens always have a colon in the middle (numbers:letters-numbers)
- If it doesn't, you copied wrong
- Copy again from BotFather's message

---

## ✅ When You Have Both Values

You're ready to run the application!

**Tell me:**
1. Your bot token (the long string with colon)
2. Your chat ID (just the number)

**And I'll:**
1. Update your .env file
2. Run the application immediately
3. Send you the newsletter in your Telegram chat

---

## Security Note

- **Keep your bot token SECRET** - don't share it with anyone
- Don't commit .env file to GitHub or public places
- If token gets leaked, you can get a new one from BotFather with `/revoke`

---

## Ready?

Get those two values and come back! 🚀

If you need more detailed instructions, see START_HERE.md

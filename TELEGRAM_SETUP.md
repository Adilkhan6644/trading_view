# Telegram Setup Guide

## 1) Create Bot

1. Open Telegram and search `@BotFather`
2. Run `/newbot`
3. Choose bot name and username
4. Copy the bot token

## 2) Get Chat ID

Option A:
- Send a message to your bot, then open:
  - `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
- Find `chat.id`

Option B:
- Use `@userinfobot` for private ID

## 3) Update `.env`

```text
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## 4) Test

Run:

```powershell
python main.py
```

On signal, you should receive formatted Telegram message instantly.

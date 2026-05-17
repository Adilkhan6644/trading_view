# Notifications Without Gmail

Gmail alerts need **2-Step Verification** + an **App Password**. If you cannot enable that, use one of these **free** options instead.

All of them send alerts for **LONG** and **SHORT** signals (entry, stop loss, take profit, indicators).

---

## Recommended: Telegram (easiest on phone)

No Gmail required. Takes about 2 minutes.

### Steps

1. Open Telegram → search **@BotFather**
2. Send `/newbot` and follow prompts
3. Copy the **bot token**
4. Open your new bot and press **Start** (send any message)
5. Open in browser (replace token):
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
6. Copy `"chat":{"id":123456789}` → that is your chat ID

### `.env`

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

EMAIL_ENABLED=false
DISCORD_ENABLED=false
NTFY_ENABLED=false
```

Restart bot: `python main.py`

More detail: `TELEGRAM_SETUP.md`

---

## Option 2: Discord (good for desktop + phone app)

No 2FA requirement. You only need a **webhook URL**.

### Steps

1. Install [Discord](https://discord.com) (free) or use the web app
2. Create a server (or use an existing one)
3. Open a **text channel** → click the **gear** (Edit Channel)
4. Go to **Integrations** → **Webhooks** → **New Webhook**
5. Name it (e.g. `Trading Alerts`) → **Copy Webhook URL**

### `.env`

```env
DISCORD_ENABLED=true
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxxx/yyyy

TELEGRAM_ENABLED=false
EMAIL_ENABLED=false
```

Restart bot: `python main.py`

Alerts appear in that Discord channel instantly.

---

## Option 3: ntfy push (phone notifications, no account)

[ntfy.sh](https://ntfy.sh) sends push notifications to your phone. Pick a **unique topic name** (like a private channel name).

### Steps

1. On your phone, install **ntfy** app:
   - [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   - [iOS](https://apps.apple.com/app/ntfy/id1625396347)
2. Open the app → **Subscribe to topic**
3. Enter a unique topic, e.g. `adilkhan-crypto-alerts-8392` (use your own random name)
4. In `.env` set the **same** topic

### `.env`

```env
NTFY_ENABLED=true
NTFY_TOPIC=adilkhan-crypto-alerts-8392
NTFY_SERVER_URL=https://ntfy.sh

TELEGRAM_ENABLED=false
EMAIL_ENABLED=false
```

Restart bot: `python main.py`

When a LONG/SHORT signal fires, your phone gets a push notification.

---

## Use multiple channels at once

You can enable more than one:

```env
TELEGRAM_ENABLED=true
DISCORD_ENABLED=true
NTFY_ENABLED=true
EMAIL_ENABLED=false
```

---

## If you only run the bot on your PC (no phone app)

Signals are always saved to:

- `logs/bot.log` — text log
- `data/alerts.csv` — spreadsheet-friendly history

You can open `data/alerts.csv` in Excel after each session.

---

## Quick comparison

| Method | Gmail 2FA needed? | Phone alert? | Difficulty |
|--------|-------------------|----------------|------------|
| Telegram | No | Yes | Easy |
| Discord | No | Yes (Discord app) | Easy |
| ntfy | No | Yes | Easy |
| Gmail SMTP | **Yes** | Email | Harder |
| CSV / logs | No | No (manual check) | Easiest |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No Telegram message | `TELEGRAM_ENABLED=true`, message the bot first, correct `CHAT_ID` |
| Discord 404 | Webhook URL copied fully; webhook not deleted in Discord |
| No ntfy push | Same `NTFY_TOPIC` in app and `.env`; phone has internet |
| No alerts at all | Strategy may not match yet; try `SESSION_FILTER_ENABLED=false` temporarily |

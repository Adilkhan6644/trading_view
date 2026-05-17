# API & Credentials Setup Guide

This document lists every **API** and **`.env` credential** the bot uses, what each one is for, whether it is required, and **step-by-step** instructions for where to get it.

---

## Quick overview

| Service | Purpose | Required? |
|--------|---------|-------------|
| **Binance** or **Bybit** | Market data (OHLCV candles) | Yes (pick one exchange) |
| **Telegram Bot API** | Instant alert messages | Optional (`TELEGRAM_ENABLED=true`) |
| **Gmail SMTP** | Email alerts | Optional (`EMAIL_ENABLED=true`) |

The bot is an **alert scanner**. It does **not** place live orders unless you extend it later. For scanning candles, you usually only need **read** access on the exchange API (or even public endpoints in many cases—but API keys are still recommended for rate limits).

---

## Step 0 — Create your `.env` file

1. Open the project folder: `C:\Users\adilk\Desktop\trading`
2. Copy the template:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Edit `.env` in any text editor (VS Code, Notepad, etc.)
4. **Never commit `.env` to Git** — it contains secrets.

---

## Part 1 — Exchange API (Binance or Bybit)

### What the bot uses from the exchange

| Data | API method (via ccxt) | Used for |
|------|----------------------|----------|
| OHLCV candles | `fetch_ohlcv` | Price, volume, indicators, signals |
| Market list | `load_markets` | Valid symbol names |

No TradingView or paid data feed is required.

### `.env` variables (exchange)

| Variable | Example | Required | Description |
|----------|---------|----------|-------------|
| `EXCHANGE_ID` | `binance` or `bybit` | Yes | Which exchange to connect to |
| `MARKET_TYPE` | `futures` or `spot` | Yes | Must match the pairs you scan |
| `API_KEY` | (from exchange) | Recommended | API key string |
| `API_SECRET` | (from exchange) | Recommended | Secret key string |
| `API_PASSWORD` | (Bybit only, sometimes) | Usually empty | Passphrase if your exchange uses one |
| `USE_TESTNET` | `false` or `true` | No | Use sandbox/testnet instead of live |

Other exchange-related settings (no secret):

| Variable | Default | Description |
|----------|---------|-------------|
| `SYMBOLS` | `BTC/USDT,ETH/USDT,SOL/USDT` | Pairs to scan (comma-separated) |
| `TIMEFRAMES` | `1m,3m,5m` | Candle intervals |
| `SCAN_INTERVAL_SECONDS` | `20` | Seconds between full scans |
| `OHLCV_LIMIT` | `250` | Number of candles fetched per request |
| `MAX_CONCURRENT_REQUESTS` | `5` | Parallel API calls cap |
| `RETRY_ATTEMPTS` | `4` | Retries on API failure |
| `RETRY_BACKOFF_SECONDS` | `1.2` | Initial delay between retries |

---

### Option A — Binance (primary)

#### Step-by-step: Binance API key

1. Go to [https://www.binance.com](https://www.binance.com) and log in.
2. Open **Profile** → **API Management**  
   Direct link (may vary by region): [https://www.binance.com/en/my/settings/api-management](https://www.binance.com/en/my/settings/api-management)
3. Complete security verification if prompted.
4. Click **Create API**.
5. Choose a label (e.g. `trading-alert-bot`).
6. Complete 2FA / email verification.
7. Copy and save:
   - **API Key** → put in `.env` as `API_KEY=`
   - **Secret Key** → put in `.env` as `API_SECRET=`  
   (Secret is shown **once** — save it immediately.)

#### Recommended Binance permissions (alert bot only)

For **scanning / alerts only** (no auto-trading):

- Enable: **Read** (or “Enable Reading”)
- Do **not** enable: Withdrawals, Enable Trading (unless you plan to auto-trade later)

Restrict by IP if Binance offers it (optional but safer on a VPS).

#### Binance Futures vs Spot

| Goal | Set in `.env` |
|------|----------------|
| USDT-M Futures (BTC/USDT, etc.) | `MARKET_TYPE=futures` |
| Spot market | `MARKET_TYPE=spot` |

Use symbols that exist on that market (e.g. `BTC/USDT` on futures).

#### Binance testnet (optional)

1. Futures testnet: [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Create testnet API keys from the testnet site (separate from live).
3. In `.env`:
   ```env
   USE_TESTNET=true
   ```
4. Use testnet key/secret in `API_KEY` / `API_SECRET`.

---

### Option B — Bybit (secondary)

#### Step-by-step: Bybit API key

1. Go to [https://www.bybit.com](https://www.bybit.com) and log in.
2. Open **Account & Security** → **API**  
   Or: [https://www.bybit.com/app/user/api-management](https://www.bybit.com/app/user/api-management)
3. Click **Create New Key**.
4. Choose **System-generated API Keys**.
5. Permissions for alert-only use:
   - **Read-Write** is not needed if you only read market data; use **Read-Only** where available.
   - Avoid **Withdraw** and **Transfer** unless required.
6. Optional: bind to your VPS/home IP.
7. Copy:
   - **API Key** → `API_KEY=`
   - **API Secret** → `API_SECRET=`
8. In `.env` set:
   ```env
   EXCHANGE_ID=bybit
   MARKET_TYPE=futures
   ```
   (or `spot` for spot markets)

#### Bybit testnet (optional)

1. [https://testnet.bybit.com](https://testnet.bybit.com)
2. Create API keys on testnet.
3. Set `USE_TESTNET=true` and use testnet credentials.

`API_PASSWORD` is usually **not** needed for Bybit with ccxt; leave blank unless you use a key type that requires a passphrase.

---

### Exchange setup checklist

- [ ] `EXCHANGE_ID` set to `binance` or `bybit`
- [ ] `MARKET_TYPE` matches your pairs (`futures` or `spot`)
- [ ] `API_KEY` and `API_SECRET` filled in
- [ ] `SYMBOLS` use correct format: `BTC/USDT` (not `BTCUSDT`)
- [ ] Keys have at least read/market data access
- [ ] Withdrawals disabled on the API key

---

## Part 2 — Telegram alerts (optional)

### What the bot uses

| Data | Endpoint | Used for |
|------|----------|----------|
| Bot token | Telegram Bot API | Authenticate your bot |
| Chat ID | `sendMessage` | Where alerts are delivered |

### `.env` variables (Telegram)

| Variable | Example | Required when enabled |
|----------|---------|------------------------|
| `TELEGRAM_ENABLED` | `true` | Yes |
| `TELEGRAM_BOT_TOKEN` | `123456:ABC...` | Yes |
| `TELEGRAM_CHAT_ID` | `123456789` or `-100...` | Yes |

---

### Step-by-step: Telegram bot token

1. Open Telegram and search for **@BotFather**.
2. Send: `/newbot`
3. Follow prompts:
   - Bot display name (e.g. `My Crypto Alerts`)
   - Bot username (must end in `bot`, e.g. `my_crypto_alerts_bot`)
4. BotFather replies with a token like:
   ```text
   1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
5. Put it in `.env`:
   ```env
   TELEGRAM_ENABLED=true
   TELEGRAM_BOT_TOKEN=1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

### Step-by-step: Telegram chat ID

**Method 1 — Personal chat (easiest)**

1. Open your new bot in Telegram and press **Start** (send any message).
2. In a browser, open (replace `YOUR_BOT_TOKEN`):
   ```text
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
3. Find JSON like:
   ```json
   "chat":{"id":123456789,...}
   ```
4. Put that number in `.env`:
   ```env
   TELEGRAM_CHAT_ID=123456789
   ```

**Method 2 — Group / channel**

1. Add the bot to the group or channel (as admin for channels).
2. Send a message in that chat.
3. Use the same `getUpdates` URL; group IDs are often **negative** (e.g. `-1001234567890`).

More detail: see `TELEGRAM_SETUP.md` in this project.

---

## Part 3 — Gmail SMTP alerts (optional)

### What the bot uses

| Data | Server | Used for |
|------|--------|----------|
| SMTP login | `smtp.gmail.com:587` | Send alert emails |
| App password | Gmail (not your normal password) | Secure SMTP auth |

### `.env` variables (email)

| Variable | Example | Required when enabled |
|----------|---------|------------------------|
| `EMAIL_ENABLED` | `true` | Yes |
| `EMAIL_SMTP_HOST` | `smtp.gmail.com` | Yes (default is fine) |
| `EMAIL_SMTP_PORT` | `587` | Yes (default is fine) |
| `EMAIL_USERNAME` | `you@gmail.com` | Yes |
| `EMAIL_APP_PASSWORD` | 16-char app password | Yes |
| `EMAIL_FROM` | `you@gmail.com` | Yes |
| `EMAIL_TO` | `you@gmail.com` or another inbox | Yes |

---

### Step-by-step: Gmail app password

1. Use a **Google Account** with Gmail.
2. Enable **2-Step Verification**:  
   [https://myaccount.google.com/security](https://myaccount.google.com/security) → **2-Step Verification** → turn on.
3. Create an **App Password**:  
   [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)  
   - App: **Mail**  
   - Device: **Other** → name it `trading-bot`
4. Google shows a **16-character password** (e.g. `abcd efgh ijkl mnop`).
5. In `.env` (no spaces in the password):
   ```env
   EMAIL_ENABLED=true
   EMAIL_SMTP_HOST=smtp.gmail.com
   EMAIL_SMTP_PORT=587
   EMAIL_USERNAME=your.email@gmail.com
   EMAIL_APP_PASSWORD=abcdefghijklmnop
   EMAIL_FROM=your.email@gmail.com
   EMAIL_TO=your.email@gmail.com
   ```

Do **not** use your normal Gmail password in `EMAIL_APP_PASSWORD`.

More detail: see `GMAIL_SMTP_SETUP.md` in this project.

---

## Part 4 — Strategy & risk (no external API)

These go in `.env` but are **not** secrets — tune them for your strategy.

| Variable | Default | Meaning |
|----------|---------|---------|
| `EMA_FAST` | `8` | Fast EMA period |
| `EMA_MID` | `21` | Mid EMA period |
| `EMA_SLOW` | `55` | Slow EMA / trend filter |
| `ATR_LENGTH` | `14` | ATR period for stop loss |
| `VOLUME_AVG_LENGTH` | `20` | Volume average lookback |
| `MOMENTUM_MIN_PCT` | `0.03` | Min EMA slope % for momentum |
| `COOLDOWN_MINUTES` | `8` | Minutes before same pair/side alerts again |
| `STOP_LOSS_MODE` | `atr` | `atr` or `percent` |
| `STOP_LOSS_ATR_MULTIPLIER` | `1.0` | SL distance in ATR units |
| `STOP_LOSS_PERCENT` | `0.5` | SL % when mode is `percent` |
| `RISK_REWARD_RATIO` | `3.0` | Take profit = 3× risk (1:3) |

---

## Part 5 — Session filter (no external API)

| Variable | Default | Meaning |
|----------|---------|---------|
| `SESSION_FILTER_ENABLED` | `true` | Only scan during listed sessions |
| `SESSIONS` | `LONDON,NEW_YORK` | Active session names (UTC windows in code) |
| `TIMEZONE` | `UTC` | Log/reference timezone label |

Session windows are defined in UTC in the bot (London ~07:00–16:00, New York ~12:00–21:00). Set `SESSION_FILTER_ENABLED=false` to scan 24/7.

---

## Part 6 — Runtime modes (no external API)

| Variable | Values | Meaning |
|----------|--------|---------|
| `MODE` | `live` (default) | Run live scanner loop |
| `MODE` | `backtest` | Run historical backtest once and exit |
| `BACKTEST_ENABLED` | `true` / `false` | Alternative flag to enable backtest |
| `BACKTEST_LOOKBACK_CANDLES` | `1200` | Candles per symbol/timeframe in backtest |
| `PAPER_TRADING_ENABLED` | `false` | Reserved for future paper-trading mode |
| `LOG_LEVEL` | `INFO`, `DEBUG`, etc. | Console/file log verbosity |

---

## Minimum `.env` examples

### Alerts only — Binance + Telegram

```env
EXCHANGE_ID=binance
MARKET_TYPE=futures
API_KEY=your_binance_api_key
API_SECRET=your_binance_api_secret
USE_TESTNET=false

SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT
TIMEFRAMES=1m,3m,5m

TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

EMAIL_ENABLED=false
```

### Binance + Telegram + Gmail

```env
EXCHANGE_ID=binance
MARKET_TYPE=futures
API_KEY=your_binance_api_key
API_SECRET=your_binance_api_secret

TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

EMAIL_ENABLED=true
EMAIL_USERNAME=you@gmail.com
EMAIL_APP_PASSWORD=your_16_char_app_password
EMAIL_FROM=you@gmail.com
EMAIL_TO=you@gmail.com
```

### Bybit only (no alerts — console + CSV only)

```env
EXCHANGE_ID=bybit
MARKET_TYPE=futures
API_KEY=your_bybit_api_key
API_SECRET=your_bybit_api_secret

TELEGRAM_ENABLED=false
EMAIL_ENABLED=false
```

---

## Step-by-step: full implementation order

1. **Install dependencies**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Create `.env`**
   ```powershell
   Copy-Item .env.example .env
   ```

3. **Exchange**
   - Create Binance or Bybit API key (read-only recommended).
   - Paste `API_KEY` and `API_SECRET`.
   - Set `EXCHANGE_ID` and `MARKET_TYPE`.
   - Set `SYMBOLS` and `TIMEFRAMES`.

4. **Telegram** (optional)
   - Create bot via @BotFather → `TELEGRAM_BOT_TOKEN`.
   - Message bot → get `TELEGRAM_CHAT_ID` via `getUpdates`.
   - Set `TELEGRAM_ENABLED=true`.

5. **Gmail** (optional)
   - Enable 2FA → create App Password.
   - Fill `EMAIL_*` variables → `EMAIL_ENABLED=true`.

6. **Run**
   ```powershell
   python main.py
   ```

7. **Verify**
   - Console: `Bot started | exchange=...`
   - File: `logs/bot.log` updating
   - On signal: `data/alerts.csv` row + Telegram/email

---

## Security best practices

- Never share API secret, Telegram token, or Gmail app password.
- Use **read-only** exchange keys for alert-only bots.
- Disable **withdrawal** on API keys.
- Restrict API key to your home/VPS IP when the exchange allows it.
- Keep `.env` out of Git (already in `.gitignore`).
- Rotate keys if they are ever exposed.

---

## Troubleshooting

| Problem | What to check |
|---------|----------------|
| `AuthenticationError` / invalid key | `API_KEY` / `API_SECRET` copied correctly; correct exchange (`EXCHANGE_ID`) |
| Symbol not found | `MARKET_TYPE` matches market; symbol format `BTC/USDT` |
| No Telegram messages | `TELEGRAM_ENABLED=true`; bot started; you messaged the bot first; correct `CHAT_ID` |
| Gmail login failed | Use **app password**, not normal password; 2FA enabled |
| No alerts but bot runs | Strategy filters strict; try `SESSION_FILTER_ENABLED=false` or lower `MOMENTUM_MIN_PCT` |
| Rate limit errors | Increase `SCAN_INTERVAL_SECONDS`; reduce pairs/timeframes; lower `MAX_CONCURRENT_REQUESTS` |

---

## Related docs in this project

| File | Topic |
|------|--------|
| `SETUP_GUIDE.md` | Install and first run |
| `TELEGRAM_SETUP.md` | Telegram-only quick guide |
| `GMAIL_SMTP_SETUP.md` | Gmail-only quick guide |
| `README.md` | Project overview and strategy |
| `.env.example` | Full variable template |

---

## External links (official)

- Binance API management: [https://www.binance.com/en/my/settings/api-management](https://www.binance.com/en/my/settings/api-management)
- Bybit API management: [https://www.bybit.com/app/user/api-management](https://www.bybit.com/app/user/api-management)
- Telegram BotFather: [https://t.me/BotFather](https://t.me/BotFather)
- Google App Passwords: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- ccxt (library used by the bot): [https://docs.ccxt.com](https://docs.ccxt.com)

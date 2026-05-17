# Crypto Trading Alert Bot (Free, API-Driven)

Professional Python crypto scalping alert bot that scans multiple pairs/timeframes and sends instant alerts through Telegram and Gmail, without TradingView paid alerts.

## Highlights

- Exchange APIs only (no TradingView dependency)
- Supports `binance` (primary) and `bybit` (secondary) via `ccxt`
- Triple EMA + VWAP + ATR confluence strategy
- Multi-pair and multi-timeframe scanning (`1m`, `3m`, `5m` default)
- London/New York session filter
- Cooldown system to avoid duplicate signals
- Retry/backoff, error handling, and rate-limit friendly async design
- CSV signal logging for later analysis
- Optional backtesting mode
- Docker ready
- Alerts without Gmail: Telegram, Discord webhook, or ntfy push (`NOTIFICATION_SETUP.md`)

## Strategy Implemented

### Long

Triggers LONG only when all are true:
1. EMA 8 crosses above EMA 21
2. Price above EMA 55
3. Price above VWAP
4. Bullish candle
5. Volume above rolling average
6. EMA 8 slope upward with minimum momentum threshold
7. Cooldown check passed

### Short

Triggers SHORT only when all are true:
1. EMA 8 crosses below EMA 21
2. Price below EMA 55
3. Price below VWAP
4. Bearish candle
5. Volume above rolling average
6. EMA 8 slope downward with minimum momentum threshold
7. Cooldown check passed

### Risk Engine

- Stop loss mode:
  - `atr`: `ATR * STOP_LOSS_ATR_MULTIPLIER`
  - `percent`: `% from entry` via `STOP_LOSS_PERCENT`
- Take profit:
  - `RISK_REWARD_RATIO` (default 1:3)

Alert includes entry, SL, TP, EMA values, VWAP, ATR, symbol, timeframe, and timestamp.

## Project Structure

```text
trading/
├── alerts/
├── config/
├── data/
├── exchange/
├── indicators/
├── logs/
├── strategy/
├── utils/
├── .env.example
├── backtest.py
├── bot.py
├── main.py
├── trading.py
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Quick Start

1. Create and activate virtualenv
2. Install dependencies
3. Copy `.env.example` to `.env`
4. Fill Telegram/Email/API settings
5. Run the **dashboard** (recommended)

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

Open **http://127.0.0.1:8000** — use **Start Live Feed** (WebSocket, no REST polling) or **Evaluate Now**.

Default data feed is **WebSocket** (`DATA_MODE=websocket`). One REST bootstrap per pair, then live stream.

Terminal-only mode: `python main.py cli`

## Configuration Notes

- `EXCHANGE_ID`: `binance` or `bybit`
- `MARKET_TYPE`: `spot` or `futures`
- `SYMBOLS`: comma-separated watchlist
- `TIMEFRAMES`: comma-separated list (ex: `1m,3m,5m`)
- `SESSION_FILTER_ENABLED=true` with `SESSIONS=LONDON,NEW_YORK`
- `MODE=backtest` or `BACKTEST_ENABLED=true` for backtesting

## Backtest

Set one of:

- `MODE=backtest`, or
- `BACKTEST_ENABLED=true`

Then run:

```powershell
python main.py
```

Console outputs trades, wins, losses, win rate, average R, and a Sharpe-like ratio from R-multiples.

## Logs and Data

- Runtime logs: `logs/bot.log`
- Signal CSV: `data/alerts.csv`

## Important Risk Disclaimer

This project is an alert engine, not financial advice. Crypto markets are volatile. Always validate strategy settings before live usage.

## Additional Guides

- `SETUP_GUIDE.md`
- `TELEGRAM_SETUP.md`
- `GMAIL_SMTP_SETUP.md`
- `VPS_DEPLOYMENT.md`

# Setup Guide

## 1) Prerequisites

- Python 3.10+ (recommended 3.11)
- Internet connection
- Exchange API key (Binance or Bybit)
- Telegram bot token (optional)
- Gmail app password (optional)

## 2) Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3) Configure Environment

```powershell
Copy-Item .env.example .env
```

Open `.env` and set:

- Exchange and API details
- Symbols and timeframes
- Strategy and risk values
- Telegram and/or email alert credentials

## 4) Run Bot

```powershell
python main.py
```

## 5) Verify

- Check console for startup log
- Confirm `logs/bot.log` is updating
- Confirm `data/alerts.csv` is created after alerts

## 6) Run Backtest

Set in `.env`:

```text
MODE=backtest
```

Then run:

```powershell
python main.py
```

## Troubleshooting

- If no alerts:
  - Reduce `MOMENTUM_MIN_PCT`
  - Increase watchlist symbols
  - Disable session filter temporarily
- If exchange errors:
  - Check API key permissions
  - Verify symbol format (e.g. `BTC/USDT`)
  - Use lower scan frequency or fewer symbols

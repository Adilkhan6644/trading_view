Risk Management

- Stop loss: 0.5% below entry or 1x ATR (choose by volatility).
- Take profit: target ~1.5% (approx. 1:3 R:R depending on SL choice).
- Position sizing: fixed-risk per trade or percent-of-equity sizing (e.g., risk 0.25% equity per trade).
- Cooldown: apply cooldown per symbol/timeframe to avoid duplicate alerts (default 8 minutes).
- Reject signals if session not open or liquidity low.
- Logging: write all signals to CSV for audit/backtests (`data/alerts.csv`).
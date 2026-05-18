Backtest Notes

- Data range referenced by earlier README: 2021–2025 for intraday evaluation.
- Typical metrics to record: win rate, avg R, max drawdown, trades per period, Sharpe-like ratio on R-multiples.
- Suggested backtest config: OHLCV limit >= 1200, timeframe 1m/3m/5m, no lookahead, candle-close confirmation for entries.
- Use CSV logs to validate live performance vs backtest results.
Filters

- VWAP filter: only trade in direction of VWAP (price > VWAP => bias long; price < VWAP => bias short).
- Session filter: only allow trades during configured high-volume sessions (London, New York).
- Volume filter: require volume > rolling average to avoid low-liquidity noise.
- Momentum filter: require EMA slope or ATR-based minimum momentum to enter.
- Backoff: exponential retry/backoff for API calls (applies at engine level).
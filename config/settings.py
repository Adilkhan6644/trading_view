from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_list(value: str, default: List[str]) -> List[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class Settings:
    exchange_id: str
    market_type: str
    api_key: str
    api_secret: str
    api_password: Optional[str]
    use_testnet: bool
    scan_interval_seconds: int
    ohlcv_limit: int
    max_concurrent_requests: int
    retry_attempts: int
    retry_backoff_seconds: float
    log_level: str
    timezone: str
    symbols: List[str]
    timeframes: List[str]
    session_filter_enabled: bool
    sessions: List[str]
    ema_fast: int
    ema_mid: int
    ema_slow: int
    atr_length: int
    volume_avg_length: int
    momentum_min_pct: float
    cooldown_minutes: int
    stop_loss_mode: str
    stop_loss_atr_multiplier: float
    stop_loss_percent: float
    risk_reward_ratio: float
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str
    email_enabled: bool
    email_smtp_host: str
    email_smtp_port: int
    email_username: str
    email_app_password: str
    email_from: str
    email_to: str
    discord_enabled: bool
    discord_webhook_url: str
    ntfy_enabled: bool
    ntfy_topic: str
    ntfy_server_url: str
    mode: str
    paper_trading_enabled: bool
    backtest_enabled: bool
    backtest_lookback_candles: int
    data_mode: str
    alert_on_candle_close_only: bool
    binance_ws_market: str
    sideways_filter_enabled: bool
    adx_length: int
    adx_trend_min: float
    sideways_ema_spread_max_pct: float


def load_settings() -> Settings:
    load_dotenv(override=False)

    return Settings(
        exchange_id=os.getenv("EXCHANGE_ID", "binance").lower(),
        market_type=os.getenv("MARKET_TYPE", "futures").lower(),
        api_key=os.getenv("API_KEY", ""),
        api_secret=os.getenv("API_SECRET", ""),
        api_password=os.getenv("API_PASSWORD") or None,
        use_testnet=_to_bool(os.getenv("USE_TESTNET"), False),
        scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "20")),
        ohlcv_limit=int(os.getenv("OHLCV_LIMIT", "250")),
        max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "5")),
        retry_attempts=int(os.getenv("RETRY_ATTEMPTS", "4")),
        retry_backoff_seconds=float(os.getenv("RETRY_BACKOFF_SECONDS", "1.2")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        timezone=os.getenv("TIMEZONE", "UTC"),
        symbols=_to_list(os.getenv("SYMBOLS", ""), ["BTC/USDT", "ETH/USDT", "SOL/USDT"]),
        timeframes=_to_list(os.getenv("TIMEFRAMES", ""), ["5m"]),
        session_filter_enabled=_to_bool(os.getenv("SESSION_FILTER_ENABLED"), True),
        sessions=[s.upper() for s in _to_list(os.getenv("SESSIONS", ""), ["LONDON", "NEW_YORK"])],
        ema_fast=int(os.getenv("EMA_FAST", "8")),
        ema_mid=int(os.getenv("EMA_MID", "21")),
        ema_slow=int(os.getenv("EMA_SLOW", "55")),
        atr_length=int(os.getenv("ATR_LENGTH", "14")),
        volume_avg_length=int(os.getenv("VOLUME_AVG_LENGTH", "20")),
        momentum_min_pct=float(os.getenv("MOMENTUM_MIN_PCT", "0.03")),
        cooldown_minutes=int(os.getenv("COOLDOWN_MINUTES", "8")),
        stop_loss_mode=os.getenv("STOP_LOSS_MODE", "atr").lower(),
        stop_loss_atr_multiplier=float(os.getenv("STOP_LOSS_ATR_MULTIPLIER", "1.0")),
        stop_loss_percent=float(os.getenv("STOP_LOSS_PERCENT", "0.5")),
        risk_reward_ratio=float(os.getenv("RISK_REWARD_RATIO", "3.0")),
        telegram_enabled=_to_bool(os.getenv("TELEGRAM_ENABLED"), False),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        email_enabled=_to_bool(os.getenv("EMAIL_ENABLED"), False),
        email_smtp_host=os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
        email_smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "587")),
        email_username=os.getenv("EMAIL_USERNAME", ""),
        email_app_password=os.getenv("EMAIL_APP_PASSWORD", ""),
        email_from=os.getenv("EMAIL_FROM", ""),
        email_to=os.getenv("EMAIL_TO", ""),
        discord_enabled=_to_bool(os.getenv("DISCORD_ENABLED"), False),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
        ntfy_enabled=_to_bool(os.getenv("NTFY_ENABLED"), False),
        ntfy_topic=os.getenv("NTFY_TOPIC", ""),
        ntfy_server_url=os.getenv("NTFY_SERVER_URL", "https://ntfy.sh"),
        mode=os.getenv("MODE", "live").lower(),
        paper_trading_enabled=_to_bool(os.getenv("PAPER_TRADING_ENABLED"), False),
        backtest_enabled=_to_bool(os.getenv("BACKTEST_ENABLED"), False),
        backtest_lookback_candles=int(os.getenv("BACKTEST_LOOKBACK_CANDLES", "1200")),
        data_mode=os.getenv("DATA_MODE", "websocket").lower(),
        alert_on_candle_close_only=_to_bool(os.getenv("ALERT_ON_CANDLE_CLOSE_ONLY"), True),
        binance_ws_market=os.getenv("BINANCE_WS_MARKET", "auto").lower(),
        sideways_filter_enabled=_to_bool(os.getenv("SIDEWAYS_FILTER_ENABLED"), True),
        adx_length=int(os.getenv("ADX_LENGTH", "14")),
        adx_trend_min=float(os.getenv("ADX_TREND_MIN", "22")),
        sideways_ema_spread_max_pct=float(os.getenv("SIDEWAYS_EMA_SPREAD_MAX_PCT", "0.2")),
    )

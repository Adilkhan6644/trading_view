from __future__ import annotations

import asyncio
import logging
from typing import Any, List

import ccxt.async_support as ccxt
import pandas as pd

from config.settings import Settings


class ExchangeClient:
    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        self.exchange = self._build_exchange()

    def _build_exchange(self) -> Any:
        exchange_class = getattr(ccxt, self.settings.exchange_id)
        exchange = exchange_class(
            {
                "apiKey": self.settings.api_key,
                "secret": self.settings.api_secret,
                "password": self.settings.api_password,
                "enableRateLimit": True,
                "options": {"defaultType": self._ccxt_market_type()},
            }
        )

        if self.settings.exchange_id == "binance" and self.settings.use_testnet:
            exchange.set_sandbox_mode(True)
        if self.settings.exchange_id == "bybit" and self.settings.use_testnet:
            exchange.set_sandbox_mode(True)

        return exchange

    def _ccxt_market_type(self) -> str:
        market = self.settings.market_type.lower()
        if market in {"futures", "future"}:
            return "future"
        return market

    def supports_websocket(self) -> bool:
        """True when a live WebSocket feed is available for this exchange."""
        if self.settings.exchange_id == "binance":
            return True
        return self.supports_ccxt_watch()

    def supports_ccxt_watch(self) -> bool:
        has = getattr(self.exchange, "has", {}) or {}
        if has.get("watchOHLCV") is True:
            return True
        return callable(getattr(self.exchange, "watch_ohlcv", None)) and has.get("watchOHLCV") is not False

    async def load_markets(self) -> None:
        await self._retry_async(self.exchange.load_markets)

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        async with self.semaphore:
            rows: List[List[float]] = await self._retry_async(
                self.exchange.fetch_ohlcv, symbol, timeframe, None, limit
            )
            frame = pd.DataFrame(
                rows,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
            return frame

    async def _retry_async(self, func: Any, *args: Any) -> Any:
        delay = self.settings.retry_backoff_seconds
        last_error: Exception | None = None

        for attempt in range(1, self.settings.retry_attempts + 1):
            try:
                return await func(*args)
            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "API call failed (attempt %s/%s): %s",
                    attempt,
                    self.settings.retry_attempts,
                    exc,
                )
                if attempt < self.settings.retry_attempts:
                    await asyncio.sleep(delay)
                    delay *= 2

        raise RuntimeError(f"API call failed after retries: {last_error}") from last_error

    async def close(self) -> None:
        try:
            await self.exchange.close()
        except Exception as exc:
            self.logger.error("Error while closing exchange client: %s", exc)

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, List, Optional

import pandas as pd

from config.settings import Settings
from exchange.binance_kline_ws import BinanceKlineWebSocket
from exchange.candle_store import CandleStore
from exchange.client import ExchangeClient

OnCandleCallback = Callable[[str, str, pd.DataFrame, bool], Awaitable[None]]


class WebSocketFeed:
    """
    Live OHLCV feed via exchange WebSocket.
    Binance: native kline stream (free, no ccxt Pro).
  Other exchanges: ccxt watch_ohlcv when supported.
    """

    def __init__(
        self,
        settings: Settings,
        exchange_client: ExchangeClient,
        logger: logging.Logger,
        store: Optional[CandleStore] = None,
    ) -> None:
        self.settings = settings
        self.exchange_client = exchange_client
        self.logger = logger
        self.store = store or CandleStore()
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._last_ts_ms: dict[str, int] = {}
        self._callback: Optional[OnCandleCallback] = None
        self._binance_ws: Optional[BinanceKlineWebSocket] = None

    @property
    def stream_count(self) -> int:
        return len(self.settings.symbols) * len(self.settings.timeframes)

    @staticmethod
    def is_available(settings: Settings, exchange_client: ExchangeClient) -> bool:
        if settings.exchange_id == "binance":
            return True
        return exchange_client.supports_ccxt_watch()

    async def bootstrap(self) -> None:
        """One REST fetch per pair/timeframe to seed indicator history."""
        self.logger.info("WebSocket bootstrap: loading %s histories (one-time REST)...", self.stream_count)
        tasks = [
            self._bootstrap_pair(symbol, timeframe)
            for symbol in self.settings.symbols
            for timeframe in self.settings.timeframes
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.logger.info("WebSocket bootstrap complete.")

    async def _bootstrap_pair(self, symbol: str, timeframe: str) -> None:
        try:
            frame = await self.exchange_client.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                limit=self.settings.ohlcv_limit,
            )
            self.store.set(symbol, timeframe, frame)
            if len(frame):
                key = self.store.key(symbol, timeframe)
                self._last_ts_ms[key] = int(pd.Timestamp(frame.iloc[-1]["timestamp"]).timestamp() * 1000)
        except Exception as exc:
            self.logger.error("Bootstrap failed %s %s: %s", symbol, timeframe, exc)

    async def start(self, callback: OnCandleCallback) -> None:
        if self._running:
            return

        self._callback = callback
        self._running = True

        if self.settings.exchange_id == "binance":
            self._binance_ws = BinanceKlineWebSocket(
                settings=self.settings,
                store=self.store,
                logger=self.logger,
            )
            await self._binance_ws.start(callback)
            self.logger.info("Binance native WebSocket started | %s streams", self.stream_count)
            return

        if not self.exchange_client.supports_ccxt_watch():
            raise RuntimeError(f"{self.settings.exchange_id} WebSocket is not supported. Use DATA_MODE=rest.")

        for symbol in self.settings.symbols:
            for timeframe in self.settings.timeframes:
                task = asyncio.create_task(
                    self._ccxt_watch_loop(symbol, timeframe),
                    name=f"ws-{symbol}-{timeframe}",
                )
                self._tasks.append(task)

        self.logger.info("ccxt WebSocket started | %s streams", self.stream_count)

    async def _ccxt_watch_loop(self, symbol: str, timeframe: str) -> None:
        key = self.store.key(symbol, timeframe)
        delay = self.settings.retry_backoff_seconds

        while self._running:
            try:
                candles = await self.exchange_client.exchange.watch_ohlcv(symbol, timeframe)
                frame = self._candles_to_frame(candles)
                if frame.empty:
                    continue

                self.store.set(symbol, timeframe, frame)
                curr_ts = int(pd.Timestamp(frame.iloc[-1]["timestamp"]).timestamp() * 1000)
                prev_ts = self._last_ts_ms.get(key)
                is_new_candle = prev_ts is not None and curr_ts != prev_ts
                self._last_ts_ms[key] = curr_ts

                if self._callback:
                    await self._callback(symbol, timeframe, frame, is_new_candle)

                delay = self.settings.retry_backoff_seconds
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.warning("WebSocket %s %s: %s — reconnecting...", symbol, timeframe, exc)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    @staticmethod
    def _candles_to_frame(candles: list) -> pd.DataFrame:
        if not candles:
            return pd.DataFrame()
        frame = pd.DataFrame(
            candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
        return frame

    async def stop(self) -> None:
        self._running = False

        if self._binance_ws:
            await self._binance_ws.stop()
            self._binance_ws = None

        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self.logger.info("WebSocket feed stopped.")

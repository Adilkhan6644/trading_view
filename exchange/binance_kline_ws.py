from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable, List, Optional

import aiohttp
import pandas as pd

from config.settings import Settings
from exchange.candle_store import CandleStore

OnCandleCallback = Callable[[str, str, pd.DataFrame, bool], Awaitable[None]]


class BinanceKlineWebSocket:
    """
    Native Binance kline WebSocket (no ccxt Pro required).
    One combined connection for all symbol/timeframe streams.
    """

    FUTURES_WS = "wss://fstream.binance.com/stream"
    FUTURES_TESTNET_WS = "wss://stream.binancefuture.com/stream"
    SPOT_WS = "wss://stream.binance.com:9443/stream"

    def __init__(
        self,
        settings: Settings,
        store: CandleStore,
        logger: logging.Logger,
    ) -> None:
        self.settings = settings
        self.store = store
        self.logger = logger
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._task: Optional[asyncio.Task] = None
        self._callback: Optional[OnCandleCallback] = None
        self._active_market: str = "futures"

    @property
    def stream_count(self) -> int:
        return len(self.settings.symbols) * len(self.settings.timeframes)

    def _resolve_ws_urls(self) -> List[tuple[str, str]]:
        """Return list of (label, base_url) to try in order."""
        prefer = self.settings.binance_ws_market
        market_type = self.settings.market_type.lower()

        futures_url = self.FUTURES_TESTNET_WS if self.settings.use_testnet else self.FUTURES_WS
        candidates: List[tuple[str, str]] = []

        if prefer == "spot":
            candidates.append(("spot", self.SPOT_WS))
        elif prefer == "futures":
            candidates.append(("futures", futures_url))
        else:
            if market_type in {"futures", "future", "swap"}:
                candidates.append(("futures", futures_url))
            else:
                candidates.append(("spot", self.SPOT_WS))
            if market_type in {"futures", "future", "swap"}:
                candidates.append(("spot", self.SPOT_WS))

        if not candidates:
            candidates.append(("spot", self.SPOT_WS))
        return candidates

    @staticmethod
    def _to_stream_symbol(symbol: str) -> str:
        return symbol.replace("/", "").lower()

    def _stream_names(self) -> List[str]:
        names: List[str] = []
        for symbol in self.settings.symbols:
            base = self._to_stream_symbol(symbol)
            for timeframe in self.settings.timeframes:
                names.append(f"{base}@kline_{timeframe}")
        return names

    @staticmethod
    def _stream_to_pair(stream: str) -> tuple[str, str] | None:
        if "@kline_" not in stream:
            return None
        raw, tf = stream.split("@kline_", 1)
        if raw.upper().endswith("USDT"):
            base = raw.upper()[:-4]
            symbol = f"{base}/USDT"
        else:
            symbol = raw.upper()
        return symbol, tf

    async def start(self, callback: OnCandleCallback) -> None:
        if self._running:
            return
        self._callback = callback
        self._running = True
        self._task = asyncio.create_task(self._run_forever(), name="binance-kline-ws")

    async def _run_forever(self) -> None:
        streams = "/".join(self._stream_names())
        delay = self.settings.retry_backoff_seconds
        url_candidates = self._resolve_ws_urls()

        while self._running:
            connected = False
            for label, base in url_candidates:
                if not self._running:
                    break
                url = f"{base}?streams={streams}"
                try:
                    connected = await self._consume_url(label, url)
                    if connected:
                        delay = self.settings.retry_backoff_seconds
                        break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.logger.warning("Binance WS (%s) failed: %s", label, exc)

            if not connected and self._running:
                self.logger.warning("All Binance WS endpoints failed — retry in %ss", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def _consume_url(self, label: str, url: str) -> bool:
        """Connect and process messages. Returns True if at least one kline was received."""
        self._session = aiohttp.ClientSession()
        received = False
        try:
            async with self._session.ws_connect(url, heartbeat=20) as ws:
                self._ws = ws
                self._active_market = label
                self.logger.info(
                    "Binance WebSocket connected (%s) | streams=%s",
                    label,
                    self.stream_count,
                )

                while self._running:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=25)
                    except asyncio.TimeoutError:
                        self.logger.warning("Binance WS (%s): no data for 25s", label)
                        return received

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        got = await self._handle_message(msg.data)
                        if got:
                            received = True
                    elif msg.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                        break
        finally:
            if self._session:
                await self._session.close()
                self._session = None
            self._ws = None

        if not received and label == "futures":
            self.logger.warning(
                "Futures WebSocket connected but no kline data. "
                "Set BINANCE_WS_MARKET=spot in .env if this persists."
            )
        return received

    async def _handle_message(self, raw: str) -> bool:
        payload = json.loads(raw)
        data = payload.get("data", payload)
        if data.get("e") != "kline":
            return False

        stream = payload.get("stream", "")
        pair = self._stream_to_pair(stream)
        if not pair:
            return False

        symbol, timeframe = pair
        k = data["k"]
        candle_closed = bool(k.get("x", False))

        frame = self.store.get(symbol, timeframe)
        if frame is None or frame.empty:
            return False

        row = {
            "timestamp": pd.to_datetime(int(k["t"]), unit="ms", utc=True),
            "open": float(k["o"]),
            "high": float(k["h"]),
            "low": float(k["l"]),
            "close": float(k["c"]),
            "volume": float(k["v"]),
        }

        last_ts = frame.iloc[-1]["timestamp"]
        new_ts = row["timestamp"]
        is_new_candle = new_ts > last_ts

        if new_ts == last_ts:
            frame.loc[frame.index[-1], ["open", "high", "low", "close", "volume"]] = [
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
            ]
        elif is_new_candle:
            frame = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
            frame = frame.tail(self.settings.ohlcv_limit).reset_index(drop=True)
        else:
            return True

        self.store.set(symbol, timeframe, frame)

        if self._callback:
            await self._callback(symbol, timeframe, frame, candle_closed or is_new_candle)
        return True

    async def stop(self) -> None:
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        if self._session:
            await self._session.close()
            self._session = None

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from alerts.dispatcher import AlertDispatcher
from app.state import BotState
from config.settings import Settings
from exchange.client import ExchangeClient
from exchange.websocket_feed import WebSocketFeed
from strategy.triple_ema_vwap import TripleEMAVWAPStrategy
from utils.csv_logger import CSVTradeLogger
from utils.sessions import session_is_open


class TradingAlertBot:
    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger,
        exchange_client: ExchangeClient,
        strategy: TripleEMAVWAPStrategy,
        alerts: AlertDispatcher,
        csv_logger: CSVTradeLogger,
        state: Optional[BotState] = None,
        ws_feed: Optional[WebSocketFeed] = None,
        strategy_name: str = "default",
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.exchange_client = exchange_client
        self.strategy = strategy
        self.alerts = alerts
        self.csv_logger = csv_logger
        self.state = state
        self.ws_feed = ws_feed
        self.strategy_name = strategy_name
        self._running = False
        self._stop_event = asyncio.Event()

    async def log(self, level: str, message: str) -> None:
        getattr(self.logger, level.lower(), self.logger.info)(message)
        if self.state:
            await self.state.add_log(level, message)

    async def run_websocket_loop(self) -> None:
        """Live mode: WebSocket streams (no REST polling loop)."""
        if not self.ws_feed:
            raise RuntimeError("WebSocket feed is not configured")

        if not WebSocketFeed.is_available(self.settings, self.exchange_client):
            raise RuntimeError(f"WebSocket not available for {self.settings.exchange_id}")

        await self.exchange_client.load_markets()
        self._running = True
        self._stop_event.clear()

        await self.ws_feed.bootstrap()

        if self.state:
            await self.state.update_status(
                running=True,
                mode="auto",
                data_source="websocket",
                ws_streams=self.ws_feed.stream_count,
                ws_connected=True,
                exchange=self.settings.exchange_id,
                symbols=self.settings.symbols,
                timeframes=self.settings.timeframes,
            )

        await self.log(
            "INFO",
            f"WebSocket live feed | exchange={self.settings.exchange_id} | "
            f"streams={self.ws_feed.stream_count} (no REST polling)",
        )

        await self.ws_feed.start(self._on_websocket_candle)

        try:
            await self._stop_event.wait()
        finally:
            await self.ws_feed.stop()
            self._running = False
            if self.state:
                await self.state.update_status(running=False, ws_connected=False)
            await self.log("INFO", "WebSocket live feed stopped.")

    async def _on_websocket_candle(
        self,
        symbol: str,
        timeframe: str,
        frame: pd.DataFrame,
        candle_closed: bool,
    ) -> None:
        session_open = session_is_open(
            self.settings.session_filter_enabled,
            self.settings.sessions,
            self.settings.timezone,
        )
        if self.state:
            await self.state.update_status(session_open=session_open)

        if not session_open:
            return

        await self._process_frame(
            symbol=symbol,
            timeframe=timeframe,
            frame=frame,
            source="websocket",
            live_tick=not candle_closed,
            allow_alerts=candle_closed or not self.settings.alert_on_candle_close_only,
        )

    async def run_auto_loop(self) -> None:
        """Legacy REST polling (use only if DATA_MODE=rest)."""
        await self.exchange_client.load_markets()
        self._running = True
        self._stop_event.clear()

        if self.state:
            await self.state.update_status(
                running=True,
                mode="auto",
                data_source="rest",
                ws_connected=False,
                exchange=self.settings.exchange_id,
                symbols=self.settings.symbols,
                timeframes=self.settings.timeframes,
            )

        await self.log(
            "INFO",
            f"REST polling started | interval={self.settings.scan_interval_seconds}s",
        )

        while self._running and not self._stop_event.is_set():
            try:
                session_open = session_is_open(
                    self.settings.session_filter_enabled,
                    self.settings.sessions,
                    self.settings.timezone,
                )
                if self.state:
                    await self.state.update_status(session_open=session_open)

                if session_open:
                    await self.run_scan_cycle()
                else:
                    await self.log("INFO", "Session filter closed — waiting.")

            except Exception as exc:
                await self.log("ERROR", f"Main loop error: {exc}")
                if self.state:
                    await self.state.update_status(last_error=str(exc))

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.settings.scan_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass

        self._running = False
        if self.state:
            await self.state.update_status(running=False)
        await self.log("INFO", "REST polling stopped.")

    async def run_scan_cycle(self) -> None:
        tasks = [
            self._scan_symbol_timeframe_rest(symbol, timeframe)
            for symbol in self.settings.symbols
            for timeframe in self.settings.timeframes
        ]
        results: List[Optional[Exception]] = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                await self.log("ERROR", f"Scan failed: {result}")

    async def _scan_symbol_timeframe_rest(self, symbol: str, timeframe: str) -> None:
        frame = await self.exchange_client.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=self.settings.ohlcv_limit,
        )
        await self._process_frame(
            symbol=symbol,
            timeframe=timeframe,
            frame=frame,
            source="rest",
            live_tick=False,
            allow_alerts=True,
        )

    async def _process_frame(
        self,
        symbol: str,
        timeframe: str,
        frame: pd.DataFrame,
        source: str,
        live_tick: bool,
        allow_alerts: bool,
    ) -> None:
        snapshot = self.strategy.build_snapshot(symbol=symbol, timeframe=timeframe, df=frame)
        if not snapshot:
            return

        scanned_at = datetime.now(timezone.utc).isoformat()
        signal = None
        if allow_alerts:
            # Check if strategy has 'evaluate' method (for backward compatibility)
            if hasattr(self.strategy, 'evaluate'):
                signal = self.strategy.evaluate(symbol=symbol, timeframe=timeframe, df=frame)
            # Otherwise check if build_snapshot returns signal info (for EMA scalping)
            elif snapshot.get("signal_type"):
                signal = snapshot

        scan_record = {
            **snapshot,
            "scanned_at": scanned_at,
            "source": source,
            "live": live_tick,
            "triggered": signal is not None,
            "signal_type": signal.get("signal_type") if isinstance(signal, dict) else (signal.side if signal else None),
            "strategy": self.strategy_name,
        }

        if self.state:
            if live_tick:
                await self.state.upsert_live_scan(scan_record)
            else:
                await self.state.add_scan(scan_record)

        if live_tick:
            return

        # Build status message
        status_msg = f"[{self.strategy_name.upper()}] [{source.upper()}] {symbol} {timeframe}"
        
        if isinstance(snapshot, dict) and "long_score" in snapshot:
            # TripleEMAVWAP format
            status_msg += (
                f" | price={snapshot['price']:.4f} | "
                f"bias={snapshot['bias']} | LONG {snapshot['long_score']}/6 | SHORT {snapshot['short_score']}/6"
            )
            if snapshot.get("is_sideways"):
                status_msg += f" | SIDEWAYS (ADX {snapshot.get('adx', 0):.1f}) — no signal"
            elif signal:
                signal_type = signal.side if hasattr(signal, 'side') else signal.get("signal_type", "UNKNOWN")
                status_msg += f" | SIGNAL {signal_type}"
            elif snapshot["long_ready"] and snapshot["cooldown_long"]:
                status_msg += " | LONG blocked (cooldown)"
            elif snapshot["short_ready"] and snapshot["cooldown_short"]:
                status_msg += " | SHORT blocked (cooldown)"
        elif isinstance(snapshot, dict) and snapshot.get("signal_type"):
            # EMA Scalping format
            status_msg += (
                f" | price={snapshot.get('price', 0):.4f} | "
                f"signal={snapshot.get('signal_type', 'N/A')} | "
                f"angle={snapshot.get('ema_angle', 0):.1f}°"
            )

        await self.log("INFO", status_msg)

        if not signal:
            return

        # Handle signal
        if isinstance(signal, dict):
            # EMA Scalping signal
            payload = signal.copy()
            payload["scanned_at"] = scanned_at
            payload["source"] = source
            payload["strategy"] = self.strategy_name
            payload["exchange"] = self.settings.exchange_id
            payload["side"] = payload.get("signal_type", "UNKNOWN")
            payload["entry"] = f"{float(payload.get('price', 0)):.6f}"

            atr = float(payload.get("atr", 0) or 0)
            if self.settings.stop_loss_mode == "percent":
                risk_per_unit = float(payload.get("price", 0)) * (self.settings.stop_loss_percent / 100)
            else:
                risk_per_unit = atr * self.settings.stop_loss_atr_multiplier
            risk_per_unit = max(risk_per_unit, 1e-9)
            reward = risk_per_unit * self.settings.risk_reward_ratio

            if payload["side"] in {"BUY", "BB"}:
                payload["stop_loss"] = f"{float(payload.get('price', 0)) - risk_per_unit:.6f}"
                payload["take_profit"] = f"{float(payload.get('price', 0)) + reward:.6f}"
            else:
                payload["stop_loss"] = f"{float(payload.get('price', 0)) + risk_per_unit:.6f}"
                payload["take_profit"] = f"{float(payload.get('price', 0)) - reward:.6f}"

            payload["ema_fast"] = f"{float(payload.get('ema_9', 0)):.6f}"
            payload["ema_mid"] = f"{float(payload.get('ema_15', 0)):.6f}"
            payload["ema_slow"] = f"{float(payload.get('ema_15', 0)):.6f}"
            payload["vwap"] = f"{float(payload.get('price', 0)):.6f}"
            
            await self.log(
                "INFO",
                f"ALERT {payload.get('signal_type', 'UNKNOWN')} {payload['symbol']} {payload['timeframe']} "
                f"price={payload.get('price', 0):.6f}",
            )
        else:
            # TripleEMAVWAP signal
            payload = signal.to_payload(self.settings.exchange_id)
            payload["scanned_at"] = scanned_at
            payload["source"] = source
            payload["strategy"] = self.strategy_name
            
            await self.log(
                "INFO",
                f"ALERT {payload['side']} {payload['symbol']} {payload['timeframe']} "
                f"entry={payload['entry']} sl={payload['stop_loss']} tp={payload['take_profit']}",
            )

        self.csv_logger.log_signal(payload)
        if self.state:
            await self.state.add_strategy_signal(self.strategy_name, payload)
        await self.alerts.send(payload)

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()

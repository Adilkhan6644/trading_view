from __future__ import annotations

import asyncio
import logging
from typing import Optional

from alerts.dispatcher import AlertDispatcher
from app.state import BotState
from bot import TradingAlertBot
from config.settings import Settings
from exchange.client import ExchangeClient
from exchange.websocket_feed import WebSocketFeed
from strategy.triple_ema_vwap import TripleEMAVWAPStrategy
from utils.csv_logger import CSVTradeLogger
from utils.logger import configure_logger
from utils.sessions import session_is_open


class BotEngine:
    """Runs the scanner via WebSocket (default) or REST polling."""

    def __init__(self, settings: Settings, state: BotState) -> None:
        self.settings = settings
        self.state = state
        self.logger = configure_logger(settings.log_level)
        self.exchange_client = ExchangeClient(settings=settings, logger=self.logger)
        self.ws_feed = WebSocketFeed(
            settings=settings,
            exchange_client=self.exchange_client,
            logger=self.logger,
        )
        self.strategy = TripleEMAVWAPStrategy(settings=settings)
        self.alerts = AlertDispatcher(settings=settings, logger=self.logger)
        self.csv_logger = CSVTradeLogger()
        self.bot = TradingAlertBot(
            settings=settings,
            logger=self.logger,
            exchange_client=self.exchange_client,
            strategy=self.strategy,
            alerts=self.alerts,
            csv_logger=self.csv_logger,
            state=state,
            ws_feed=self.ws_feed,
        )
        self._auto_task: Optional[asyncio.Task] = None
        self._mode = "manual"

    @property
    def is_running(self) -> bool:
        return self._auto_task is not None and not self._auto_task.done()

    def _use_websocket(self) -> bool:
        if self.settings.data_mode == "rest":
            return False
        return WebSocketFeed.is_available(self.settings, self.exchange_client)

    async def initialize(self) -> None:
        await self.exchange_client.load_markets()
        session_open = session_is_open(
            self.settings.session_filter_enabled,
            self.settings.sessions,
            self.settings.timezone,
        )
        data_source = "websocket" if self._use_websocket() else "rest"
        await self.state.update_status(
            running=False,
            mode=self._mode,
            session_open=session_open,
            data_source=data_source,
            ws_streams=self.ws_feed.stream_count if data_source == "websocket" else 0,
            ws_connected=False,
            exchange=self.settings.exchange_id,
            symbols=self.settings.symbols,
            timeframes=self.settings.timeframes,
        )
        msg = (
            f"Dashboard ready | data={data_source.upper()} | "
            f"{'WebSocket live streams' if data_source == 'websocket' else 'REST polling'} — "
            "click Start Auto or Scan Now"
        )
        await self.state.add_log("INFO", msg)

    async def start_auto(self) -> None:
        if self.is_running:
            await self.state.add_log("WARNING", "Scanner is already running.")
            return

        self._mode = "auto"
        if self._use_websocket():
            self._auto_task = asyncio.create_task(self.bot.run_websocket_loop())
        else:
            await self.state.add_log(
                "WARNING",
                f"WebSocket not available for {self.settings.exchange_id} — using REST polling.",
            )
            self._auto_task = asyncio.create_task(self.bot.run_auto_loop())

        await self.state.update_status(mode="auto", running=True)

    async def stop(self) -> None:
        self.bot.stop()
        if self.ws_feed:
            await self.ws_feed.stop()
        if self._auto_task:
            try:
                await asyncio.wait_for(self._auto_task, timeout=8)
            except asyncio.TimeoutError:
                self._auto_task.cancel()
            self._auto_task = None
        self._mode = "manual"
        await self.state.update_status(mode="manual", running=False, ws_connected=False)
        await self.state.add_log("INFO", "Scanner stopped.")

    async def manual_scan(self) -> None:
        if self.is_running:
            await self.state.add_log("WARNING", "Stop auto mode before manual scan.")
            return

        self._mode = "manual"
        await self.state.update_status(mode="manual", running=True)

        session_open = session_is_open(
            self.settings.session_filter_enabled,
            self.settings.sessions,
            self.settings.timezone,
        )
        await self.state.update_status(session_open=session_open)

        if not session_open:
            await self.state.add_log("INFO", "Session closed — manual scan skipped.")
            await self.state.update_status(running=False)
            return

        try:
            if not self.exchange_client.exchange.markets:
                await self.exchange_client.load_markets()

            if self._use_websocket() and self.ws_feed.store.keys():
                await self.state.add_log("INFO", "Manual scan using cached WebSocket candle data.")
                for symbol in self.settings.symbols:
                    for timeframe in self.settings.timeframes:
                        frame = self.ws_feed.store.get(symbol, timeframe)
                        if frame is not None:
                            await self.bot._process_frame(
                                symbol=symbol,
                                timeframe=timeframe,
                                frame=frame,
                                source="websocket",
                                live_tick=False,
                                allow_alerts=True,
                            )
            else:
                await self.bot.run_scan_cycle()
        except Exception as exc:
            await self.state.add_log("ERROR", f"Manual scan error: {exc}")
            await self.state.update_status(last_error=str(exc))
        finally:
            await self.state.update_status(running=False)

    async def shutdown(self) -> None:
        await self.stop()
        await self.exchange_client.close()

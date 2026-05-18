from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from alerts.dispatcher import AlertDispatcher
from app.state import BotState
from bot import TradingAlertBot
from config.settings import Settings
from exchange.client import ExchangeClient
from exchange.websocket_feed import WebSocketFeed
from strategy.triple_ema_vwap import TripleEMAVWAPStrategy
from strategy.ema_scalping import EMAScalpingStrategy
from utils.csv_logger import CSVTradeLogger
from utils.logger import configure_logger
from utils.sessions import session_is_open


class BotEngine:
    """Runs the scanner via WebSocket (default) or REST polling with support for multiple strategies."""

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
        
        # Initialize strategies
        self.strategies: Dict[str, TripleEMAVWAPStrategy | EMAScalpingStrategy] = {
            "triple_ema_vwap": TripleEMAVWAPStrategy(settings=settings),
            "ema_scalping": EMAScalpingStrategy(settings=settings),
        }
        
        self.alerts = AlertDispatcher(settings=settings, logger=self.logger)
        self.csv_logger = CSVTradeLogger()
        
        # Create bots for each strategy
        self.bots: Dict[str, TradingAlertBot] = {
            name: TradingAlertBot(
                settings=settings,
                logger=self.logger,
                exchange_client=self.exchange_client,
                strategy=strategy,
                alerts=self.alerts,
                csv_logger=self.csv_logger,
                state=state,
                ws_feed=self.ws_feed,
                strategy_name=name,
            )
            for name, strategy in self.strategies.items()
        }
        
        self._auto_tasks: Dict[str, asyncio.Task] = {}
        self._mode = "manual"
        self._enabled_strategies = {"triple_ema_vwap"}  # Start with first strategy by default

    @property
    def is_running(self) -> bool:
        return any(task is not None and not task.done() for task in self._auto_tasks.values())

    def _use_websocket(self) -> bool:
        if self.settings.data_mode == "rest":
            return False
        return WebSocketFeed.is_available(self.settings, self.exchange_client)

    async def initialize(self) -> None:
        try:
            print("DEBUG: Initializing strategies...")
            # Initialize state for each strategy
            for strategy_name in self.strategies.keys():
                await self.state.initialize_strategy(strategy_name)
            
            print("DEBUG: Loading markets...")
            try:
                await self.exchange_client.load_markets()
            except Exception as exc:
                await self.state.add_log("WARNING", f"Market load skipped during dashboard startup: {exc}")
                print(f"WARNING: market load failed during startup: {exc}")
            
            print("DEBUG: Checking session...")
            session_open = session_is_open(
                self.settings.session_filter_enabled,
                self.settings.sessions,
                self.settings.timezone,
            )
            
            print("DEBUG: Setting up data source...")
            data_source = "websocket" if self._use_websocket() else "rest"
            
            print("DEBUG: Updating status...")
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
                active_strategies=list(self._enabled_strategies),
            )
            
            print("DEBUG: Enabling initial strategies...")
            # Enable initial strategies
            for strategy_name in self._enabled_strategies:
                await self.state.enable_strategy(strategy_name)
            
            msg = (
                f"Dashboard ready | strategies={', '.join(self._enabled_strategies)} | "
                f"data={data_source.upper()} | "
                f"{'WebSocket live streams' if data_source == 'websocket' else 'REST polling'} — "
                "click Start Auto or Scan Now"
            )
            await self.state.add_log("INFO", msg)
            print("DEBUG: Initialization complete!")
        except Exception as e:
            print(f"ERROR during initialization: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def start_auto(self) -> None:
        if self.is_running:
            await self.state.add_log("WARNING", "Scanner is already running.")
            return

        self._mode = "auto"
        
        # Start a task for each enabled strategy
        for strategy_name in self._enabled_strategies:
            bot = self.bots[strategy_name]
            if self._use_websocket():
                task = asyncio.create_task(bot.run_websocket_loop())
            else:
                await self.state.add_log(
                    "WARNING",
                    f"WebSocket not available for {self.settings.exchange_id} — using REST polling.",
                )
                task = asyncio.create_task(bot.run_auto_loop())
            self._auto_tasks[strategy_name] = task

        await self.state.update_status(mode="auto", running=True)

    async def stop(self) -> None:
        # Stop all bots
        for bot in self.bots.values():
            bot.stop()
        
        if self.ws_feed:
            await self.ws_feed.stop()
        
        # Wait for all tasks to finish or timeout
        if self._auto_tasks:
            for strategy_name, task in self._auto_tasks.items():
                if task:
                    try:
                        await asyncio.wait_for(task, timeout=8)
                    except asyncio.TimeoutError:
                        task.cancel()
        
        self._auto_tasks.clear()
        self._mode = "manual"
        await self.state.update_status(mode="manual", running=False, ws_connected=False)
        await self.state.add_log("INFO", "All scanners stopped.")

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

            # Run manual scan for all enabled strategies concurrently
            tasks = []
            for strategy_name in self._enabled_strategies:
                bot = self.bots[strategy_name]
                if self._use_websocket() and self.ws_feed.store.keys():
                    await self.state.add_log(
                        "INFO", 
                        f"[{strategy_name}] Manual scan using cached WebSocket candle data."
                    )
                    for symbol in self.settings.symbols:
                        for timeframe in self.settings.timeframes:
                            frame = self.ws_feed.store.get(symbol, timeframe)
                            if frame is not None:
                                tasks.append(bot._process_frame(
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    frame=frame,
                                    source="websocket",
                                    live_tick=False,
                                    allow_alerts=True,
                                ))
                else:
                    tasks.append(bot.run_scan_cycle())
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as exc:
            await self.state.add_log("ERROR", f"Manual scan error: {exc}")
            await self.state.update_status(last_error=str(exc))
        finally:
            await self.state.update_status(running=False)

    async def toggle_strategy(self, strategy_name: str, enabled: bool) -> None:
        """Enable or disable a specific strategy"""
        if strategy_name not in self.strategies:
            await self.state.add_log("WARNING", f"Strategy '{strategy_name}' not found")
            return
        
        if enabled:
            self._enabled_strategies.add(strategy_name)
            await self.state.enable_strategy(strategy_name)
            await self.state.add_log("INFO", f"Strategy '{strategy_name}' enabled")
        else:
            self._enabled_strategies.discard(strategy_name)
            await self.state.disable_strategy(strategy_name)
            await self.state.add_log("INFO", f"Strategy '{strategy_name}' disabled")
        
        # Update status with active strategies
        await self.state.update_status(active_strategies=list(self._enabled_strategies))

    async def shutdown(self) -> None:
        await self.stop()
        await self.exchange_client.close()

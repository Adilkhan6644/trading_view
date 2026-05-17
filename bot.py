from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from alerts.dispatcher import AlertDispatcher
from config.settings import Settings
from exchange.client import ExchangeClient
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
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.exchange_client = exchange_client
        self.strategy = strategy
        self.alerts = alerts
        self.csv_logger = csv_logger

    async def run(self) -> None:
        await self.exchange_client.load_markets()
        self.logger.info(
            "Bot started | exchange=%s | symbols=%s | timeframes=%s",
            self.settings.exchange_id,
            ",".join(self.settings.symbols),
            ",".join(self.settings.timeframes),
        )

        while True:
            try:
                if not session_is_open(
                    self.settings.session_filter_enabled,
                    self.settings.sessions,
                    self.settings.timezone,
                ):
                    self.logger.debug("Session filter is closed. Waiting for next scan.")
                    await asyncio.sleep(self.settings.scan_interval_seconds)
                    continue

                tasks = [
                    self._scan_symbol_timeframe(symbol, timeframe)
                    for symbol in self.settings.symbols
                    for timeframe in self.settings.timeframes
                ]
                results: List[Optional[Exception]] = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        self.logger.error("Worker task failed: %s", result)
            except Exception as exc:
                self.logger.exception("Main loop error: %s", exc)

            await asyncio.sleep(self.settings.scan_interval_seconds)

    async def _scan_symbol_timeframe(self, symbol: str, timeframe: str) -> None:
        frame = await self.exchange_client.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=self.settings.ohlcv_limit,
        )
        signal = self.strategy.evaluate(symbol=symbol, timeframe=timeframe, df=frame)
        if not signal:
            return

        payload = signal.to_payload(self.settings.exchange_id)
        self.logger.info(
            "Signal %s %s %s entry=%s sl=%s tp=%s",
            payload["side"],
            payload["symbol"],
            payload["timeframe"],
            payload["entry"],
            payload["stop_loss"],
            payload["take_profit"],
        )
        self.csv_logger.log_signal(payload)
        await self.alerts.send(payload)

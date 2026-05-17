from __future__ import annotations

import asyncio

from alerts.dispatcher import AlertDispatcher
from backtest import run_backtest
from bot import TradingAlertBot
from config.settings import load_settings
from exchange.client import ExchangeClient
from strategy.triple_ema_vwap import TripleEMAVWAPStrategy
from utils.csv_logger import CSVTradeLogger
from utils.logger import configure_logger


async def _run() -> None:
    settings = load_settings()
    logger = configure_logger(settings.log_level)

    exchange_client = ExchangeClient(settings=settings, logger=logger)
    strategy = TripleEMAVWAPStrategy(settings=settings)

    try:
        if settings.backtest_enabled or settings.mode == "backtest":
            logger.info("Starting backtest mode...")
            await run_backtest(settings, logger, exchange_client, strategy)
            return

        bot = TradingAlertBot(
            settings=settings,
            logger=logger,
            exchange_client=exchange_client,
            strategy=strategy,
            alerts=AlertDispatcher(settings=settings, logger=logger),
            csv_logger=CSVTradeLogger(),
        )
        await bot.run()
    finally:
        await exchange_client.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

from __future__ import annotations

import asyncio
import os
import sys

from alerts.dispatcher import AlertDispatcher
from backtest import run_backtest
from bot import TradingAlertBot
from config.settings import load_settings
from exchange.client import ExchangeClient
from strategy.triple_ema_vwap import TripleEMAVWAPStrategy
from utils.csv_logger import CSVTradeLogger
from utils.logger import configure_logger


async def _run_cli() -> None:
    """Terminal-only mode (no dashboard)."""
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
        await bot.run_auto_loop()
    finally:
        await exchange_client.close()


def _run_dashboard() -> None:
    import uvicorn

    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT", "8000"))
    print(f"Dashboard: http://{host}:{port}")
    print("API docs: http://{0}:{1}/docs".format(host, port))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1].lower() in {"cli", "bot"}:
        asyncio.run(_run_cli())
        return
    if len(sys.argv) > 1 and sys.argv[1].lower() == "backtest":
        os.environ.setdefault("MODE", "backtest")
        os.environ.setdefault("BACKTEST_ENABLED", "true")
        asyncio.run(_run_cli())
        return
    _run_dashboard()


if __name__ == "__main__":
    main()

from __future__ import annotations

import logging
from pathlib import Path


def configure_logger(level: str = "INFO") -> logging.Logger:
    Path("logs").mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("trading_alert_bot")
    logger.setLevel(level.upper())
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = logging.FileHandler("logs/bot.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger

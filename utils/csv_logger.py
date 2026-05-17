from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict


class CSVTradeLogger:
    def __init__(self, csv_path: str = "data/alerts.csv") -> None:
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_header()

    def _ensure_header(self) -> None:
        if self.csv_path.exists():
            return
        with self.csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "timestamp",
                    "exchange",
                    "symbol",
                    "timeframe",
                    "side",
                    "entry",
                    "stop_loss",
                    "take_profit",
                    "ema_fast",
                    "ema_mid",
                    "ema_slow",
                    "vwap",
                    "atr",
                    "volume",
                ]
            )

    def log_signal(self, payload: Dict[str, str]) -> None:
        with self.csv_path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    payload.get("timestamp", ""),
                    payload.get("exchange", ""),
                    payload.get("symbol", ""),
                    payload.get("timeframe", ""),
                    payload.get("side", ""),
                    payload.get("entry", ""),
                    payload.get("stop_loss", ""),
                    payload.get("take_profit", ""),
                    payload.get("ema_fast", ""),
                    payload.get("ema_mid", ""),
                    payload.get("ema_slow", ""),
                    payload.get("vwap", ""),
                    payload.get("atr", ""),
                    payload.get("volume", ""),
                ]
            )

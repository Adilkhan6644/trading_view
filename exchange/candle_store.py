from __future__ import annotations

from typing import Dict, Optional

import pandas as pd


class CandleStore:
    """In-memory OHLCV buffers keyed by symbol|timeframe."""

    def __init__(self) -> None:
        self._frames: Dict[str, pd.DataFrame] = {}

    @staticmethod
    def key(symbol: str, timeframe: str) -> str:
        return f"{symbol}|{timeframe}"

    def set(self, symbol: str, timeframe: str, frame: pd.DataFrame) -> None:
        self._frames[self.key(symbol, timeframe)] = frame

    def get(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        return self._frames.get(self.key(symbol, timeframe))

    def keys(self) -> list[str]:
        return list(self._frames.keys())

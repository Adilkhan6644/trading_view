from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import pandas as pd

from config.settings import Settings
from indicators.calculations import prepare_indicators


@dataclass(slots=True)
class SignalResult:
    symbol: str
    timeframe: str
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    ema_fast: float
    ema_mid: float
    ema_slow: float
    vwap: float
    atr: float
    volume: float
    timestamp: datetime

    def to_payload(self, exchange: str) -> Dict[str, str]:
        return {
            "exchange": exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "side": self.side,
            "entry": f"{self.entry:.6f}",
            "stop_loss": f"{self.stop_loss:.6f}",
            "take_profit": f"{self.take_profit:.6f}",
            "ema_fast": f"{self.ema_fast:.6f}",
            "ema_mid": f"{self.ema_mid:.6f}",
            "ema_slow": f"{self.ema_slow:.6f}",
            "vwap": f"{self.vwap:.6f}",
            "atr": f"{self.atr:.6f}",
            "volume": f"{self.volume:.2f}",
            "timestamp": self.timestamp.isoformat(),
        }


class TripleEMAVWAPStrategy:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.last_alert_at: Dict[str, datetime] = {}

    def evaluate(self, symbol: str, timeframe: str, df: pd.DataFrame) -> Optional[SignalResult]:
        enriched = prepare_indicators(
            df,
            ema_fast=self.settings.ema_fast,
            ema_mid=self.settings.ema_mid,
            ema_slow=self.settings.ema_slow,
            atr_length=self.settings.atr_length,
            volume_avg_length=self.settings.volume_avg_length,
        )
        if len(enriched) < 3:
            return None

        prev = enriched.iloc[-2]
        curr = enriched.iloc[-1]

        cross_up = prev["ema_fast"] <= prev["ema_mid"] and curr["ema_fast"] > curr["ema_mid"]
        cross_down = prev["ema_fast"] >= prev["ema_mid"] and curr["ema_fast"] < curr["ema_mid"]

        bullish = curr["close"] > curr["open"]
        bearish = curr["close"] < curr["open"]
        high_volume = curr["volume"] > curr["volume_avg"]

        up_momentum = curr["ema_fast_slope_pct"] >= self.settings.momentum_min_pct
        down_momentum = curr["ema_fast_slope_pct"] <= -self.settings.momentum_min_pct

        long_ready = (
            cross_up
            and curr["close"] > curr["ema_slow"]
            and curr["close"] > curr["vwap"]
            and bullish
            and high_volume
            and up_momentum
        )
        short_ready = (
            cross_down
            and curr["close"] < curr["ema_slow"]
            and curr["close"] < curr["vwap"]
            and bearish
            and high_volume
            and down_momentum
        )

        if long_ready:
            side = "LONG"
        elif short_ready:
            side = "SHORT"
        else:
            return None

        if self._is_cooldown(symbol, timeframe, side):
            return None

        entry = float(curr["close"])
        atr = float(curr["atr"])
        stop_loss, take_profit = self._risk_prices(side, entry, atr)

        self.last_alert_at[self._cooldown_key(symbol, timeframe, side)] = datetime.now(timezone.utc)
        return SignalResult(
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            ema_fast=float(curr["ema_fast"]),
            ema_mid=float(curr["ema_mid"]),
            ema_slow=float(curr["ema_slow"]),
            vwap=float(curr["vwap"]),
            atr=atr,
            volume=float(curr["volume"]),
            timestamp=pd.to_datetime(curr["timestamp"]).to_pydatetime(),
        )

    def _risk_prices(self, side: str, entry: float, atr: float) -> tuple[float, float]:
        if self.settings.stop_loss_mode == "percent":
            risk_per_unit = entry * (self.settings.stop_loss_percent / 100)
        else:
            risk_per_unit = atr * self.settings.stop_loss_atr_multiplier

        risk_per_unit = max(risk_per_unit, 1e-9)
        reward = risk_per_unit * self.settings.risk_reward_ratio

        if side == "LONG":
            stop_loss = entry - risk_per_unit
            take_profit = entry + reward
        else:
            stop_loss = entry + risk_per_unit
            take_profit = entry - reward

        return stop_loss, take_profit

    def _cooldown_key(self, symbol: str, timeframe: str, side: str) -> str:
        return f"{symbol}|{timeframe}|{side}"

    def _is_cooldown(self, symbol: str, timeframe: str, side: str) -> bool:
        key = self._cooldown_key(symbol, timeframe, side)
        recent = self.last_alert_at.get(key)
        if recent is None:
            return False

        return datetime.now(timezone.utc) - recent < timedelta(minutes=self.settings.cooldown_minutes)

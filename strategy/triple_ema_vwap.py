from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

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

    def build_snapshot(self, symbol: str, timeframe: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        enriched = prepare_indicators(
            df,
            ema_fast=self.settings.ema_fast,
            ema_mid=self.settings.ema_mid,
            ema_slow=self.settings.ema_slow,
            atr_length=self.settings.atr_length,
            volume_avg_length=self.settings.volume_avg_length,
            adx_length=self.settings.adx_length,
        )
        if len(enriched) < 3:
            return None

        prev = enriched.iloc[-2]
        curr = enriched.iloc[-1]

        cross_up = bool(prev["ema_fast"] <= prev["ema_mid"] and curr["ema_fast"] > curr["ema_mid"])
        cross_down = bool(prev["ema_fast"] >= prev["ema_mid"] and curr["ema_fast"] < curr["ema_mid"])
        bullish = bool(curr["close"] > curr["open"])
        bearish = bool(curr["close"] < curr["open"])
        high_volume = bool(curr["volume"] > curr["volume_avg"])
        up_momentum = bool(curr["ema_fast_slope_pct"] >= self.settings.momentum_min_pct)
        down_momentum = bool(curr["ema_fast_slope_pct"] <= -self.settings.momentum_min_pct)

        long_conditions = {
            "ema_cross_up": cross_up,
            "price_above_ema55": bool(curr["close"] > curr["ema_slow"]),
            "price_above_vwap": bool(curr["close"] > curr["vwap"]),
            "bullish_candle": bullish,
            "volume_above_avg": high_volume,
            "upward_momentum": up_momentum,
        }
        short_conditions = {
            "ema_cross_down": cross_down,
            "price_below_ema55": bool(curr["close"] < curr["ema_slow"]),
            "price_below_vwap": bool(curr["close"] < curr["vwap"]),
            "bearish_candle": bearish,
            "volume_above_avg": high_volume,
            "downward_momentum": down_momentum,
        }

        long_score = sum(long_conditions.values())
        short_score = sum(short_conditions.values())
        long_ready = long_score == len(long_conditions)
        short_ready = short_score == len(short_conditions)

        if long_ready:
            bias = "LONG"
        elif short_ready:
            bias = "SHORT"
        elif long_score >= short_score:
            bias = "LONG_BIAS"
        else:
            bias = "SHORT_BIAS"

        cooldown_long = self._is_cooldown(symbol, timeframe, "LONG")
        cooldown_short = self._is_cooldown(symbol, timeframe, "SHORT")

        is_sideways = self._is_sideways_market(curr)
        if is_sideways:
            bias = "SIDEWAYS"
            long_ready = False
            short_ready = False

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "price": float(curr["close"]),
            "bias": bias,
            "is_sideways": is_sideways,
            "market_regime": "SIDEWAYS" if is_sideways else "TRENDING",
            "adx": float(curr["adx"]),
            "long_score": long_score,
            "short_score": short_score,
            "long_conditions": long_conditions,
            "short_conditions": short_conditions,
            "long_ready": long_ready,
            "short_ready": short_ready,
            "cooldown_long": cooldown_long,
            "cooldown_short": cooldown_short,
            "ema_fast": float(curr["ema_fast"]),
            "ema_mid": float(curr["ema_mid"]),
            "ema_slow": float(curr["ema_slow"]),
            "vwap": float(curr["vwap"]),
            "atr": float(curr["atr"]),
            "volume": float(curr["volume"]),
            "momentum_pct": float(curr["ema_fast_slope_pct"]),
            "candle_time": pd.to_datetime(curr["timestamp"]).isoformat(),
        }

    def _is_sideways_market(self, curr: pd.Series) -> bool:
        if not self.settings.sideways_filter_enabled:
            return False

        adx = float(curr["adx"])
        price = float(curr["close"])
        emas = [float(curr["ema_fast"]), float(curr["ema_mid"]), float(curr["ema_slow"])]
        ema_spread_pct = ((max(emas) - min(emas)) / price) * 100

        low_trend_strength = adx < self.settings.adx_trend_min
        ema_compression = ema_spread_pct < self.settings.sideways_ema_spread_max_pct
        return low_trend_strength or ema_compression

    def evaluate(self, symbol: str, timeframe: str, df: pd.DataFrame) -> Optional[SignalResult]:
        snapshot = self.build_snapshot(symbol, timeframe, df)
        if not snapshot:
            return None

        if snapshot.get("is_sideways"):
            return None

        if snapshot["long_ready"] and not snapshot["cooldown_long"]:
            side = "LONG"
        elif snapshot["short_ready"] and not snapshot["cooldown_short"]:
            side = "SHORT"
        else:
            return None

        entry = snapshot["price"]
        atr = snapshot["atr"]
        stop_loss, take_profit = self._risk_prices(side, entry, atr)

        self.last_alert_at[self._cooldown_key(symbol, timeframe, side)] = datetime.now(timezone.utc)
        return SignalResult(
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            ema_fast=snapshot["ema_fast"],
            ema_mid=snapshot["ema_mid"],
            ema_slow=snapshot["ema_slow"],
            vwap=snapshot["vwap"],
            atr=atr,
            volume=snapshot["volume"],
            timestamp=pd.to_datetime(snapshot["candle_time"]).to_pydatetime(),
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

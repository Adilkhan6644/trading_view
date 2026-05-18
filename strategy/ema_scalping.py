from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pandas as pd

from config.settings import Settings
from indicators.calculations import prepare_indicators, calculate_ema_angle


@dataclass(slots=True)
class ScalpingSignalResult:
    symbol: str
    timeframe: str
    signal_type: str  # BUY, SELL, BB, SS
    price: float
    ema_9: float
    ema_15: float
    ema_angle: float
    atr: float
    timestamp: datetime

    def to_payload(self, exchange: str) -> Dict[str, str]:
        return {
            "strategy": "ema_scalping",
            "exchange": exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "signal_type": self.signal_type,
            "price": f"{self.price:.6f}",
            "ema_9": f"{self.ema_9:.6f}",
            "ema_15": f"{self.ema_15:.6f}",
            "ema_angle": f"{self.ema_angle:.2f}",
            "atr": f"{self.atr:.6f}",
            "timestamp": self.timestamp.isoformat(),
        }


class EMAScalpingStrategy:
    """
    EMA Scalping Strategy for 5-minute timeframe.
    
    Key signals:
    - BUY: EMA9 > EMA15, angle >= 30°, green candle touches EMA
    - SELL: EMA15 > EMA9, angle >= 30°, red candle touches EMA
    - BB: First green candle touching EMA (bullish start)
    - SS: First red candle touching EMA (short start)
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ema_9 = 9
        self.ema_15 = 15
        self.angle_threshold = 30.0  # degrees
        self.last_signal_at: Dict[str, datetime] = {}
        self.first_touch_bb: Dict[str, bool] = {}  # Track first touch for BB signal
        self.first_touch_ss: Dict[str, bool] = {}  # Track first touch for SS signal

    def _cooldown_key(self, symbol: str, timeframe: str, signal_type: str) -> str:
        return f"{symbol}|{timeframe}|{signal_type}"

    def _is_cooldown(self, symbol: str, timeframe: str, signal_type: str) -> bool:
        key = self._cooldown_key(symbol, timeframe, signal_type)
        recent = self.last_signal_at.get(key)
        if recent is None:
            return False
        return datetime.now(timezone.utc) - recent < timedelta(minutes=self.settings.cooldown_minutes)

    def _calculate_candle_pattern(
        self, candle: pd.Series
    ) -> str:
        """
        Identify candle pattern:
        - hammer_bullish: Lower wick > body, small upper wick
        - marubozu_bullish: No wicks or very small
        - strong_bullish: 70%+ of range is body
        - inverted_hammer_bearish: Upper wick > body, small lower wick
        - marubozu_bearish: No wicks or very small
        - strong_bearish: 70%+ of range is body
        - none: Doesn't match patterns
        """
        open_price = candle["open"]
        close_price = candle["close"]
        high_price = candle["high"]
        low_price = candle["low"]

        body = abs(close_price - open_price)
        total_range = high_price - low_price

        if total_range == 0:
            return "none"

        upper_wick = high_price - max(open_price, close_price)
        lower_wick = min(open_price, close_price) - low_price
        wick_ratio = body / total_range if body > 0 else 0

        is_bullish = close_price > open_price
        is_bearish = close_price < open_price

        if is_bullish:
            # Hammer: small upper wick, large lower wick
            if lower_wick >= body * 2 and upper_wick < body * 0.3:
                return "hammer_bullish"
            # Marubozu: almost no wicks
            if upper_wick < body * 0.1 and lower_wick < body * 0.1:
                return "marubozu_bullish"
            # Strong bullish: 70%+ of range is body
            if wick_ratio >= 0.7:
                return "strong_bullish"

        if is_bearish:
            # Inverted hammer: small lower wick, large upper wick
            if upper_wick >= body * 2 and lower_wick < body * 0.3:
                return "inverted_hammer_bearish"
            # Marubozu: almost no wicks
            if upper_wick < body * 0.1 and lower_wick < body * 0.1:
                return "marubozu_bearish"
            # Strong bearish: 70%+ of range is body
            if wick_ratio >= 0.7:
                return "strong_bearish"

        return "none"

    def _candle_touches_ema(self, candle: pd.Series, ema_9: float, ema_15: float) -> bool:
        """Check if candle touches either EMA line"""
        low = candle["low"]
        high = candle["high"]
        return (low <= ema_9 <= high) or (low <= ema_15 <= high)

    def _check_last_3_candles(
        self, df: pd.DataFrame, ema_col: str, color: str
    ) -> bool:
        """
        Check if within last 3 candles, there's a colored candle touching EMA.
        color: 'green' or 'red'
        """
        if len(df) < 3:
            return False

        last_3 = df.iloc[-3:].copy()

        for idx, candle in last_3.iterrows():
            if color == "green":
                is_colored = candle["close"] > candle["open"]
            else:  # red
                is_colored = candle["close"] < candle["open"]

            if not is_colored:
                continue

            ema_val = candle["ema_fast"] if ema_col == "ema_9" else candle["ema_mid"]
            if self._candle_touches_ema(candle, candle["ema_fast"], candle["ema_mid"]):
                return True

        return False

    def _check_first_touch_candle(
        self, df: pd.DataFrame, color: str
    ) -> Optional[pd.Series]:
        """
        Find the FIRST colored candle touching EMA.
        color: 'green' or 'red'
        Returns the candle or None
        """
        if len(df) < 1:
            return None

        for idx in range(len(df) - 1, -1, -1):
            candle = df.iloc[idx]

            if color == "green":
                is_colored = candle["close"] > candle["open"]
            else:  # red
                is_colored = candle["close"] < candle["open"]

            if not is_colored:
                continue

            if self._candle_touches_ema(candle, candle["ema_fast"], candle["ema_mid"]):
                return candle

        return None

    def build_snapshot(
        self, symbol: str, timeframe: str, df: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze candles and generate signals.
        Returns Dict with signal info or None if no signal.
        """
        enriched = prepare_indicators(
            df,
            ema_fast=9,
            ema_mid=15,
            ema_slow=55,
            atr_length=self.settings.atr_length,
            volume_avg_length=self.settings.volume_avg_length,
            adx_length=self.settings.adx_length,
        )

        if len(enriched) < 3:
            return None

        curr = enriched.iloc[-1]
        ema_9 = curr["ema_fast"]
        ema_15 = curr["ema_mid"]

        # Calculate EMA angle
        if len(enriched) >= 5:
            ema_angle_deg = calculate_ema_angle(enriched, ema_col="ema_fast", periods=5)
        else:
            ema_angle_deg = 0

        # Check for BUY signal
        if (
            ema_9 > ema_15
            and ema_angle_deg >= self.angle_threshold
            and self._check_last_3_candles(enriched, "ema_9", "green")
            and float(curr.get("adx", 0)) >= float(self.settings.adx_trend_min)
        ):
            # Verify candle pattern
            for idx in range(len(enriched) - 1, max(len(enriched) - 4, -1), -1):
                candle = enriched.iloc[idx]
                if (
                    candle["close"] > candle["open"]
                    and self._candle_touches_ema(
                        candle, candle["ema_fast"], candle["ema_mid"]
                    )
                ):
                    pattern = self._calculate_candle_pattern(candle)
                    if pattern in [
                        "hammer_bullish",
                        "marubozu_bullish",
                        "strong_bullish",
                    ]:
                        key = self._cooldown_key(symbol, timeframe, "BUY")
                        if self._is_cooldown(symbol, timeframe, "BUY"):
                            return None
                        self.last_signal_at[key] = datetime.now(timezone.utc)
                        return {
                        "strategy_name": "ema_scalping",
                            "timeframe": timeframe,
                            "signal_type": "BUY",
                            "price": curr["close"],
                            "ema_9": ema_9,
                            "ema_15": ema_15,
                            "ema_angle": ema_angle_deg,
                            "atr": curr.get("atr", 0),
                            "candle_pattern": pattern,
                            "timestamp": datetime.now(timezone.utc),
                        }

        # Check for SELL signal
        if (
            ema_15 > ema_9
            and abs(ema_angle_deg) >= self.angle_threshold
            and self._check_last_3_candles(enriched, "ema_15", "red")
            and float(curr.get("adx", 0)) >= float(self.settings.adx_trend_min)
        ):
            # Verify candle pattern
            for idx in range(len(enriched) - 1, max(len(enriched) - 4, -1), -1):
                candle = enriched.iloc[idx]
                if (
                    candle["close"] < candle["open"]
                    and self._candle_touches_ema(
                        candle, candle["ema_fast"], candle["ema_mid"]
                    )
                ):
                    pattern = self._calculate_candle_pattern(candle)
                    if pattern in [
                        "inverted_hammer_bearish",
                        "marubozu_bearish",
                        "strong_bearish",
                    ]:
                        key = self._cooldown_key(symbol, timeframe, "SELL")
                        if self._is_cooldown(symbol, timeframe, "SELL"):
                            return None
                        self.last_signal_at[key] = datetime.now(timezone.utc)
                        return {
                            "strategy_name": "ema_scalping",                            "exchange": "binance",                            "symbol": symbol,
                            "timeframe": timeframe,
                            "signal_type": "SELL",
                            "price": curr["close"],
                            "ema_9": ema_9,
                            "ema_15": ema_15,
                            "ema_angle": abs(ema_angle_deg),
                            "atr": curr.get("atr", 0),
                            "candle_pattern": pattern,
                            "timestamp": datetime.now(timezone.utc),
                        }

        # Check for BB signal (first green candle touching EMA)
        key = f"{symbol}|{timeframe}"
        if ema_9 > ema_15 and ema_angle_deg >= self.angle_threshold:
            touch_candle = self._check_first_touch_candle(enriched, "green")
            if touch_candle is not None and key not in self.first_touch_bb:
                self.first_touch_bb[key] = True
                return {
                    "strategy_name": "ema_scalping",
                    "exchange": "binance",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal_type": "BB",
                    "price": curr["close"],
                    "ema_9": ema_9,
                    "ema_15": ema_15,
                    "ema_angle": ema_angle_deg,
                    "atr": curr.get("atr", 0),
                    "candle_pattern": "first_touch_green",
                    "timestamp": datetime.now(timezone.utc),
                }
            elif ema_9 <= ema_15:
                self.first_touch_bb.pop(key, None)

        # Check for SS signal (first red candle touching EMA)
        if ema_15 > ema_9 and abs(ema_angle_deg) >= self.angle_threshold:
            touch_candle = self._check_first_touch_candle(enriched, "red")
            if touch_candle is not None and key not in self.first_touch_ss:
                self.first_touch_ss[key] = True
                return {
                    "strategy_name": "ema_scalping",
                    "exchange": "binance",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal_type": "SS",
                    "price": curr["close"],
                    "ema_9": ema_9,
                    "ema_15": ema_15,
                    "ema_angle": abs(ema_angle_deg),
                    "atr": curr.get("atr", 0),
                    "candle_pattern": "first_touch_red",
                    "timestamp": datetime.now(timezone.utc),
                }
            elif ema_15 <= ema_9:
                self.first_touch_ss.pop(key, None)

        return None

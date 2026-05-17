from __future__ import annotations

import pandas as pd


def _compute_adx(frame: pd.DataFrame, length: int) -> pd.Series:
    up_move = frame["high"].diff()
    down_move = -frame["low"].diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    prev_close = frame["close"].shift(1)
    tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(alpha=1 / length, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace([pd.NA, float("inf")], 0)
    return dx.ewm(alpha=1 / length, adjust=False).mean()


def prepare_indicators(
    df: pd.DataFrame,
    ema_fast: int,
    ema_mid: int,
    ema_slow: int,
    atr_length: int,
    volume_avg_length: int,
    adx_length: int = 14,
) -> pd.DataFrame:
    frame = df.copy()

    frame["ema_fast"] = frame["close"].ewm(span=ema_fast, adjust=False).mean()
    frame["ema_mid"] = frame["close"].ewm(span=ema_mid, adjust=False).mean()
    frame["ema_slow"] = frame["close"].ewm(span=ema_slow, adjust=False).mean()

    prev_close = frame["close"].shift(1)
    tr_components = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    true_range = tr_components.max(axis=1)
    frame["atr"] = true_range.rolling(window=atr_length).mean()

    tp = (frame["high"] + frame["low"] + frame["close"]) / 3
    cumulative_vp = (tp * frame["volume"]).cumsum()
    cumulative_volume = frame["volume"].cumsum().replace(0, pd.NA)
    frame["vwap"] = cumulative_vp / cumulative_volume

    frame["volume_avg"] = frame["volume"].rolling(window=volume_avg_length).mean()
    frame["ema_fast_slope_pct"] = frame["ema_fast"].pct_change() * 100
    frame["adx"] = _compute_adx(frame, adx_length)

    return frame.dropna().reset_index(drop=True)

from __future__ import annotations

import pandas as pd


def prepare_indicators(
    df: pd.DataFrame,
    ema_fast: int,
    ema_mid: int,
    ema_slow: int,
    atr_length: int,
    volume_avg_length: int,
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

    return frame.dropna().reset_index(drop=True)

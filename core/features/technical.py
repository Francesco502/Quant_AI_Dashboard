"""Technical feature calculations used by v3 feature snapshots."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.rolling(window, min_periods=1).mean()
    avg_loss = losses.rolling(window, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0).clip(0.0, 100.0)


def add_technical_features(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    df = frame.copy()
    if "date" not in df.columns:
        df = df.reset_index().rename(columns={"index": "date"})
    if "ticker" not in df.columns:
        df["ticker"] = ""
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")

    out = []
    for _ticker, group in df.groupby("ticker", sort=False):
        g = group.sort_values("date").copy()
        close = pd.to_numeric(g["close"], errors="coerce")
        g["ma_20"] = close.rolling(20, min_periods=1).mean()
        g["ma_60"] = close.rolling(60, min_periods=1).mean()
        g["return_20d"] = close.pct_change(20).fillna(0.0)
        g["rsi_14"] = _rsi(close, 14)
        g["volatility_20d"] = close.pct_change().rolling(20, min_periods=1).std(ddof=0).fillna(0.0)
        if "volume" in g.columns:
            volume = pd.to_numeric(g["volume"], errors="coerce")
            avg_volume = volume.rolling(20, min_periods=1).mean()
            ratio = volume / avg_volume.replace(0, np.nan)
            g["volume_ratio_20d"] = ratio.fillna(1.0)
        else:
            g["volume_ratio_20d"] = 1.0
        out.append(g)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

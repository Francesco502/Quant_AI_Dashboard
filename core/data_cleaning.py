"""Data cleaning and refresh-check utilities for price/OHLCV data.

Extracted from data_service.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd

from .data_utils import identify_asset_type


def _clean_price_dataframe(df: pd.DataFrame, max_one_day_return: float = 0.30, ffill_limit: int = 5) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        s = out[col].dropna()
        if s.empty:
            continue
        s = s[~s.index.duplicated(keep="first")]
        s = s.sort_index()
        s = s.ffill(limit=ffill_limit).bfill(limit=ffill_limit)
        if len(s) < 2:
            out[col] = s.reindex(out.index)
            continue
        ret = s.pct_change()
        ret = ret.clip(lower=-max_one_day_return, upper=max_one_day_return)
        clean = s.iloc[0] * (1 + ret.fillna(0)).cumprod()
        out[col] = clean.reindex(out.index)
    return _fill_dataframe_within_valid_range(out)


def _fill_dataframe_within_valid_range(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if not out.empty and not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    out = out.sort_index()

    for col in out.columns:
        series = out[col]
        first_valid = series.first_valid_index()
        last_valid = series.last_valid_index()
        if first_valid is None or last_valid is None:
            continue
        filled = series.loc[first_valid:last_valid].ffill().bfill()
        out.loc[first_valid:last_valid, col] = filled
        if first_valid != out.index[0]:
            out.loc[out.index < first_valid, col] = np.nan
        if last_valid != out.index[-1]:
            out.loc[out.index > last_valid, col] = np.nan

    return out


def _latest_series_date(series: pd.Series | None) -> Optional[datetime]:
    if series is None or series.empty:
        return None
    try:
        return pd.to_datetime(series.index.max()).to_pydatetime()
    except Exception:
        return None


def _should_refresh_local_series(
    ticker: str,
    series: pd.Series | None,
    *,
    refresh_stale: bool,
) -> bool:
    if series is None or series.empty:
        return True
    if not refresh_stale:
        return False

    latest_dt = _latest_series_date(series)
    if latest_dt is None:
        return True

    today = datetime.now().date()
    latest_date = latest_dt.date()
    recent = series.dropna().sort_index().tail(2)
    if (
        len(recent) == 2
        and pd.Timestamp(recent.index[-1]).date() == today
        and pd.Timestamp(recent.index[-2]).date() < today
        and abs(float(recent.iloc[-1]) - float(recent.iloc[-2])) < 1e-9
    ):
        return True

    asset_type = identify_asset_type(ticker)
    if asset_type == "fund":
        return latest_date < (today - timedelta(days=1))
    return latest_date < today


def _trim_synthetic_tail(
    local_series: pd.Series | None,
    remote_series: pd.Series | None,
) -> pd.Series | None:
    if local_series is None or local_series.empty or remote_series is None or remote_series.empty:
        return local_series

    remote_last_dt = _latest_series_date(remote_series)
    if remote_last_dt is None:
        return local_series

    trimmed = local_series.sort_index()
    tail = trimmed[trimmed.index > pd.Timestamp(remote_last_dt)]
    if tail.empty:
        return trimmed

    reference = float(remote_series.iloc[-1])
    numeric_tail = pd.to_numeric(tail, errors="coerce").dropna()
    if numeric_tail.empty:
        return trimmed[trimmed.index <= pd.Timestamp(remote_last_dt)]

    if all(abs(float(value) - reference) < 1e-9 for value in numeric_tail.tolist()):
        return trimmed[trimmed.index <= pd.Timestamp(remote_last_dt)]

    return trimmed


def _extract_ohlcv_close_series(df: pd.DataFrame | None) -> pd.Series | None:
    if df is None or df.empty:
        return None

    if "close" in df.columns:
        close = df["close"]
    elif "price" in df.columns:
        close = df["price"]
    else:
        close = df.iloc[:, 0]

    if not isinstance(close.index, pd.DatetimeIndex):
        close.index = pd.to_datetime(close.index)
    return close.sort_index()


def _normalize_ohlcv_from_df(
    df: pd.DataFrame,
    open_candidates: List[str],
    high_candidates: List[str],
    low_candidates: List[str],
    close_candidates: List[str],
    volume_candidates: List[str],
) -> Optional[pd.DataFrame]:
    """Normalize source-specific OHLCV columns to open/high/low/close/volume."""

    cols_lower = {str(c).lower(): c for c in df.columns}

    def pick(candidates: List[str]) -> Optional[str]:
        for name in candidates:
            key = name.lower()
            for lowered, original in cols_lower.items():
                if key in lowered:
                    return original
        return None

    close_col = pick(close_candidates)
    if close_col is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            return None
        close_col = numeric_cols[0]

    open_col = pick(open_candidates) or close_col
    high_col = pick(high_candidates) or close_col
    low_col = pick(low_candidates) or close_col
    volume_col = pick(volume_candidates)

    out = pd.DataFrame(
        {
            "open": df[open_col].astype(float),
            "high": df[high_col].astype(float),
            "low": df[low_col].astype(float),
            "close": df[close_col].astype(float),
        }
    )
    out["volume"] = df[volume_col].astype(float) if volume_col is not None else np.nan

    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    return out.sort_index()


def _should_refresh_local_ohlcv_history(
    ticker: str,
    df: pd.DataFrame | None,
    *,
    refresh_stale: bool,
) -> bool:
    return _should_refresh_local_series(
        ticker,
        _extract_ohlcv_close_series(df),
        refresh_stale=refresh_stale,
    )


def _trim_synthetic_ohlcv_tail(
    local_df: pd.DataFrame | None,
    remote_df: pd.DataFrame | None,
) -> pd.DataFrame | None:
    if local_df is None or local_df.empty or remote_df is None or remote_df.empty:
        return local_df

    trimmed_local = local_df.sort_index()
    trimmed_local = trimmed_local[~trimmed_local.index.duplicated(keep="last")]
    local_close = _extract_ohlcv_close_series(trimmed_local)
    remote_close = _extract_ohlcv_close_series(remote_df)
    trimmed_close = _trim_synthetic_tail(local_close, remote_close)

    if trimmed_close is None or trimmed_close.empty:
        return trimmed_local.iloc[0:0]
    if local_close is not None and len(trimmed_close) == len(local_close):
        return trimmed_local
    return trimmed_local.loc[trimmed_close.index]

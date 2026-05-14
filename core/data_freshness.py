"""Data freshness checks for daily decision workflows."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable

import pandas as pd

from .data_store import load_local_ohlcv_history


def _coerce_last_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def get_price_freshness(ticker: str, *, max_age_days: int = 5, today: date | None = None) -> Dict[str, Any]:
    clean_ticker = ticker.strip().upper()
    check_date = today or date.today()
    source = "local_parquet"

    try:
        history = load_local_ohlcv_history(clean_ticker)
    except Exception as exc:  # noqa: BLE001
        return {
            "ticker": clean_ticker,
            "source": source,
            "status": "error",
            "is_stale": True,
            "should_block": True,
            "last_date": None,
            "age_days": None,
            "message": f"读取本地价格数据失败: {exc}",
        }

    if history is None or history.empty:
        return {
            "ticker": clean_ticker,
            "source": source,
            "status": "missing",
            "is_stale": True,
            "should_block": True,
            "last_date": None,
            "age_days": None,
            "message": "本地没有可用价格数据。",
        }

    last_date = _coerce_last_date(history.index.max())
    if last_date is None:
        return {
            "ticker": clean_ticker,
            "source": source,
            "status": "error",
            "is_stale": True,
            "should_block": True,
            "last_date": None,
            "age_days": None,
            "message": "价格数据日期无法识别。",
        }

    age_days = max(0, (check_date - last_date).days)
    is_stale = age_days > max_age_days
    status = "stale" if is_stale else "fresh"

    return {
        "ticker": clean_ticker,
        "source": source,
        "status": status,
        "is_stale": is_stale,
        "should_block": is_stale,
        "last_date": last_date.isoformat(),
        "age_days": age_days,
        "message": "数据已过期，建议先更新后再扫描、预测或回测。" if is_stale else "数据新鲜度可接受。",
    }


def get_price_freshness_batch(
    tickers: Iterable[str],
    *,
    max_age_days: int = 5,
    today: date | None = None,
) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for ticker in tickers:
        clean_ticker = ticker.strip().upper()
        if not clean_ticker or clean_ticker in result:
            continue
        result[clean_ticker] = get_price_freshness(clean_ticker, max_age_days=max_age_days, today=today)
    return result

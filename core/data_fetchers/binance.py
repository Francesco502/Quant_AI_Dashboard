"""Data fetcher: binance — price and OHLCV loading.

Auto-extracted from data_service.py.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests


from core import data_store
from ..data_utils import get_api_keys
from ..data_cleaning import _clean_price_dataframe

def _fetch_binance_single(
    ticker: str, days: int, base_url: str, limit: int
) -> Optional[pd.Series]:
    """单个标的的 Binance 日线收盘价数据获取（供并发调用）"""

    def to_binance_symbol(t: str) -> Optional[str]:
        if t.endswith("-USD"):
            return t.replace("-USD", "USDT")
        if t.endswith("USDT"):
            return t
        return None

    symbol = to_binance_symbol(ticker)
    if not symbol:
        return None

    params = {"symbol": symbol, "interval": "1d", "limit": limit}
    try:
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        klines = resp.json()
        if not isinstance(klines, list) or len(klines) == 0:
            return None

        dates = [datetime.utcfromtimestamp(k[0] / 1000) for k in klines]
        closes = [float(k[4]) for k in klines]
        series = pd.Series(closes, index=pd.to_datetime(dates), name=ticker)
        series = series.iloc[-days:]
        return series
    except Exception:
        return None


def load_price_data_binance(tickers: List[str], days: int) -> pd.DataFrame:
    """从 Binance 公共 API 获取加密货币日线数据（支持并发请求）"""
    base_url = "https://api.binance.com/api/v3/klines"
    data_dict: Dict[str, pd.Series] = {}

    if not tickers:
        return pd.DataFrame()

    limit = min(max(days * 2, 50), 1000)
    max_workers = min(len(tickers), 2)  # 低配优化

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_binance_single, ticker, days, base_url, limit): ticker
            for ticker in tickers
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            series = fut.result()
            if series is not None and not series.empty:
                data_dict[ticker] = series

    if not data_dict:
        return pd.DataFrame()

    result = pd.DataFrame(data_dict)
    return result.ffill().bfill()


def load_ohlcv_data_binance(tickers: List[str], days: int) -> Dict[str, pd.DataFrame]:
    """从 Binance 公共 API 获取加密货币日线 OHLCV（支持并发请求）"""
    base_url = "https://api.binance.com/api/v3/klines"
    result: Dict[str, pd.DataFrame] = {}

    if not tickers:
        return {}

    limit = min(max(days * 2, 50), 1000)
    max_workers = min(len(tickers), 2)  # 低配优化

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _fetch_binance_ohlcv_single, ticker, days, base_url, limit
            ): ticker
            for ticker in tickers
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            df = fut.result()
            if df is not None and not df.empty:
                result[ticker] = df

    return result


def _fetch_binance_ohlcv_single(
    ticker: str, days: int, base_url: str, limit: int
) -> Optional[pd.DataFrame]:
    """单个标的的 Binance 日线 OHLCV 数据获取（供并发调用）"""

    def to_binance_symbol(t: str) -> Optional[str]:
        if t.endswith("-USD"):
            return t.replace("-USD", "USDT")
        if t.endswith("USDT"):
            return t
        return None

    symbol = to_binance_symbol(ticker)
    if not symbol:
        return None

    params = {"symbol": symbol, "interval": "1d", "limit": limit}
    try:
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        klines = resp.json()
        if not isinstance(klines, list) or len(klines) == 0:
            return None

        # Binance K 线字段含义参见官方文档：[open_time, open, high, low, close, volume, ...]
        dates = [datetime.utcfromtimestamp(k[0] / 1000) for k in klines]
        opens = [float(k[1]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        closes = [float(k[4]) for k in klines]
        volumes = [float(k[5]) for k in klines]

        df = pd.DataFrame(
            {
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            },
            index=pd.to_datetime(dates),
        )
        df = df.sort_index().iloc[-days:]
        return df
    except Exception:
        return None

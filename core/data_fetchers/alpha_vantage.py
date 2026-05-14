"""Data fetcher: alpha_vantage — price and OHLCV loading.

Auto-extracted from data_service.py.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests


from core import data_store
from ..data_utils import get_api_keys
from ..data_cleaning import _clean_price_dataframe, _normalize_ohlcv_from_df

def _fetch_alpha_vantage_single(
    ticker: str, days: int, api_key: str, base_url: str
) -> Optional[pd.Series]:
    """单个标的的 Alpha Vantage 收盘价数据获取（供并发调用）"""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days * 2)

    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": ticker,
        "apikey": api_key,
        "outputsize": "compact",
    }
    try:
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        js = resp.json()
        if "Error Message" in js or "Note" in js:
            return None

        ts_key = next((k for k in js.keys() if "Time Series" in k), None)
        if not ts_key:
            return None

        ts_data = js[ts_key]
        df = pd.DataFrame.from_dict(ts_data, orient="index")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        close_col = None
        for c in df.columns:
            if "adjusted close" in c:
                close_col = c
                break
        if close_col is None:
            for c in df.columns:
                if "close" in c:
                    close_col = c
                    break
        if close_col is None:
            return None

        series = df[close_col].astype(float)
        series = series[series.index.date >= start_date]
        return series
    except Exception:
        return None


def load_price_data_alpha_vantage(
    tickers: List[str], days: int, api_key: str
) -> pd.DataFrame:
    """Alpha Vantage 日线数据封装（支持并发请求以提升多标的数据拉取速度）"""
    base_url = "https://www.alphavantage.co/query"
    data_dict: Dict[str, pd.Series] = {}

    if not tickers:
        return pd.DataFrame()

    max_workers = min(len(tickers), 2)  # 低配优化
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _fetch_alpha_vantage_single, ticker, days, api_key, base_url
            ): ticker
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


def _fetch_alpha_vantage_ohlcv_single(
    ticker: str, days: int, api_key: str, base_url: str
) -> Optional[pd.DataFrame]:
    """单个标的的 Alpha Vantage OHLCV 数据获取（供并发调用）"""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days * 2)

    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": ticker,
        "apikey": api_key,
        "outputsize": "compact",
    }
    try:
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        js = resp.json()
        if "Error Message" in js or "Note" in js:
            return None

        ts_key = next((k for k in js.keys() if "Time Series" in k), None)
        if not ts_key:
            return None

        ts_data = js[ts_key]
        df = pd.DataFrame.from_dict(ts_data, orient="index")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        # Alpha Vantage 列名通常为 '1. open', '2. high', '3. low', '4. close', '5. adjusted close', '6. volume'
        norm = _normalize_ohlcv_from_df(
            df,
            open_candidates=["1. open", "open"],
            high_candidates=["2. high", "high"],
            low_candidates=["3. low", "low"],
            close_candidates=[
                "5. adjusted close",
                "4. close",
                "adjusted close",
                "close",
            ],
            volume_candidates=["6. volume", "volume"],
        )
        if norm is None or norm.empty:
            return None

        norm = norm[norm.index.date >= start_date]
        norm = norm.iloc[-days:]
        return norm
    except Exception:
        return None


def load_ohlcv_data_alpha_vantage(
    tickers: List[str], days: int, api_key: str
) -> Dict[str, pd.DataFrame]:
    """Alpha Vantage 日线 OHLCV 封装（支持并发请求以提升多标的数据拉取速度）"""
    base_url = "https://www.alphavantage.co/query"
    result: Dict[str, pd.DataFrame] = {}

    if not tickers or not api_key:
        return {}

    max_workers = min(len(tickers), 2)  # 低配优化
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _fetch_alpha_vantage_ohlcv_single, ticker, days, api_key, base_url
            ): ticker
            for ticker in tickers
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            df = fut.result()
            if df is not None and not df.empty:
                result[ticker] = df

    return result

"""Data fetcher: yfinance — price and OHLCV loading.

Auto-extracted from data_service.py.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - depends on optional local dependency
    yf = None


from core import data_store
from ..data_utils import get_api_keys
from ..data_cleaning import _clean_price_dataframe

def load_price_data_yfinance(tickers: List[str], days: int) -> pd.DataFrame:
    """从 yfinance 获取数据的简化封装（保留原有重试/兜底逻辑可以后续迁移）"""
    if not tickers or yf is None:
        return pd.DataFrame()

    raw = yf.download(
        tickers,
        period=f"{days}d",
        progress=False,
        auto_adjust=False,
    )
    if raw.empty:
        return pd.DataFrame()

    if "Adj Close" in raw.columns:
        data = raw["Adj Close"]
    elif "Close" in raw.columns:
        data = raw["Close"]
    else:
        return pd.DataFrame()

    return data.ffill().bfill()


def load_ohlcv_data_yfinance(tickers: List[str], days: int) -> Dict[str, pd.DataFrame]:
    """
    使用 yfinance 获取多资产的 OHLCV 数据

    返回:
        {ticker: DataFrame(index=日期, columns=[open, high, low, close, volume])}
    """
    if not tickers or yf is None:
        return {}

    raw = yf.download(
        tickers,
        period=f"{days}d",
        progress=False,
        auto_adjust=False,
        group_by="column",
    )
    if raw is None or raw.empty:
        return {}

    result: Dict[str, pd.DataFrame] = {}

    # yfinance MultiIndex 结构：第一层为字段(Open/High/...), 第二层为 ticker
    if isinstance(raw.columns, pd.MultiIndex):
        for t in tickers:
            frames: Dict[str, pd.Series] = {}
            for field, new_name in [
                ("Open", "open"),
                ("High", "high"),
                ("Low", "low"),
                ("Close", "close"),
                ("Volume", "volume"),
            ]:
                try:
                    if field in raw.columns.get_level_values(0):
                        s = raw[field][t].dropna()
                        if not s.empty:
                            frames[new_name] = s
                except Exception:
                    continue
            if frames:
                df = pd.DataFrame(frames)
                df.index = pd.to_datetime(df.index)
                df = df.sort_index().iloc[-days:]
                result[t] = df
    else:
        # 单 ticker 情况：列为单层 Open/High/Low/Close/Volume
        frames: Dict[str, pd.Series] = {}
        for field, new_name in [
            ("Open", "open"),
            ("High", "high"),
            ("Low", "low"),
            ("Close", "close"),
            ("Volume", "volume"),
        ]:
            if field in raw.columns:
                s = raw[field].dropna()
                if not s.empty:
                    frames[new_name] = s
        if frames:
            df = pd.DataFrame(frames)
            df.index = pd.to_datetime(df.index)
            df = df.sort_index().iloc[-days:]
            # 当 tickers 只有一个时，使用第一个代码作为键
            result[tickers[0]] = df

    return result

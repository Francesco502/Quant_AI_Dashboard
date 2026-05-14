"""Data fetcher: hk_index — price and OHLCV loading.

Auto-extracted from data_service.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import akshare as ak

    AKSHARE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional local dependency
    ak = None
    AKSHARE_AVAILABLE = False


from core import data_store
from ..data_utils import get_api_keys
from ..data_cleaning import _clean_price_dataframe

def load_price_data_hk_index_akshare(tickers: List[str], days: int) -> pd.DataFrame:
    """使用 AkShare 获取港股指数数据（当前主要支持 HSI 恒生指数）"""
    if not AKSHARE_AVAILABLE:
        raise ImportError("AkShare未安装，无法获取港股指数数据")

    data_dict: Dict[str, pd.Series] = {}
    end_date_str = datetime.now().strftime("%Y%m%d")
    start_date_str = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

    for ticker in tickers:
        code = ticker.upper()
        try:
            if code == "HSI":
                try:
                    temp_df = ak.stock_hk_hist(
                        symbol="HSI",
                        period="daily",
                        start_date=start_date_str,
                        end_date=end_date_str,
                        adjust="",
                    )
                except Exception:
                    temp_df = pd.DataFrame()
            else:
                temp_df = pd.DataFrame()

            if temp_df is None or temp_df.empty:
                continue

            df = temp_df.copy()
            date_col = None
            for c in df.columns:
                if "日期" in str(c) or "date" in str(c).lower():
                    date_col = c
                    break
            if date_col is None:
                df.index = pd.to_datetime(df.index)
            else:
                df[date_col] = pd.to_datetime(df[date_col])
                df = df.set_index(date_col)

            price_col = None
            for c in df.columns:
                if "收盘" in str(c) or "close" in str(c).lower():
                    price_col = c
                    break
            if price_col is None:
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    price_col = numeric_cols[0]

            if price_col is None:
                continue

            series = df[price_col].astype(float)
            series = series.iloc[-days:]
            data_dict[ticker] = series
        except Exception:
            continue

    if not data_dict:
        return pd.DataFrame()

    result = pd.DataFrame(data_dict)
    return result.ffill().bfill()

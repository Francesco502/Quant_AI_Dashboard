"""Data fetcher: tushare — price and OHLCV loading.

Auto-extracted from data_service.py.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import tushare as ts  # type: ignore[import]

    TUSHARE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional local dependency
    ts = None
    TUSHARE_AVAILABLE = False

from core import data_store, tushare_provider
from ..data_utils import get_api_keys
from ..data_cleaning import _clean_price_dataframe, _normalize_ohlcv_from_df


def _resolve_tushare_runtime():
    """Resolve Tushare globals, honoring data_service monkeypatches in tests."""

    parent = sys.modules.get("core.data_service")
    available = TUSHARE_AVAILABLE
    module = ts
    if parent is not None:
        available = bool(getattr(parent, "TUSHARE_AVAILABLE", available))
        module = getattr(parent, "ts", module)
    return available, module

def load_price_data_tushare(
    tickers: List[str],
    days: int,
    tushare_token: str,
) -> pd.DataFrame:
    """使用 Tushare Pro 获取 A股/基金等日线数据

    仅对带 .SZ/.SS 后缀的中国资产生效；其他代码类型仍由 AkShare 等数据源处理。
    """
    tushare_available, tushare_module = _resolve_tushare_runtime()
    if not tushare_available or tushare_module is None:
        raise ImportError("Tushare 未安装，请运行: pip install tushare")
    if not tushare_token:
        raise ValueError("未提供 Tushare Token")

    tushare_module.set_token(tushare_token)
    pro = tushare_module.pro_api()

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days * 2)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    data_dict: Dict[str, pd.Series] = {}

    for ticker in tickers:
        ts_code = tushare_provider.normalize_cn_ticker(ticker)
        if ts_code is None:
            # 非中国市场代码暂不由 Tushare 处理
            continue

        df = pd.DataFrame()
        try:
            # 优先尝试股票日线
            daily = pro.daily(ts_code=ts_code, start_date=start_str, end_date=end_str)
            if daily is not None and not daily.empty:
                daily["trade_date"] = pd.to_datetime(daily["trade_date"])
                daily = daily.sort_values("trade_date").set_index("trade_date")
                series = daily["close"].astype(float)
                data_dict[ticker] = series.tail(days)
                continue
        except Exception:
            pass

        # 若股票接口无数据，尝试基金日线
        try:
            fund_daily = pro.fund_daily(
                ts_code=ts_code, start_date=start_str, end_date=end_str
            )
            if fund_daily is not None and not fund_daily.empty:
                fund_daily["trade_date"] = pd.to_datetime(fund_daily["trade_date"])
                fund_daily = fund_daily.sort_values("trade_date").set_index(
                    "trade_date"
                )
                # fund_daily close 字段名通常为 'close'
                if "close" in fund_daily.columns:
                    series = fund_daily["close"].astype(float)
                    data_dict[ticker] = series.tail(days)
        except Exception:
            continue

    if not data_dict:
        return pd.DataFrame()

    result = pd.DataFrame(data_dict)
    return result.ffill().bfill()


def load_ohlcv_data_tushare(
    tickers: List[str],
    days: int,
    tushare_token: str,
) -> Dict[str, pd.DataFrame]:
    """使用 Tushare Pro 获取 A 股/基金日线 OHLCV"""
    tushare_available, tushare_module = _resolve_tushare_runtime()
    if not tushare_available or tushare_module is None or not tushare_token:
        return {}

    tushare_module.set_token(tushare_token)
    pro = tushare_module.pro_api()

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days * 2)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    result: Dict[str, pd.DataFrame] = {}

    for ticker in tickers:
        ts_code = tushare_provider.normalize_cn_ticker(ticker)
        if ts_code is None:
            # 非中国市场标的暂不由 Tushare 处理
            continue

        try:
            daily = pro.daily(ts_code=ts_code, start_date=start_str, end_date=end_str)
            if daily is not None and not daily.empty:
                daily["trade_date"] = pd.to_datetime(daily["trade_date"])
                daily = daily.sort_values("trade_date").set_index("trade_date")
                norm = _normalize_ohlcv_from_df(
                    daily,
                    open_candidates=["open"],
                    high_candidates=["high"],
                    low_candidates=["low"],
                    close_candidates=["close"],
                    volume_candidates=["vol", "volume"],
                )
                if norm is not None and not norm.empty:
                    norm = norm.iloc[-days:]
                    result[ticker] = norm
                    continue
        except Exception:
            pass

        # 若股票接口没有可用数据，可以视需要补充 fund_daily 等，这里暂默认跳过

    return result

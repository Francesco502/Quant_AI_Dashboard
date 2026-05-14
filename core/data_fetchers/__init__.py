"""Data fetcher subpackage — per-source price and OHLCV loaders.

Re-exports the remote loader orchestration functions for use by data_service.py.
"""

from __future__ import annotations

# Per-source loaders
from .akshare import load_ohlcv_data_akshare, load_price_data_akshare, load_cn_realtime_quotes_sina
from .alpha_vantage import load_ohlcv_data_alpha_vantage, load_price_data_alpha_vantage
from .binance import load_ohlcv_data_binance, load_price_data_binance
from .hk_index import load_price_data_hk_index_akshare
from .tushare import load_ohlcv_data_tushare, load_price_data_tushare
from .yfinance import load_ohlcv_data_yfinance, load_price_data_yfinance

__all__ = [
    "load_price_data_akshare",
    "load_price_data_tushare",
    "load_price_data_yfinance",
    "load_price_data_alpha_vantage",
    "load_price_data_binance",
    "load_price_data_hk_index_akshare",
    "load_ohlcv_data_akshare",
    "load_ohlcv_data_tushare",
    "load_ohlcv_data_yfinance",
    "load_ohlcv_data_alpha_vantage",
    "load_ohlcv_data_binance",
    "load_cn_realtime_quotes_sina",
]

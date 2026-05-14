"""Data source utilities and asset type identification.

Extracted from data_service.py to keep the main module focused on orchestration.
"""

from __future__ import annotations

import os
from math import ceil
from typing import Dict, List

from .asset_metadata import get_asset_hint, resolve_asset_type

DEFAULT_DATA_SOURCE_ORDER = ["Tushare", "AkShare", "AlphaVantage", "Binance", "yfinance"]


def _merge_data_sources(preferred: List[str]) -> List[str]:
    merged: List[str] = []
    for source in preferred:
        if source in DEFAULT_DATA_SOURCE_ORDER and source not in merged:
            merged.append(source)
    for source in DEFAULT_DATA_SOURCE_ORDER:
        if source not in merged:
            merged.append(source)
    return merged


def _env_enabled_sources() -> List[str]:
    api_keys = get_api_keys()
    enabled: List[str] = []
    if api_keys.get("TUSHARE_TOKEN"):
        enabled.append("Tushare")
    enabled.append("AkShare")
    if api_keys.get("ALPHA_VANTAGE_KEY"):
        enabled.append("AlphaVantage")
    enabled.extend(["Binance", "yfinance"])
    return _merge_data_sources(enabled)


def _estimate_quality_min_points(days: int) -> int:
    safe_days = max(1, int(days or 1))
    estimated_trading_points = ceil(safe_days * 0.55) - 1
    return min(30, max(1, estimated_trading_points))


def identify_asset_type(ticker: str) -> str:
    ticker = ticker.upper()
    hint = get_asset_hint(ticker)
    hinted_type = hint.get("asset_type") if hint else None
    hinted_name = hint.get("name") if hint else None

    if ticker.endswith(".OF"):
        return "fund"
    if ticker in ["AU99.99", "AU99.95", "AG(T+D)", "AU(T+D)"]:
        return "gold"
    if ticker.endswith("USDT"):
        return "crypto"
    if ticker.isalpha() and len(ticker) <= 5 and not ticker.startswith("SH") and not ticker.startswith("SZ"):
        return "us_stock"

    resolved = resolve_asset_type(ticker, asset_name=hinted_name, asset_type=hinted_type)
    if resolved in {"fund", "etf", "stock"}:
        return resolved

    if ticker.isdigit() and len(ticker) == 6:
        if ticker.startswith(("00", "30", "60", "68")):
            return "stock"
        if ticker.startswith(("51", "15")):
            return "etf"
        if ticker.startswith(("11", "12")):
            return "bond"
        return "stock"

    return "stock"


def get_active_data_sources() -> List[str]:
    return _env_enabled_sources()


def get_api_key_status() -> Dict[str, bool]:
    api_keys = get_api_keys()
    return {
        "Tushare": bool(api_keys.get("TUSHARE_TOKEN")),
        "AlphaVantage": bool(api_keys.get("ALPHA_VANTAGE_KEY")),
    }


def get_api_keys() -> Dict[str, str]:
    api_keys: Dict[str, str] = {}
    if os.getenv("ALPHA_VANTAGE_KEY"):
        api_keys["ALPHA_VANTAGE_KEY"] = os.getenv("ALPHA_VANTAGE_KEY")
    if os.getenv("TUSHARE_TOKEN"):
        api_keys["TUSHARE_TOKEN"] = os.getenv("TUSHARE_TOKEN")
    return api_keys

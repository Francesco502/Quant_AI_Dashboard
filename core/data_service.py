"""统一数据服务模块

职责：
- 封装 AkShare / yfinance / AlphaVantage / Binance 等多源价格数据获取逻辑；
- 对外提供一个统一的 `load_price_data` 接口，方便在 app.py 中调用；
- 后续可以在这里加入本地缓存、持久化等功能，而不影响上层调用。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import ceil
from typing import List, Dict, Optional, Tuple
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


try:
    import akshare as ak

    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    ak = None

try:
    import tushare as ts

    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None

import yfinance as yf

from . import data_store, tushare_provider
from .asset_metadata import get_asset_hint, resolve_asset_type
from .error_handler import handle_error, create_data_error, create_network_error
from .data_quality import DataQualityChecker, validate_data_before_analysis

# Extracted sub-modules — keep data_service focused on orchestration
from .data_utils import (
    DEFAULT_DATA_SOURCE_ORDER,
    _env_enabled_sources,
    _estimate_quality_min_points,
    _merge_data_sources,
    get_active_data_sources,
    get_api_key_status,
    get_api_keys,
    identify_asset_type,
)
from .data_cleaning import (
    _clean_price_dataframe,
    _extract_ohlcv_close_series,
    _fill_dataframe_within_valid_range,
    _latest_series_date,
    _should_refresh_local_ohlcv_history,
    _should_refresh_local_series,
    _trim_synthetic_ohlcv_tail,
    _trim_synthetic_tail,
)
from .data_fetchers import (
    load_cn_realtime_quotes_sina,
    load_ohlcv_data_akshare,
    load_ohlcv_data_alpha_vantage,
    load_ohlcv_data_binance,
    load_ohlcv_data_tushare,
    load_ohlcv_data_yfinance,
    load_price_data_akshare,
    load_price_data_alpha_vantage,
    load_price_data_binance,
    load_price_data_hk_index_akshare,
    load_price_data_tushare,
    load_price_data_yfinance,
)


DATA_DIR = Path("data")
USER_STATE_FILE = DATA_DIR / "user_state.json"
DEFAULT_DATA_SOURCE_ORDER = ["Tushare", "AkShare", "AlphaVantage", "Binance", "yfinance"]


# ================================================================
#  收盘价级别的历史代码（兼容旧逻辑）
# ================================================================


# ================================================================
#  新增：各数据源的 OHLCV 提取函数
# ================================================================


# ================================================================
#  统一远程 OHLCV 加载（为战法/形态策略和未来系统做准备）
# ================================================================


def _load_ohlcv_data_remote(
    tickers: List[str],
    days: int,
    data_sources: List[str] | None = None,
    alpha_vantage_key: str | None = None,
    tushare_token: str | None = None,
) -> Dict[str, pd.DataFrame]:
    """
    仅从远程数据源加载 OHLCV（不访问本地缓存），返回 {ticker: OHLCV DataFrame}

    默认数据源优先级（可通过 data_sources 覆盖）：
    AkShare -> Tushare -> Binance -> AlphaVantage -> yfinance
    """
    if not tickers:
        return {}

    if data_sources is None:
        data_sources = get_active_data_sources()

    use_akshare = "AkShare" in data_sources and AKSHARE_AVAILABLE
    use_tushare = "Tushare" in data_sources and TUSHARE_AVAILABLE and bool(
        tushare_token
    )
    use_binance = "Binance" in data_sources
    use_alpha = "AlphaVantage" in data_sources and bool(alpha_vantage_key)
    use_yfinance = "yfinance" in data_sources

    remaining = set(tickers)
    result: Dict[str, pd.DataFrame] = {}

    # 1) AkShare：A股/ETF/基金/部分美股
    if remaining and use_akshare:
        try:
            ak_data = load_ohlcv_data_akshare(list(remaining), days)
            for t, df in ak_data.items():
                if t in remaining and df is not None and not df.empty:
                    result[t] = df
                    remaining.discard(t)
        except Exception:
            pass

    # 2) Tushare：A股
    if remaining and use_tushare:
        try:
            ts_data = load_ohlcv_data_tushare(
                [t for t in remaining], days, tushare_token=tushare_token  # type: ignore[arg-type]
            )
            for t, df in ts_data.items():
                if t in remaining and df is not None and not df.empty:
                    result[t] = df
                    remaining.discard(t)
        except Exception:
            pass

    # 3) Binance：加密货币
    if remaining and use_binance:
        try:
            bn_data = load_ohlcv_data_binance(list(remaining), days)
            for t, df in bn_data.items():
                if t in remaining and df is not None and not df.empty:
                    result[t] = df
                    remaining.discard(t)
        except Exception:
            pass

    # 4) AlphaVantage：美股/外汇等
    if remaining and use_alpha and alpha_vantage_key:
        try:
            av_data = load_ohlcv_data_alpha_vantage(
                list(remaining), days, api_key=alpha_vantage_key
            )
            for t, df in av_data.items():
                if t in remaining and df is not None and not df.empty:
                    result[t] = df
                    remaining.discard(t)
        except Exception:
            pass

    # 5) yfinance：兜底
    if remaining and use_yfinance:
        try:
            yf_data = load_ohlcv_data_yfinance(list(remaining), days)
            for t, df in yf_data.items():
                if t in remaining and df is not None and not df.empty:
                    result[t] = df
                    remaining.discard(t)
        except Exception:
            pass

    return result


# ================================================================
#  收盘价级别：统一远程加载 + 本地缓存（旧接口）
# ================================================================


def _load_price_data_remote(
    tickers: List[str],
    days: int,
    data_sources: List[str] | None = None,
    alpha_vantage_key: str | None = None,
    tushare_token: str | None = None,
) -> pd.DataFrame:
    """仅从远程数据源加载数据，不访问本地缓存"""
    if data_sources is None:
        data_sources = get_active_data_sources()

    use_akshare = "AkShare" in data_sources and AKSHARE_AVAILABLE
    use_tushare = "Tushare" in data_sources and TUSHARE_AVAILABLE and bool(
        tushare_token
    )
    use_yfinance = "yfinance" in data_sources
    use_binance = "Binance" in data_sources
    use_alpha = "AlphaVantage" in data_sources and bool(alpha_vantage_key)

    known_us_stocks = {
        "AAPL",
        "TSLA",
        "NVDA",
        "MSFT",
        "GOOGL",
        "AMZN",
        "META",
        "NFLX",
        "AMD",
        "INTC",
        "BABA",
        "JD",
    }

    chinese_tickers = [
        t for t in tickers if ".SZ" in t or ".SS" in t or (t.isdigit() and len(t) == 6)
    ]
    chinese_fund_tickers = [t for t in chinese_tickers if identify_asset_type(t) == "fund"]
    chinese_market_tickers = [t for t in chinese_tickers if t not in chinese_fund_tickers]
    hk_index_tickers = [t for t in tickers if t.upper() in {"HSI"}]
    us_stock_tickers = [
        t
        for t in tickers
        if t.upper() in known_us_stocks and t not in chinese_tickers and t not in hk_index_tickers
    ]
    crypto_tickers = [
        t
        for t in tickers
        if t not in chinese_tickers and t not in us_stock_tickers and t not in hk_index_tickers
    ]

    data_frames: List[pd.DataFrame] = []

    if chinese_tickers:
        chinese_data = pd.DataFrame()
        used_tickers: List[str] = []

        # 优先尝试 Tushare（如果启用且配置了 token）
        if chinese_market_tickers and use_tushare:
            try:
                ts_data = load_price_data_tushare(
                    chinese_market_tickers, days, tushare_token=tushare_token  # type: ignore[arg-type]
                )
                if not ts_data.empty:
                    chinese_data = ts_data.copy()
                    used_tickers.extend(list(ts_data.columns))
            except Exception:
                pass

        # 场外基金直接走 AkShare；其余对 Tushare 未覆盖的中国标的再回退到 AkShare
        remaining = [t for t in chinese_market_tickers if t not in used_tickers] + chinese_fund_tickers
        if remaining and use_akshare:
            try:
                ak_data = load_price_data_akshare(remaining, days)
                if not ak_data.empty:
                    if chinese_data.empty:
                        chinese_data = ak_data
                    else:
                        chinese_data = pd.concat([chinese_data, ak_data], axis=1)
            except Exception:
                pass

        if not chinese_data.empty:
            data_frames.append(chinese_data)

    if us_stock_tickers:
        obtained = False
        if use_akshare:
            try:
                us_data = load_price_data_akshare(us_stock_tickers, days)
                if not us_data.empty:
                    data_frames.append(us_data)
                    obtained = True
            except Exception:
                pass
        if not obtained and use_alpha and alpha_vantage_key:
            try:
                av_data = load_price_data_alpha_vantage(
                    us_stock_tickers, days, api_key=alpha_vantage_key
                )
                if not av_data.empty:
                    data_frames.append(av_data)
                    obtained = True
            except Exception:
                pass
        if not obtained and use_yfinance:
            try:
                us_data = load_price_data_yfinance(us_stock_tickers, days)
                if not us_data.empty:
                    data_frames.append(us_data)
            except Exception:
                pass

    if hk_index_tickers:
        obtained = False
        if use_akshare:
            try:
                hk_data = load_price_data_hk_index_akshare(hk_index_tickers, days)
                if not hk_data.empty:
                    data_frames.append(hk_data)
                    obtained = True
            except Exception:
                pass
        if not obtained and use_yfinance:
            try:
                mapping = {"HSI": "^HSI"}
                mapped = [mapping.get(t.upper(), t) for t in hk_index_tickers]
                hk_data = load_price_data_yfinance(mapped, days)
                if not hk_data.empty:
                    if isinstance(hk_data, pd.Series):
                        hk_data = hk_data.to_frame()
                    rename_map = {}
                    for orig, yfs in mapping.items():
                        if yfs in hk_data.columns:
                            rename_map[yfs] = orig
                    hk_data = hk_data.rename(columns=rename_map)
                    data_frames.append(hk_data)
            except Exception:
                pass

    if crypto_tickers:
        if use_binance:
            try:
                crypto_data = load_price_data_binance(crypto_tickers, days)
                if not crypto_data.empty:
                    data_frames.append(crypto_data)
            except Exception:
                pass
        if use_yfinance:
            try:
                crypto_data = load_price_data_yfinance(crypto_tickers, days)
                if not crypto_data.empty:
                    data_frames.append(crypto_data)
            except Exception:
                pass

    if not data_frames:
        return pd.DataFrame()
    if len(data_frames) == 1:
        return _fill_dataframe_within_valid_range(data_frames[0])
    return _fill_dataframe_within_valid_range(pd.concat(data_frames, axis=1))


def load_price_data(
    tickers: List[str],
    days: int,
    data_sources: List[str] | None = None,
    alpha_vantage_key: str | None = None,
    tushare_token: str | None = None,
    refresh_stale: bool = True,
    remote_cache_days: int | None = None,
) -> pd.DataFrame:
    """内部实现：优先使用本地仓库，不足时再回退远程并写回本地"""
    if not tickers:
        return pd.DataFrame()

    effective_remote_cache_days = max(days, int(remote_cache_days or 3650))

    # API 响应文件缓存（Dexter 借鉴）：命中则直接返回
    try:
        from .api_response_cache import get_cached, set_cached, is_api_cache_enabled
        if is_api_cache_enabled():
            cache_params = {
                "tickers": sorted(tickers),
                "days": days,
                "refresh_stale": refresh_stale,
                "remote_cache_days": effective_remote_cache_days,
            }
            cached = get_cached("prices", cache_params)
            if cached is not None:
                df = pd.DataFrame.from_dict(cached, orient="split")
                if not df.empty and hasattr(df.index, "astype"):
                    try:
                        df.index = pd.to_datetime(df.index)
                    except Exception:
                        pass
                return df
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug("api_response_cache get_cached skip: %s", e)

    if alpha_vantage_key is None or tushare_token is None:
        keys = get_api_keys()
        if alpha_vantage_key is None:
            alpha_vantage_key = keys.get("ALPHA_VANTAGE_KEY")
        if tushare_token is None:
            tushare_token = keys.get("TUSHARE_TOKEN")

    if data_sources is None:
        data_sources = get_active_data_sources()

    local_series_map: Dict[str, pd.Series] = {}
    tickers_to_refresh: List[str] = []

    # 1. 先尝试从本地仓库读取
    for t in tickers:
        s = data_store.load_local_price_history(t)
        if s is not None and not s.empty:
            # 本地有数据，先存下来，稍后统一裁剪
            local_series_map[t] = s
        if _should_refresh_local_series(t, s, refresh_stale=refresh_stale):
            tickers_to_refresh.append(t)

    # 2. 对于本地缺失或已过时的标的，从远程加载并写回本地
    if tickers_to_refresh:
        # 为本地仓库尽量缓存更长的历史，而不仅仅是用户当前选择的 days。
        # 这里与 data_updater 中的 MAX_CACHE_DAYS 保持一致，默认约 10 年（3650 天）。
        REMOTE_CACHE_DAYS = effective_remote_cache_days
        remote_df = _load_price_data_remote(
            tickers=tickers_to_refresh,
            days=REMOTE_CACHE_DAYS,
            data_sources=data_sources,
            alpha_vantage_key=alpha_vantage_key,
            tushare_token=tushare_token,
        )
        if remote_df is not None and not remote_df.empty:
            for t in tickers_to_refresh:
                if t in remote_df.columns:
                    remote_series = remote_df[t].dropna()
                    if remote_series.empty:
                        continue
                    local_series = local_series_map.get(t)
                    if local_series is not None and not local_series.empty:
                        local_series = _trim_synthetic_tail(local_series, remote_series)
                        s = pd.concat([local_series, remote_series]).sort_index()
                        s = s[~s.index.duplicated(keep="last")]
                    else:
                        s = remote_series
                    if not s.empty:
                        # 旧接口继续保存为单列 close，以保持兼容性
                        data_store.save_local_price_history(t, s)
                        local_series_map[t] = s

    # 3. 组合所有本地数据，并裁剪到最近 days 天
    if not local_series_map:
        return pd.DataFrame()

    # 取所有本地序列的并集后，再选所有 ticker 列
    all_index = None
    for s in local_series_map.values():
        if all_index is None:
            all_index = s.index
        else:
            all_index = all_index.union(s.index)

    if all_index is None or all_index.empty:
        return pd.DataFrame()

    all_index = all_index.sort_values()
    # 只保留最近 days 天
    cutoff = all_index.max() - timedelta(days=days - 1)
    trimmed_index = all_index[all_index >= cutoff]

    result = pd.DataFrame(index=trimmed_index)
    for t, s in local_series_map.items():
        result[t] = s.reindex(trimmed_index)

    result_df = _fill_dataframe_within_valid_range(result)
    
    # 方案一：数据清洗增强（去重、前向填充限制、异常收益率截断）
    if not result_df.empty:
        result_df = _clean_price_dataframe(result_df)
    
    # 数据质量检查
    if not result_df.empty:
        min_points = _estimate_quality_min_points(days)
        is_valid, warnings = validate_data_before_analysis(
            result_df,
            tickers,
            min_data_points=min_points,
        )
        if warnings:
            # 记录警告但不阻止返回数据
            import logging
            logger = logging.getLogger(__name__)
            for warning in warnings:
                logger.warning(f"数据质量警告: {warning}")

    # API 响应文件缓存：写入本次结果
    try:
        from .api_response_cache import set_cached, is_api_cache_enabled
        if is_api_cache_enabled() and not result_df.empty:
            cache_params = {
                "tickers": sorted(tickers),
                "days": days,
                "refresh_stale": refresh_stale,
                "remote_cache_days": effective_remote_cache_days,
            }
            set_cached("prices", cache_params, result_df.to_dict(orient="split"))
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug("api_response_cache set_cached skip: %s", e)

    return result_df


# ================================================================
#  新增：统一 OHLCV 加载接口（本地缓存 + 远程按优先级）
# ================================================================


def load_ohlcv_data(
    tickers: List[str],
    days: int,
    data_sources: List[str] | None = None,
    alpha_vantage_key: str | None = None,
    tushare_token: str | None = None,
    refresh_stale: bool = True,
    remote_cache_days: int | None = None,
) -> Dict[str, pd.DataFrame]:
    """内部实现：优先使用本地 OHLCV 仓库，不足时再回退远程并写回本地"""
    if not tickers:
        return {}

    effective_remote_cache_days = max(days, int(remote_cache_days or 3650))

    if alpha_vantage_key is None or tushare_token is None:
        keys = get_api_keys()
        if alpha_vantage_key is None:
            alpha_vantage_key = keys.get("ALPHA_VANTAGE_KEY")
        if tushare_token is None:
            tushare_token = keys.get("TUSHARE_TOKEN")

    if data_sources is None:
        data_sources = get_active_data_sources()

    local_ohlcv_map: Dict[str, pd.DataFrame] = {}
    tickers_to_refresh: List[str] = []

    # 1. 先尝试从本地 OHLCV 仓库读取
    for t in tickers:
        df = data_store.load_local_ohlcv_history(t)
        if df is not None and not df.empty:
            local_ohlcv_map[t] = df
        if _should_refresh_local_ohlcv_history(t, df, refresh_stale=refresh_stale):
            tickers_to_refresh.append(t)

    # 2. 对于本地缺失或已陈旧的标的，从远程加载 OHLCV 并写回本地
    if tickers_to_refresh:
        remote_map = _load_ohlcv_data_remote(
            tickers=tickers_to_refresh,
            days=effective_remote_cache_days,
            data_sources=data_sources,
            alpha_vantage_key=alpha_vantage_key,
            tushare_token=tushare_token,
        )
        if remote_map:
            for t in tickers_to_refresh:
                df = remote_map.get(t)
                if df is not None and not df.empty:
                    local_df = local_ohlcv_map.get(t)
                    if local_df is not None and not local_df.empty:
                        local_df = _trim_synthetic_ohlcv_tail(local_df, df)
                        merged = pd.concat([local_df, df]).sort_index()
                        merged = merged[~merged.index.duplicated(keep="last")]
                    else:
                        merged = df.sort_index()
                    data_store.save_local_ohlcv_history(t, merged)
                    local_ohlcv_map[t] = merged

    # 3. 截取最近 days 天，并返回
    if not local_ohlcv_map:
        return {}

    out: Dict[str, pd.DataFrame] = {}
    for t, df in local_ohlcv_map.items():
        if df is None or df.empty:
            continue
        tmp = df.sort_index().iloc[-days:]
        out[t] = tmp

    return out


# ================================================================
#  外部数据源接口
# ================================================================


def load_external_data(
    economic: bool = True,
    industry: bool = True,
    sentiment: bool = True,
    flow: bool = True,
    start_date: str = "2010-01-01",
    end_date: str = None,
) -> Dict[str, Any]:
    """
    加载外部数据（宏观经济、行业轮动、市场情绪、资金流向）

    Args:
        economic: 是否加载宏观经济数据
        industry: 是否加载行业轮动数据
        sentiment: 是否加载市场情绪数据
        flow: 是否加载资金流向数据
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        外部数据字典
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    external_data = {}

    try:
        from .data.external.loader import ExternalDataLoader
    except ImportError:
        try:
            from core.data.external.loader import ExternalDataLoader
        except ImportError:
            return external_data

    loader = ExternalDataLoader(data_dir="data/external")

    if economic:
        try:
            economic_data = loader.economic_loader.get_all_data(start_date, end_date)
            external_data["economic"] = economic_data
        except Exception:
            external_data["economic"] = {}

    if industry:
        try:
            industry_df = loader.industry_loader.get_industry_rotation(start_date, end_date)
            external_data["industry"] = industry_df
        except Exception:
            external_data["industry"] = pd.DataFrame()

    if sentiment:
        try:
            sentiment_df = loader.sentiment_loader.get_market_sentiment(start_date, end_date)
            external_data["sentiment"] = sentiment_df
        except Exception:
            external_data["sentiment"] = pd.DataFrame()

    if flow:
        try:
            flow_df = loader.flow_loader.get_flow_data(start_date, end_date)
            external_data["flow"] = flow_df
        except Exception:
            external_data["flow"] = pd.DataFrame()

    return external_data


def merge_price_with_external(
    price_df: pd.DataFrame,
    external_data: Dict[str, Any] = None,
    start_date: str = "2010-01-01",
    end_date: str = None,
) -> pd.DataFrame:
    """
    将价格数据与外部数据合并

    Args:
        price_df: 价格数据
        external_data: 外部数据字典（若为None则自动加载）
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        合并后的DataFrame
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    if external_data is None:
        external_data = load_external_data(
            economic=True, industry=True, sentiment=True, flow=True,
            start_date=start_date, end_date=end_date
        )

    try:
        from .data.external.loader import ExternalDataLoader
    except ImportError:
        try:
            from core.data.external.loader import ExternalDataLoader
        except ImportError:
            return price_df

    loader = ExternalDataLoader(data_dir="data/external")
    merged_df = loader.merge_price_with_external(price_df, external_data)

    return merged_df


def get_external_features(
    price_df: pd.DataFrame,
    start_date: str = "2010-01-01",
    end_date: str = None,
) -> pd.DataFrame:
    """
    获取外部数据特征（完整的特征工程管道）

    流程：
    1. 加载外部数据
    2. 数据合并
    3. 特征提取

    Args:
        price_df: 价格数据
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        包含所有特征的DataFrame
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        from .data.external.loader import ExternalDataLoader
    except ImportError:
        try:
            from core.data.external.loader import ExternalDataLoader
        except ImportError:
            return price_df

    loader = ExternalDataLoader(data_dir="data/external")
    features_df = loader.get_full_pipeline(price_df, start_date, end_date)

    return features_df


def get_economic_summary(start_date: str = "2010-01-01", end_date: str = None) -> Dict[str, Any]:
    """
    获取宏观经济摘要

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        宏观经济摘要字典
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        from .data.external.loader import ExternalDataLoader
    except ImportError:
        try:
            from core.data.external.loader import ExternalDataLoader
        except ImportError:
            return {}

    loader = ExternalDataLoader(data_dir="data/external")
    return loader.get_economic_summary(start_date, end_date)


def get_industry_summary(start_date: str = "2010-01-01", end_date: str = None) -> Dict[str, Any]:
    """
    获取行业轮动摘要

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        行业轮动摘要字典
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        from .data.external.loader import ExternalDataLoader
    except ImportError:
        try:
            from core.data.external.loader import ExternalDataLoader
        except ImportError:
            return {}

    loader = ExternalDataLoader(data_dir="data/external")
    return loader.get_industry_summary(start_date, end_date)


def get_sentiment_summary(start_date: str = "2010-01-01", end_date: str = None) -> Dict[str, Any]:
    """
    获取市场情绪摘要

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        市场情绪摘要字典
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        from .data.external.loader import ExternalDataLoader
    except ImportError:
        try:
            from core.data.external.loader import ExternalDataLoader
        except ImportError:
            return {}

    loader = ExternalDataLoader(data_dir="data/external")
    return loader.get_sentiment_summary(start_date, end_date)


def get_flow_summary(start_date: str = "2010-01-01", end_date: str = None) -> Dict[str, Any]:
    """
    获取资金流向摘要

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        资金流向摘要字典
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        from .data.external.loader import ExternalDataLoader
    except ImportError:
        try:
            from core.data.external.loader import ExternalDataLoader
        except ImportError:
            return {}

    loader = ExternalDataLoader(data_dir="data/external")
    return loader.get_flow_summary(start_date, end_date)

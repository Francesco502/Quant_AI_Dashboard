"""统一数据服务模块

职责：
- 封装 AkShare / yfinance / AlphaVantage / Binance 等多源价格数据获取逻辑；
- 对外提供一个统一的 `load_price_data` 接口，方便在 app.py 中调用；
- 后续可以在这里加入本地缓存、持久化等功能，而不影响上层调用。
"""

from __future__ import annotations

from datetime import datetime, timedelta
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


DATA_DIR = Path("data")
USER_STATE_FILE = DATA_DIR / "user_state.json"
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
    """根据请求窗口估算最小有效点数，避免短窗口请求被误判为数据不足。"""
    safe_days = max(1, int(days or 1))
    estimated_trading_points = ceil(safe_days * 0.55) - 1
    return min(30, max(1, estimated_trading_points))

def identify_asset_type(ticker: str) -> str:
    """
    根据代码规则推断资产类型
    Returns: 'stock', 'index', 'etf', 'fund', 'bond', 'gold', 'crypto', 'us_stock', 'unknown'
    """
    ticker = ticker.upper()
    hint = get_asset_hint(ticker)
    hinted_type = hint.get("asset_type") if hint else None
    hinted_name = hint.get("name") if hint else None
    
    if ticker.endswith(".OF"):
        return "fund" # 场外基金
    
    if ticker in ["AU99.99", "AU99.95", "AG(T+D)", "AU(T+D)"]:
        return "gold"
        
    # Crypto (Binance format usually handled separately, but just in case)
    if ticker.endswith("USDT"):
        return "crypto"
        
    # US Stock (simple heuristic)
    if ticker.isalpha() and len(ticker) <= 5 and not ticker.startswith("SH") and not ticker.startswith("SZ"):
        # Could be US stock
        return "us_stock"
        
    resolved = resolve_asset_type(ticker, asset_name=hinted_name, asset_type=hinted_type)
    if resolved in {"fund", "etf", "stock"}:
        return resolved

    # A-Share / ETF / Index
    if ticker.isdigit() and len(ticker) == 6:
        # 00, 30, 60, 68 -> Stock
        if ticker.startswith(("00", "30", "60", "68")):
            return "stock"
        # 51, 15 -> ETF
        if ticker.startswith(("51", "15")):
            return "etf"
        # 11, 12 -> Bond
        if ticker.startswith(("11", "12")):
            return "bond"
        # 000xxx (Index usually?)
        return "stock" # Default to stock/index mix
        
    return "stock"

def get_active_data_sources() -> List[str]:
    """获取当前激活的数据源列表（按优先级排序）。统一由服务端环境变量控制。"""
    return _env_enabled_sources()


def get_api_key_status() -> Dict[str, bool]:
    """返回服务端环境变量中的数据源密钥是否已配置，不暴露明文。"""
    api_keys = get_api_keys()
    return {
        "Tushare": bool(api_keys.get("TUSHARE_TOKEN")),
        "AlphaVantage": bool(api_keys.get("ALPHA_VANTAGE_KEY")),
    }

def get_api_keys() -> Dict[str, str]:
    """获取数据源 API Keys。统一从服务端环境变量读取。"""
    api_keys = {}

    if os.getenv("ALPHA_VANTAGE_KEY"):
        api_keys["ALPHA_VANTAGE_KEY"] = os.getenv("ALPHA_VANTAGE_KEY")
    if os.getenv("TUSHARE_TOKEN"):
        api_keys["TUSHARE_TOKEN"] = os.getenv("TUSHARE_TOKEN")

    return api_keys



# ================================================================
#  收盘价级别的历史代码（兼容旧逻辑）
# ================================================================


def load_price_data_akshare(tickers: List[str], days: int) -> pd.DataFrame:
    """使用AkShare获取A股/ETF/基金/美股数据（从 app.py 抽取）"""
    if not AKSHARE_AVAILABLE:
        raise ImportError("AkShare未安装，请运行: pip install akshare")

    data_dict: Dict[str, pd.Series] = {}
    end_date_str = datetime.now().strftime("%Y%m%d")
    start_date_str = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    us_stock_prefix = {
        "AAPL": "105.AAPL",
        "TSLA": "105.TSLA",
        "NVDA": "105.NVDA",
        "MSFT": "105.MSFT",
        "GOOGL": "105.GOOGL",
        "AMZN": "105.AMZN",
        "META": "105.META",
        "NFLX": "105.NFLX",
        "AMD": "105.AMD",
        "INTC": "105.INTC",
        "BABA": "105.BABA",
        "JD": "105.JD",
    }

    for ticker in tickers:
        # 处理 .OF 后缀 (场外基金)
        is_otc_fund = ticker.endswith(".OF")
        clean_ticker = ticker.replace(".SZ", "").replace(".SS", "").replace(".OF", "")
        hint = get_asset_hint(ticker)
        resolved_type = resolve_asset_type(
            ticker,
            asset_name=str(hint.get("name") or ""),
            asset_type=hint.get("asset_type"),
        )

        df = pd.DataFrame()
        is_fund = resolved_type == "fund" or is_otc_fund
        is_us_stock = ticker in us_stock_prefix or ticker.upper() in us_stock_prefix
        
        # 简单判断黄金/贵金属 (上海黄金交易所)
        is_gold_spot = ticker.upper() in ["AU99.99", "AU99.95", "AG(T+D)", "AU(T+D)"]

        try:
            # -1) 黄金/贵金属现货 (上海黄金交易所)
            if is_gold_spot:
                try:
                    # 尝试获取黄金现货数据
                    # 注意：AkShare 接口可能变动，这里尝试 spot_hist_sge
                    temp_df = ak.spot_hist_sge(symbol=ticker)
                    if not temp_df.empty:
                        # 转换列名
                        if "date" in temp_df.columns:
                            temp_df["date"] = pd.to_datetime(temp_df["date"])
                            temp_df = temp_df.set_index("date")
                        elif "日期" in temp_df.columns:
                            temp_df["日期"] = pd.to_datetime(temp_df["日期"])
                            temp_df = temp_df.set_index("日期")
                        
                        # 找收盘价
                        for col in ["close", "收盘", "收盘价"]:
                            if col in temp_df.columns:
                                df = temp_df[[col]].rename(columns={col: "close"})
                                break
                except Exception:
                    pass

            # 0) 场外基金优先按净值获取，避免误读成股票价格
            if df.empty and (is_otc_fund or resolved_type == "fund"):
                try:
                    temp_df = ak.fund_open_fund_info_em(
                        symbol=clean_ticker, indicator="单位净值走势"
                    )
                    if not temp_df.empty:
                        date_col = None
                        value_col = None
                        for col in ["净值日期", "日期", "date"]:
                            if col in temp_df.columns:
                                date_col = col
                                break
                        for col in ["单位净值", "净值", "value"]:
                            if col in temp_df.columns:
                                value_col = col
                                break
                        if date_col and value_col:
                            temp_df[date_col] = pd.to_datetime(temp_df[date_col])
                            temp_df = temp_df.set_index(date_col)
                            df = temp_df[[value_col]].rename(columns={value_col: "净值"})
                except Exception:
                    pass

            # 1) 美股处理
            if df.empty and is_us_stock:
                try:
                    us_symbol = us_stock_prefix.get(
                        ticker.upper(), f"105.{ticker.upper()}"
                    )
                    temp_df = ak.stock_us_hist(
                        symbol=us_symbol,
                        period="daily",
                        start_date=start_date_str,
                        end_date=end_date_str,
                    )
                    if not temp_df.empty:
                        df = temp_df
                except Exception:
                    pass

            # 2) 优先尝试作为 ETF 获取行情 (场内交易价格优先于净值)
            # 159755 等 ETF 应优先走此逻辑
            if df.empty and resolved_type != "fund":
                try:
                    temp_df = ak.fund_etf_hist_em(
                        symbol=clean_ticker,
                        start_date=start_date_str,
                        end_date=end_date_str,
                    )
                    if not temp_df.empty:
                        df = temp_df
                except Exception:
                    pass

            # 3) 尝试作为 A股 获取行情
            if df.empty and resolved_type == "stock":
                try:
                    temp_df = ak.stock_zh_a_hist(
                        symbol=clean_ticker,
                        period="daily",
                        start_date=start_date_str,
                        end_date=end_date_str,
                        adjust="qfq",
                    )
                    if not temp_df.empty:
                        df = temp_df
                except Exception:
                    pass

            # 4) 最后尝试作为 开放式基金 获取净值 (兜底)
            # 仅当上述行情接口都无数据，且看起来像基金代码时尝试
            if df.empty and is_fund:
                try:
                    temp_df = ak.fund_open_fund_info_em(
                        symbol=clean_ticker, indicator="单位净值走势"
                    )
                    if not temp_df.empty:
                        date_col = None
                        value_col = None
                        for col in ["净值日期", "日期", "date"]:
                            if col in temp_df.columns:
                                date_col = col
                                break
                        for col in ["单位净值", "净值", "value"]:
                            if col in temp_df.columns:
                                value_col = col
                                break
                        if date_col and value_col:
                            temp_df[date_col] = pd.to_datetime(temp_df[date_col])
                            temp_df = temp_df.set_index(date_col)
                            df = temp_df[[value_col]].rename(columns={value_col: "净值"})
                        elif len(temp_df.columns) >= 2:
                            temp_df.iloc[:, 0] = pd.to_datetime(temp_df.iloc[:, 0])
                            temp_df = temp_df.set_index(temp_df.columns[0])
                            df = temp_df.iloc[:, [0]].copy()
                            df.columns = ["净值"]
                except Exception:
                    pass

            if not df.empty:
                if "日期" in df.columns:
                    df["日期"] = pd.to_datetime(df["日期"])
                    df = df.set_index("日期")
                elif "净值日期" in df.columns:
                    df.index = pd.to_datetime(df.index)
                elif not isinstance(df.index, pd.DatetimeIndex):
                    try:
                        df.index = pd.to_datetime(df.index)
                    except Exception:
                        pass

                price_col = None
                for col_name in ["收盘", "净值", "单位净值", "累计净值", "close", "net_value"]:
                    if col_name in df.columns:
                        price_col = col_name
                        break

                if price_col is None:
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        price_col = numeric_cols[0]
                    elif len(df.columns) > 0:
                        price_col = df.columns[0]

                if price_col:
                    price_series = df[price_col].tail(days)
                    price_series.index = pd.to_datetime(price_series.index)
                    data_dict[ticker] = price_series
        except Exception:
            continue

    if not data_dict:
        raise ValueError("AkShare无法获取任何数据")

    result = pd.DataFrame(data_dict)
    return result.ffill().bfill()


def load_price_data_tushare(
    tickers: List[str],
    days: int,
    tushare_token: str,
) -> pd.DataFrame:
    """使用 Tushare Pro 获取 A股/基金等日线数据

    仅对带 .SZ/.SS 后缀的中国资产生效；其他代码类型仍由 AkShare 等数据源处理。
    """
    if not TUSHARE_AVAILABLE:
        raise ImportError("Tushare 未安装，请运行: pip install tushare")
    if not tushare_token:
        raise ValueError("未提供 Tushare Token")

    ts.set_token(tushare_token)
    pro = ts.pro_api()

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


def load_price_data_yfinance(tickers: List[str], days: int) -> pd.DataFrame:
    """从 yfinance 获取数据的简化封装（保留原有重试/兜底逻辑可以后续迁移）"""
    if not tickers:
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


def load_cn_realtime_quotes_sina(tickers: List[str]) -> Dict[str, Dict[str, object]]:
    """Load mainland China realtime quotes from Sina in a lightweight batch call."""
    normalized: List[Tuple[str, str]] = []
    for ticker in tickers:
        text = str(ticker or "").strip()
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) != 6:
            continue
        prefix = "sh" if digits.startswith(("5", "6", "9", "11", "12")) else "sz"
        normalized.append((ticker, f"{prefix}{digits}"))

    if not normalized:
        return {}

    url = "https://hq.sinajs.cn/list=" + ",".join(code for _, code in normalized)
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0",
    }

    response = requests.get(url, timeout=15, headers=headers)
    response.raise_for_status()
    response.encoding = "gbk"

    quote_map: Dict[str, Dict[str, object]] = {}
    for line in response.text.splitlines():
        line = line.strip()
        if not line or '="' not in line:
            continue
        left, right = line.split('="', 1)
        payload = right.rstrip('";')
        symbol = left.rsplit("_", 1)[-1]
        fields = payload.split(",")
        if len(fields) < 32:
            continue

        ticker = next((original for original, code in normalized if code == symbol), None)
        if ticker is None:
            continue

        try:
            price = float(fields[3])
        except (TypeError, ValueError):
            continue

        trade_date = str(fields[30]).strip() or None
        trade_time = str(fields[31]).strip() or None
        timestamp = None
        if trade_date and trade_time:
            try:
                timestamp = pd.Timestamp(f"{trade_date} {trade_time}")
            except Exception:
                timestamp = None

        quote_map[ticker] = {
            "ticker": ticker,
            "name": fields[0].strip(),
            "price": price,
            "trade_date": trade_date,
            "trade_time": trade_time,
            "timestamp": timestamp,
        }

    return quote_map


# ================================================================
#  新增：各数据源的 OHLCV 提取函数
# ================================================================


def _normalize_ohlcv_from_df(
    df: pd.DataFrame,
    open_candidates: List[str],
    high_candidates: List[str],
    low_candidates: List[str],
    close_candidates: List[str],
    volume_candidates: List[str],
) -> Optional[pd.DataFrame]:
    """
    通用的 DataFrame -> OHLCV 归一化工具：
    - 尝试按候选列名寻找 open/high/low/close/volume；
    - 若 open/high/low 缺失，则回退为 close；
    - 若 close 也找不到，则返回 None。
    """
    cols_lower = {str(c).lower(): c for c in df.columns}

    def pick(candidates: List[str]) -> Optional[str]:
        for name in candidates:
            key = name.lower()
            for lc, orig in cols_lower.items():
                if key in lc:
                    return orig
        return None

    close_col = pick(close_candidates)
    if close_col is None:
        # 如果没有 close，就尝试从所有数值列里取第一列
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            return None
        close_col = numeric_cols[0]

    open_col = pick(open_candidates) or close_col
    high_col = pick(high_candidates) or close_col
    low_col = pick(low_candidates) or close_col
    vol_col = pick(volume_candidates)

    out = pd.DataFrame(
        {
            "open": df[open_col].astype(float),
            "high": df[high_col].astype(float),
            "low": df[low_col].astype(float),
            "close": df[close_col].astype(float),
        }
    )
    if vol_col is not None:
        out["volume"] = df[vol_col].astype(float)
    else:
        out["volume"] = np.nan

    # 统一索引为日期
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    return out


def _fetch_akshare_ohlcv_single(
    ticker: str, days: int, end_date_str: str, start_date_str: str
) -> Optional[pd.DataFrame]:
    """单个标的的 AkShare OHLCV 数据获取（供并发调用，带超时控制）"""
    if not AKSHARE_AVAILABLE:
        return None

    clean_ticker = ticker.replace(".SZ", "").replace(".SS", "")
    df = pd.DataFrame()
    hint = get_asset_hint(ticker)
    resolved_type = resolve_asset_type(
        ticker,
        asset_name=str(hint.get("name") or ""),
        asset_type=hint.get("asset_type"),
    )
    is_fund = resolved_type == "fund"

    us_stock_prefix = {
        "AAPL": "105.AAPL",
        "TSLA": "105.TSLA",
        "NVDA": "105.NVDA",
        "MSFT": "105.MSFT",
        "GOOGL": "105.GOOGL",
        "AMZN": "105.AMZN",
        "META": "105.META",
        "NFLX": "105.NFLX",
        "AMD": "105.AMD",
        "INTC": "105.INTC",
        "BABA": "105.BABA",
        "JD": "105.JD",
    }
    is_us_stock = ticker in us_stock_prefix or ticker.upper() in us_stock_prefix

    try:
        # 1) 公开基金净值（无 OHLC，只能构造）
        if is_fund:
            try:
                temp_df = ak.fund_open_fund_info_em(
                    symbol=clean_ticker, indicator="单位净值走势"
                )
                if temp_df is not None and not temp_df.empty:
                    date_col = None
                    value_col = None
                    for col in ["净值日期", "日期", "date"]:
                        if col in temp_df.columns:
                            date_col = col
                            break
                    for col in ["单位净值", "净值", "value"]:
                        if col in temp_df.columns:
                            value_col = col
                            break
                    if date_col and value_col:
                        temp_df[date_col] = pd.to_datetime(temp_df[date_col])
                        temp_df = temp_df.set_index(date_col)
                        df = temp_df[[value_col]].rename(columns={value_col: "净值"})
            except Exception:
                pass

        # 2) 美股（日线含 OHLCV）
        if df.empty and is_us_stock:
            try:
                us_symbol = us_stock_prefix.get(
                    ticker.upper(), f"105.{ticker.upper()}"
                )
                temp_df = ak.stock_us_hist(
                    symbol=us_symbol,
                    period="daily",
                    start_date=start_date_str,
                    end_date=end_date_str,
                )
                if temp_df is not None and not temp_df.empty:
                    df = temp_df
            except Exception:
                pass

        # 3) ETF / A 股（日线含 OHLCV）
        if df.empty and resolved_type != "fund":
            try:
                temp_df = ak.fund_etf_hist_em(
                    symbol=clean_ticker,
                    start_date=start_date_str,
                    end_date=end_date_str,
                )
                if temp_df is not None and not temp_df.empty:
                    df = temp_df
            except Exception:
                pass

        if df.empty and resolved_type == "stock":
            try:
                temp_df = ak.stock_zh_a_hist(
                    symbol=clean_ticker,
                    period="daily",
                    start_date=start_date_str,
                    end_date=end_date_str,
                    adjust="qfq",
                )
                if temp_df is not None and not temp_df.empty:
                    df = temp_df
            except Exception:
                pass

        if df.empty:
            return None

        # 统一索引为日期
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.set_index("日期")
        elif "净值日期" in df.columns:
            df.index = pd.to_datetime(df["净值日期"])
        elif not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                pass

        # 使用通用归一化：中文/英文列名混合
        norm = _normalize_ohlcv_from_df(
            df,
            open_candidates=["开盘", "open"],
            high_candidates=["最高", "high"],
            low_candidates=["最低", "low"],
            close_candidates=["收盘", "净值", "单位净值", "累计净值", "close", "net_value"],
            volume_candidates=["成交量", "volume"],
        )
        if norm is None or norm.empty:
            return None

        norm = norm.iloc[-days:]
        return norm
    except Exception:
        return None


def load_ohlcv_data_akshare(tickers: List[str], days: int) -> Dict[str, pd.DataFrame]:
    """使用 AkShare 获取多资产 OHLCV（A股/ETF/基金/部分美股），支持并发请求和超时控制"""
    if not AKSHARE_AVAILABLE:
        return {}

    if not tickers:
        return {}

    end_date_str = datetime.now().strftime("%Y%m%d")
    start_date_str = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

    result: Dict[str, pd.DataFrame] = {}

    # 使用并发请求，但限制并发数避免被封，并设置较短的超时时间（5秒）
    max_workers = min(len(tickers), 3)  # 低配优化：最多3个并发
    timeout_seconds = 5  # 每个请求最多等待5秒

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _fetch_akshare_ohlcv_single, ticker, days, end_date_str, start_date_str
            ): ticker
            for ticker in tickers
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            try:
                # 设置超时，快速失败
                df = fut.result(timeout=timeout_seconds)
                if df is not None and not df.empty:
                    result[ticker] = df
            except Exception:
                # 超时或出错时静默跳过，避免阻塞
                continue

    return result


def load_ohlcv_data_tushare(
    tickers: List[str],
    days: int,
    tushare_token: str,
) -> Dict[str, pd.DataFrame]:
    """使用 Tushare Pro 获取 A 股/基金日线 OHLCV"""
    if not TUSHARE_AVAILABLE or not tushare_token:
        return {}

    ts.set_token(tushare_token)
    pro = ts.pro_api()

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


def _fetch_alpha_vantage_single(
    ticker: str, days: int, api_key: str, base_url: str
) -> Optional[pd.Series]:
    """单个标的的 Alpha Vantage 收盘价数据获取（供并发调用）"""
    end_date = datetime.utcnow().date()
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
    end_date = datetime.utcnow().date()
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


def load_ohlcv_data_yfinance(tickers: List[str], days: int) -> Dict[str, pd.DataFrame]:
    """
    使用 yfinance 获取多资产的 OHLCV 数据

    返回:
        {ticker: DataFrame(index=日期, columns=[open, high, low, close, volume])}
    """
    if not tickers:
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


def _clean_price_dataframe(df: pd.DataFrame, max_one_day_return: float = 0.30, ffill_limit: int = 5) -> pd.DataFrame:
    """
    方案一：数据清洗增强。对每列：去重、前向填充（限制天数）、单日收益率 Winsorize（默认±30%）。
    """
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
        # 单日收益率截断后重建价格
        ret = s.pct_change()
        ret = ret.clip(lower=-max_one_day_return, upper=max_one_day_return)
        clean = s.iloc[0] * (1 + ret.fillna(0)).cumprod()
        out[col] = clean.reindex(out.index)
    return _fill_dataframe_within_valid_range(out)


def _fill_dataframe_within_valid_range(df: pd.DataFrame) -> pd.DataFrame:
    """Only fill gaps between a column's first and last real observations."""
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

    # 估值类场景需要尽量拿到最新可得价格。
    # 场外基金通常按 T+1 披露净值，允许落后一个自然日；
    # 场内股票/ETF/指数等应尽量更新到当日。
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


def load_price_data(
    tickers: List[str],
    days: int,
    data_sources: List[str] | None = None,
    alpha_vantage_key: str | None = None,
    tushare_token: str | None = None,
    refresh_stale: bool = False,
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
) -> Dict[str, pd.DataFrame]:
    """内部实现：优先使用本地 OHLCV 仓库，不足时再回退远程并写回本地"""
    if not tickers:
        return {}

    if alpha_vantage_key is None or tushare_token is None:
        keys = get_api_keys()
        if alpha_vantage_key is None:
            alpha_vantage_key = keys.get("ALPHA_VANTAGE_KEY")
        if tushare_token is None:
            tushare_token = keys.get("TUSHARE_TOKEN")

    if data_sources is None:
        data_sources = get_active_data_sources()

    local_ohlcv_map: Dict[str, pd.DataFrame] = {}
    missing_tickers: List[str] = []

    # 1. 先尝试从本地 OHLCV 仓库读取
    for t in tickers:
        df = data_store.load_local_ohlcv_history(t)
        if df is None or df.empty:
            missing_tickers.append(t)
        else:
            local_ohlcv_map[t] = df

    # 2. 对于本地缺失的标的，从远程加载 OHLCV 并写回本地
    if missing_tickers:
        REMOTE_CACHE_DAYS = max(days, 3650)
        remote_map = _load_ohlcv_data_remote(
            tickers=missing_tickers,
            days=REMOTE_CACHE_DAYS,
            data_sources=data_sources,
            alpha_vantage_key=alpha_vantage_key,
            tushare_token=tushare_token,
        )
        if remote_map:
            for t, df in remote_map.items():
                if df is not None and not df.empty:
                    data_store.save_local_ohlcv_history(t, df)
                    local_ohlcv_map[t] = df

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

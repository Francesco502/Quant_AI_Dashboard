"""Data fetcher: akshare — price and OHLCV loading.

Auto-extracted from data_service.py.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

try:
    import akshare as ak

    AKSHARE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional local dependency
    ak = None
    AKSHARE_AVAILABLE = False

from core import data_store
from core import tushare_provider
from core.asset_metadata import get_asset_hint, resolve_asset_type

from ..data_utils import get_api_keys
from ..data_cleaning import _clean_price_dataframe

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

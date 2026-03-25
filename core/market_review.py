"""大盘复盘模块

职责：
- 按市场类型（cn/us/both）汇总主要指数、涨跌家数、板块涨跌、北向资金等信息；
- 为前端「大盘复盘」页面与每日分析报告提供结构化数据。

数据源策略（兼容系统代理 / 网络受限环境）：
- A 股指数：AkShare（stock_zh_index_daily），降级方案支持 Tushare（需 token）
- 板块涨跌：同花顺（stock_board_industry_summary_ths），独立域名、稳定
- 涨跌概况：从板块汇总中提取涨跌/涨停跌停家数、振幅、换手率
- 北向资金：东方财富 datacenter（stock_hsgt_fund_flow_summary_em），与 push2 不同域名
- 美股指数：yfinance（基础数据）+ Alpha Vantage（详细数据，需配置 token）
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

import logging
from core import tushare_provider

try:
    import akshare as ak  # type: ignore[import]

    AK_AVAILABLE = True
except Exception:  # pragma: no cover
    ak = None  # type: ignore[assignment]
    AK_AVAILABLE = False

try:
    import pandas as pd  # type: ignore[import]
    PD_AVAILABLE = True
except Exception:  # pragma: no cover
    pd = None  # type: ignore[assignment]
    PD_AVAILABLE = False

try:
    import yfinance as yf  # type: ignore[import]

    YF_AVAILABLE = True
except Exception:  # pragma: no cover
    yf = None  # type: ignore[assignment]
    YF_AVAILABLE = False

try:
    import tushare as ts  # type: ignore[import]

    TUSHARE_AVAILABLE = True
except Exception:  # pragma: no cover
    ts = None  # type: ignore[assignment]
    TUSHARE_AVAILABLE = False

try:
    import requests  # type: ignore[import]

    REQUESTS_AVAILABLE = True
except Exception:  # pragma: no cover
    REQUESTS_AVAILABLE = False


logger = logging.getLogger(__name__)

MarketType = Literal["cn", "us", "both"]


@contextmanager
def _bypass_proxy():
    """临时绕过系统代理（Windows 注册表代理），避免 akshare 请求超时。"""
    saved = {}
    keys = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy")
    for k in keys:
        saved[k] = os.environ.get(k)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    try:
        yield
    finally:
        for k in keys:
            if saved[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = saved[k]


@dataclass
class IndexSnapshot:
    name: str
    value: float
    pct_change: float
    volume: Optional[float] = None  # 成交量（手）
    amount: Optional[float] = None  # 成交额（亿元）
    amplitude: Optional[float] = None  # 振幅(%)
    turn_rate: Optional[float] = None  # 换手率(%)


_CN_INDEX_MAP = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
}


def _cn_indices() -> List[IndexSnapshot]:
    """获取 A 股主要指数快照（优先使用新浪/网易源 stock_zh_index_daily，降级方案包含成交量数据）"""
    # 优先使用 Tushare，字段更规整，适合复盘和 daily analysis 的结构化消费。
    try:
        ts_indices = tushare_provider.get_cn_index_snapshots()
        if ts_indices:
            return [IndexSnapshot(**item) for item in ts_indices]
    except Exception as e:
        logger.debug("Tushare 获取 A 股指数失败，降级到 AkShare: %s", e)

    res: List[IndexSnapshot] = []
    if not AK_AVAILABLE:
        return res

    # 首先尝试 stock_zh_index_spot_sina（新浪源，返回中文列名，但可能较慢）
    try:
        with _bypass_proxy():
            df = ak.stock_zh_index_spot_sina()
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                name = row.get("name", "")
                if name not in _CN_INDEX_MAP.values():
                    continue
                try:
                    current = float(row.get("now", 0))
                    change_pct = float(str(row.get("change", 0)).replace("%", "")) if row.get("change") else 0
                    res.append(IndexSnapshot(name=name, value=round(current, 2), pct_change=round(change_pct, 2)))
                except Exception:
                    continue
            if res:
                return res
    except Exception as e:
        logger.debug("获取 A 股指数实时数据失败: %s", e)

    # 降级使用 stock_zh_index_daily（新浪/网易源，绕过 push2.eastmoney）
    try:
        for symbol, name in _CN_INDEX_MAP.items():
            with _bypass_proxy():
                df = ak.stock_zh_index_daily(symbol=symbol)
            if df is not None and not df.empty and len(df) >= 2:
                tail = df.tail(2)
                prev_close = float(tail.iloc[0]["close"])
                last_close = float(tail.iloc[1]["close"])
                pct = (last_close / prev_close - 1.0) * 100.0 if prev_close else 0.0
                res.append(IndexSnapshot(name=name, value=round(last_close, 2), pct_change=round(pct, 2)))
    except Exception as e:
        logger.warning("获取 A 股指数失败: %s", e)

    # 尝试使用 Tushare 获取更详细的指数数据（成交量、成交额）
    try:
        from core.data_service import get_api_keys
        api_keys = get_api_keys()
        tushare_token = api_keys.get("TUSHARE_TOKEN")
        if tushare_token and TUSHARE_AVAILABLE:
            ts_indices = _cn_indices_tushare(tushare_token)
            if ts_indices:
                # 合并数据：保留 akshare 的涨跌幅，使用 tushare 的成交量
                for ts_idx in ts_indices:
                    for idx in res:
                        if idx.name == ts_idx.name:
                            idx.volume = ts_idx.volume
                            idx.amount = ts_idx.amount
                            break
    except Exception as e:
        logger.debug("Tushare 获取指数详细数据失败: %s", e)

    return res


def _cn_indices_tushare(tushare_token: str) -> List[IndexSnapshot]:
    """使用 Tushare Pro 获取 A股指数详细数据（成交量、成交额）

    注意：需要 Tushare Pro 付费版本权限。
    免费版可能无法访问 index_daily 接口。
    """
    res: List[IndexSnapshot] = []
    if not TUSHARE_AVAILABLE:
        return res

    try:
        ts.set_token(tushare_token)
        pro = ts.pro_api()

        # 验证 API 连接
        try:
            test_df = pro.trade_cal(exchange='SSE', start_date='20240101', end_date='20240110')
            if test_df is None or test_df.empty:
                logger.debug("Tushare API 验证失败，返回空数据")
                return res
        except Exception as e:
            logger.debug(f"Tushare API 验证失败: {e}")
            return res

        # Tushare Pro 的指数数据接口
        # 指数代码格式：SH000001, SZ399001, SZ399006
        index_map = {
            "000001.SH": "上证指数",
            "399001.SZ": "深证成指",
            "399006.SZ": "创业板指",
        }

        for ts_code, name in index_map.items():
            try:
                # 使用 index_daily 接口获取日线数据
                df = pro.index_daily(ts_code=ts_code, fields='ts_code,trade_date,open,high,low,close,vol,amount')
                if df is None or df.empty or len(df) < 2:
                    logger.debug(f"Tushare {name} 数据为空")
                    continue

                df = df.sort_values("trade_date", ascending=False)
                today = df.iloc[0]
                yesterday = df.iloc[1]

                today_close = float(today["close"])
                yesterday_close = float(yesterday["close"])
                pct = (today_close / yesterday_close - 1.0) * 100.0

                # Tushare: vol 是手，amount 是元
                volume = int(today["vol"]) if "vol" in today else None
                amount = float(today["amount"]) if "amount" in today else None

                res.append(IndexSnapshot(
                    name=name,
                    value=round(today_close, 2),
                    pct_change=round(pct, 2),
                    volume=volume,
                    amount=round(amount / 1e8, 2) if amount else None,  # 转亿元
                    amplitude=None,
                    turn_rate=None
                ))
            except Exception as e:
                logger.debug(f"Tushare 获取 {name} 失败: {e}")
                continue
    except Exception as e:
        logger.debug(f"Tushare 初始化失败: {e}")

    return res


def _cn_indices_legacy() -> List[IndexSnapshot]:
    """获取 A 股主要指数快照（stock_zh_index_daily，降级方案）"""
    res: List[IndexSnapshot] = []
    if not AK_AVAILABLE:
        return res
    for symbol, name in _CN_INDEX_MAP.items():
        try:
            with _bypass_proxy():
                df = ak.stock_zh_index_daily(symbol=symbol)
            if df is None or df.empty or len(df) < 2:
                continue
            tail = df.tail(2)
            prev_close = float(tail.iloc[0]["close"])
            last_close = float(tail.iloc[1]["close"])
            pct = (last_close / prev_close - 1.0) * 100.0 if prev_close else 0.0
            res.append(IndexSnapshot(name=name, value=round(last_close, 2), pct_change=round(pct, 2)))
        except Exception as e:
            logger.warning("获取 A 股指数 %s 失败: %s", name, e)
    return res


def _us_indices() -> List[IndexSnapshot]:
    """获取美股主要指数快照（优先使用 Alpha Vantage 获取详细数据，降级使用 yfinance）"""
    tickers = {"^GSPC": "SPX", "^DJI": "DJI", "^IXIC": "IXIC"}
    res: List[IndexSnapshot] = []

    # 尝试使用 Alpha Vantage（支持成交量、成交额）
    try:
        from core.data_service import get_api_keys
        api_keys = get_api_keys()
        av_key = api_keys.get("ALPHA_VANTAGE_KEY")
        if av_key and REQUESTS_AVAILABLE:
            indices = _us_indices_alpha_vantage(tickers, av_key)
            if indices:
                return indices
    except Exception as e:
        logger.debug("Alpha Vantage 获取美股指数失败，降级使用 yfinance: %s", e)

    # 降级使用 yfinance（仅支持价格和涨跌幅）
    if not YF_AVAILABLE:
        return []
    try:
        ys = yf.download(list(tickers.keys()), period="2d", interval="1d", progress=False)
        if ys.empty:
            return res
        close_key = "Adj Close" if "Adj Close" in (ys.columns.get_level_values(0) if hasattr(ys.columns, "levels") else ys.columns) else "Close"
        close = ys[close_key] if hasattr(ys.columns, "levels") else ys
        for code, name in tickers.items():
            if code not in close.columns:
                continue
            series = close[code].dropna()
            if len(series) == 0:
                continue
            last = float(series.iloc[-1])
            pct = (series.iloc[-1] / series.iloc[-2] - 1.0) * 100.0 if len(series) > 1 else 0.0
            res.append(IndexSnapshot(name=name, value=last, pct_change=pct))
    except Exception as e:
        logger.warning("获取美股指数失败: %s", e)
    return res


def _us_indices_alpha_vantage(tickers: Dict[str, str], api_key: str) -> List[IndexSnapshot]:
    """使用 Alpha Vantage 获取美股指数数据（支持成交量、成交额）"""
    res: List[IndexSnapshot] = []
    base_url = "https://www.alphavantage.co/query"

    # Alpha Vantage 的指数代码需要特定前缀
    # 对于主要指数，使用不同的代码格式
    index_mapping = {
        "^GSPC": "^SPX",    # S&P 500
        "^DJI": "^DJI",     # Dow Jones
        "^IXIC": "^IXIC",   # Nasdaq
    }

    for code, name in tickers.items():
        try:
            # Alpha Vantage 使用带 ^ 前缀的指数代码
            symbol = index_mapping.get(code, name)
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "apikey": api_key,
                "outputsize": "compact",
            }
            resp = requests.get(base_url, params=params, timeout=30)
            resp.raise_for_status()
            js = resp.json()

            if "Error Message" in js or "Note" in js:
                continue
            if "Time Series (Daily)" not in js:
                continue

            ts_data = js["Time Series (Daily)"]
            dates = sorted(ts_data.keys(), reverse=True)[:2]
            if len(dates) < 2:
                continue

            today_data = ts_data[dates[0]]
            yesterday_data = ts_data[dates[1]]

            today_close = float(today_data["4. close"])
            yesterday_close = float(yesterday_data["4. close"])
            pct = (today_close / yesterday_close - 1.0) * 100.0

            # Alpha Vantage 列名：1. open, 2. high, 3. low, 4. close, 5. volume
            volume = int(today_data["5. volume"]) if "5. volume" in today_data else None

            res.append(IndexSnapshot(
                name=name,
                value=round(today_close, 2),
                pct_change=round(pct, 2),
                volume=volume,
                amount=None,  # Alpha Vantage 不直接提供成交额
                amplitude=None,
                turn_rate=None
            ))
        except Exception as e:
            logger.debug(f"Alpha Vantage 获取 {name} 失败: {e}")
            continue

    return res


def _cn_overview_and_sectors() -> Dict[str, Any]:
    """A 股涨跌概况与板块信息（同花顺数据源）

    从板块汇总中提取：涨跌家数、涨停跌停数、领涨领跌板块、板块涨跌幅。
    避免下载全部个股（新浪 stock_zh_a_spot 需 35+ 秒）。
    """
    overview: Dict[str, Any] = {
        "up": None, "down": None, "limit_up": None, "limit_down": None,
        "amplitude": None, "turn_rate": None  # 振幅、换手率（整体市场）
    }
    sectors: Dict[str, list] = {"gain": [], "loss": []}

    if not AK_AVAILABLE:
        return {"overview": overview, "sectors": sectors}

    try:
        with _bypass_proxy():
            df = ak.stock_board_industry_summary_ths()
        if df.empty:
            return {"overview": overview, "sectors": sectors}

        cols = list(df.columns)
        name_col = cols[1] if len(cols) > 1 else None
        pct_col = cols[2] if len(cols) > 2 else None
        up_count_col = cols[6] if len(cols) > 6 else None
        down_count_col = cols[7] if len(cols) > 7 else None
        amplitude_col = cols[3] if len(cols) > 3 else None  # 振幅
        turnover_col = cols[4] if len(cols) > 4 else None  # 换手率

        if name_col and pct_col:
            ranked = df[[name_col, pct_col]].copy()
            ranked[pct_col] = pd.to_numeric(ranked[pct_col], errors="coerce")
            ranked = ranked.dropna(subset=[pct_col]).sort_values(pct_col, ascending=False).reset_index(drop=True)
            gain_rows = ranked[ranked[pct_col] > 0].head(5)
            loss_rows = ranked[ranked[pct_col] < 0].sort_values(pct_col, ascending=True).head(5)
            sectors["gain"] = [
                {"name": str(row[name_col]), "pct_change": float(row[pct_col])}
                for _, row in gain_rows.iterrows()
            ]
            sectors["loss"] = [
                {"name": str(row[name_col]), "pct_change": float(row[pct_col])}
                for _, row in loss_rows.iterrows()
            ]

        if up_count_col and down_count_col and name_col:
            try:
                market_rows = df[df[name_col].astype(str).str.contains("A股|沪深|全市场|全部", na=False)]
                if not market_rows.empty:
                    market_row = market_rows.iloc[0]
                    overview["up"] = int(float(market_row[up_count_col]))
                    overview["down"] = int(float(market_row[down_count_col]))
            except Exception:
                pass

        # 提取振幅和换手率（整体市场）
        if amplitude_col:
            try:
                amplitude = round(float(pd.to_numeric(df[amplitude_col], errors="coerce").dropna().mean()), 2)
                if 0 <= amplitude <= 100:
                    overview["amplitude"] = amplitude
            except Exception:
                pass
        if turnover_col:
            try:
                turn_rate = round(float(pd.to_numeric(df[turnover_col], errors="coerce").dropna().mean()), 2)
                if 0 <= turn_rate <= 100:
                    overview["turn_rate"] = turn_rate
            except Exception:
                pass

    except Exception as e:
        logger.warning("获取板块/涨跌概况失败: %s", e)

    return {"overview": overview, "sectors": sectors}


def _cn_northbound() -> Dict[str, Any]:
    """北向资金简要信息（东方财富 datacenter 域名，非 push2）"""
    info: Dict[str, Any] = {"net_inflow": None, "unit": "亿元", "description": ""}

    try:
        ts_info = tushare_provider.get_cn_northbound_flow()
        if ts_info.get("net_inflow") is not None:
            return ts_info
    except Exception as e:
        logger.debug("Tushare 北向资金获取失败，降级到 AkShare: %s", e)

    if not AK_AVAILABLE:
        return info

    fn = getattr(ak, "stock_hsgt_fund_flow_summary_em", None)
    if fn is None:
        logger.debug("akshare 未提供 stock_hsgt_fund_flow_summary_em，跳过北向资金")
        return info

    try:
        with _bypass_proxy():
            df = fn()
        if df.empty:
            return info

        cols = list(df.columns)
        # stock_hsgt_fund_flow_summary_em 返回表格含"资金净流入"或类似列
        # 筛选沪股通 + 深股通 行并求和
        flow_col = None
        for c in cols:
            if "净流入" in c or "资金净" in c:
                flow_col = c
                break
        if flow_col is None and len(cols) > 5:
            flow_col = cols[5]

        if flow_col is not None:
            name_col = cols[1] if len(cols) > 1 else None
            if name_col:
                hk_rows = df[df[name_col].astype(str).str.contains("沪股通|深股通", na=False)]
                if not hk_rows.empty:
                    total = float(hk_rows[flow_col].sum())
                    info["net_inflow"] = round(total, 2)
                    info["description"] = f"北向资金当日净流入 {total:.2f} 亿元"
                else:
                    total = float(df[flow_col].sum())
                    info["net_inflow"] = round(total, 2)
                    info["description"] = f"互联互通当日净流入 {total:.2f} 亿元"
    except Exception as e:
        logger.warning("获取北向资金数据失败: %s", e)
    return info


def daily_review(market: MarketType = "cn") -> Dict[str, Any]:
    """生成大盘复盘摘要"""
    try:
        from core.api_response_cache import get_cached, set_cached, is_api_cache_enabled
        if is_api_cache_enabled():
            cached = get_cached("market_review", {"market": market})
            if cached is not None:
                return cached
    except Exception:
        pass

    today = datetime.now().date().isoformat()
    resp: Dict[str, Any] = {"date": today, "market": market}

    indices: List[IndexSnapshot] = []
    if market in ("cn", "both"):
        indices.extend(_cn_indices())
    if market in ("us", "both"):
        indices.extend(_us_indices())

    resp["indices"] = [asdict(i) for i in indices]

    if market in ("cn", "both"):
        extra = _cn_overview_and_sectors()
        resp["overview"] = extra.get("overview")
        resp["sectors"] = extra.get("sectors")
        resp["northbound"] = _cn_northbound()

    try:
        from core.api_response_cache import set_cached, is_api_cache_enabled
        if is_api_cache_enabled():
            set_cached("market_review", {"market": market}, resp)
    except Exception:
        pass

    return resp

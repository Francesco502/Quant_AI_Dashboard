from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from core import tushare_provider
from core.data_service import identify_asset_type, load_price_data
from core.technical_indicators import calculate_sma

from .config import get_bias_threshold, get_news_max_age_days


logger = logging.getLogger(__name__)


def _infer_name_from_ticker(ticker: str) -> str:
    """优先使用 Tushare 解析 A 股/基金名称，失败时回退为代码本身。"""
    try:
        name = tushare_provider.get_cn_security_name(ticker)
        if name:
            return name
    except Exception as exc:  # pragma: no cover - 容错
        logger.debug("解析标的名称失败 (%s): %s", ticker, exc)
    return ticker


def _iso_text(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _round_or_none(value: Any, digits: int = 2) -> Optional[float]:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        return round(float(value), digits)
    except Exception:
        return None


def _format_number(value: Optional[float], suffix: str = "", digits: int = 2) -> str:
    if value is None:
        return "暂无"
    return f"{value:.{digits}f}{suffix}"


def _format_pct(value: Optional[float]) -> str:
    if value is None:
        return "暂无"
    return f"{value:+.2f}%"


def _pct_change(series: pd.Series, window: int) -> Optional[float]:
    if len(series) < window + 1:
        return None
    start = series.iloc[-window - 1]
    end = series.iloc[-1]
    if start in (None, 0) or pd.isna(start) or pd.isna(end):
        return None
    return (float(end) / float(start) - 1.0) * 100.0


def _annualized_volatility(series: pd.Series, window: int = 20) -> Optional[float]:
    returns = series.pct_change().dropna()
    if len(returns) < window:
        return None
    return float(returns.tail(window).std(ddof=0) * np.sqrt(252) * 100.0)


def _range_snapshot(series: pd.Series, window: int) -> Dict[str, Optional[float]]:
    sample = series.tail(window)
    if sample.empty:
        return {
            "window": float(window),
            "high": None,
            "low": None,
            "distance_to_high_pct": None,
            "distance_to_low_pct": None,
            "range_position_pct": None,
        }

    current = float(sample.iloc[-1])
    high = float(sample.max())
    low = float(sample.min())
    distance_to_high = None if high == 0 else (current / high - 1.0) * 100.0
    distance_to_low = None if low == 0 else (current / low - 1.0) * 100.0
    range_position = None
    if high != low:
        range_position = (current - low) / (high - low) * 100.0

    return {
        "window": float(window),
        "high": round(high, 2),
        "low": round(low, 2),
        "distance_to_high_pct": _round_or_none(distance_to_high),
        "distance_to_low_pct": _round_or_none(distance_to_low),
        "range_position_pct": _round_or_none(range_position),
    }


def _build_profile_lines(profile: Dict[str, Any]) -> List[str]:
    if not profile:
        return []

    lines: List[str] = []
    asset_type = str(profile.get("asset_type") or "")
    if asset_type == "stock":
        if profile.get("industry"):
            lines.append(f"- 行业: {profile['industry']}")
        if profile.get("area"):
            lines.append(f"- 地域: {profile['area']}")
        if profile.get("market"):
            lines.append(f"- 板块属性: {profile['market']}")
    elif asset_type == "fund":
        if profile.get("fund_type"):
            lines.append(f"- 基金类型: {profile['fund_type']}")
        if profile.get("management"):
            lines.append(f"- 管理人: {profile['management']}")
        if profile.get("market"):
            lines.append(f"- 市场: {profile['market']}")

    if profile.get("list_date"):
        lines.append(f"- 上市/成立日期: {profile['list_date']}")
    return lines


def _build_valuation_lines(valuation: Dict[str, Any]) -> List[str]:
    if not valuation:
        return ["- 暂无 Tushare 每日指标数据"]

    lines = [f"- 指标日期: {valuation.get('trade_date') or '暂无'}"]
    fields = [
        ("收盘价", valuation.get("close"), ""),
        ("PE", valuation.get("pe"), ""),
        ("PE(TTM)", valuation.get("pe_ttm"), ""),
        ("PB", valuation.get("pb"), ""),
        ("PS(TTM)", valuation.get("ps_ttm"), ""),
        ("股息率", valuation.get("dv_ratio"), "%"),
        ("股息率(TTM)", valuation.get("dv_ttm"), "%"),
        ("换手率", valuation.get("turnover_rate"), "%"),
        ("自由流通换手率", valuation.get("turnover_rate_f"), "%"),
        ("量比", valuation.get("volume_ratio"), ""),
        ("总市值", valuation.get("total_mv"), "亿元"),
        ("流通市值", valuation.get("circ_mv"), "亿元"),
    ]
    for label, value, suffix in fields:
        if value is None:
            continue
        lines.append(f"- {label}: {_format_number(float(value), suffix)}")
    return lines


def _build_capital_flow_lines(flow: Dict[str, Any]) -> List[str]:
    if not flow:
        return ["- 暂无个股资金流数据"]

    lines = [f"- 数据日期: {flow.get('trade_date') or '暂无'}"]
    if flow.get("description"):
        lines.append(f"- {flow['description']}")

    fields = [
        ("5日主力净流", flow.get("net_mf_5d_amount_billion")),
        ("20日主力净流", flow.get("net_mf_20d_amount_billion")),
        ("大单+超大单净流", flow.get("large_order_net_amount_billion")),
        ("中单净流", flow.get("medium_order_net_amount_billion")),
        ("小单净流", flow.get("small_order_net_amount_billion")),
    ]
    for label, value in fields:
        if value is None:
            continue
        lines.append(f"- {label}: {_format_number(float(value), '亿元')}")
    return lines


def _normalize_ticker_key(ticker: str, market: str = "cn") -> str:
    text = str(ticker or "").strip().upper()
    if market == "cn":
        normalized = tushare_provider.normalize_cn_ticker(text)
        if normalized:
            return normalized.split(".")[0]
    return text


def summarize_market_review(review: Dict[str, Any]) -> Dict[str, Any]:
    overview = review.get("overview") or {}
    sectors = review.get("sectors") or {}
    indices = review.get("indices") or []
    northbound = review.get("northbound") or {}

    breadth = {
        "up": overview.get("up"),
        "down": overview.get("down"),
        "limit_up": overview.get("limit_up"),
        "limit_down": overview.get("limit_down"),
        "amplitude": overview.get("amplitude"),
        "turn_rate": overview.get("turn_rate"),
    }
    if breadth.get("up") is not None and breadth.get("down") not in (None, 0):
        try:
            breadth["advance_decline_ratio"] = round(float(breadth["up"]) / float(breadth["down"]), 2)
        except Exception:
            pass

    return {
        "date": review.get("date"),
        "market": review.get("market"),
        "indices": indices[:3],
        "breadth": breadth,
        "leading_sectors": (sectors.get("gain") or [])[:3],
        "lagging_sectors": (sectors.get("loss") or [])[:3],
        "northbound": northbound,
    }


def _load_scan_universe_for_context(
    focus_tickers: List[str],
    *,
    market: str = "cn",
    limit: int = 180,
) -> List[str]:
    ordered: List[str] = []
    seen = set()

    def _push(value: str) -> None:
        text = str(value or "").strip().upper()
        if not text or text in seen:
            return
        seen.add(text)
        ordered.append(text)

    for item in focus_tickers:
        _push(item)

    if market == "cn":
        try:
            rows = tushare_provider.list_active_a_share_tickers(limit=limit)
            for row in rows:
                _push(str(row.get("ticker") or ""))
        except Exception as exc:  # pragma: no cover - 容错
            logger.debug("加载扫描样本股票池失败: %s", exc)

    return ordered[: max(limit, len(focus_tickers))]


def build_market_scanner_summary(
    focus_tickers: List[str],
    *,
    market: str = "cn",
    scan_limit: int = 180,
    scan_top_n: int = 12,
    scan_min_score: int = 60,
) -> Dict[str, Any]:
    if market != "cn":
        return {
            "market": market,
            "sample_size": 0,
            "result_count": 0,
            "leaders": [],
            "matches": {},
            "limitations": ["当前仅对 A 股提供统一扫描摘要。"],
        }

    universe = _load_scan_universe_for_context(focus_tickers, market=market, limit=scan_limit)
    if not universe:
        return {
            "market": market,
            "sample_size": 0,
            "result_count": 0,
            "leaders": [],
            "matches": {},
            "limitations": ["缺少可用于市场扫描的股票池样本。"],
        }

    try:
        from core.scanner.scanner_engine import get_scanner_engine

        price_df = load_price_data(universe, days=365)
        if price_df is None or price_df.empty:
            return {
                "market": market,
                "sample_size": len(universe),
                "result_count": 0,
                "leaders": [],
                "matches": {},
                "limitations": ["市场扫描价格样本加载失败，无法生成扫描摘要。"],
            }

        engine = get_scanner_engine()
        result_df = engine.scan(
            price_df,
            top_n=scan_top_n,
            min_score=scan_min_score,
        )
    except Exception as exc:  # pragma: no cover - 容错
        logger.debug("构建扫描摘要失败: %s", exc)
        return {
            "market": market,
            "sample_size": len(universe),
            "result_count": 0,
            "leaders": [],
            "matches": {},
            "limitations": [f"市场扫描摘要生成失败: {exc}"],
        }

    if result_df is None or result_df.empty:
        return {
            "market": market,
            "sample_size": len(universe),
            "result_count": 0,
            "leaders": [],
            "matches": {},
            "limitations": [],
        }

    leaders: List[Dict[str, Any]] = []
    matches: Dict[str, Dict[str, Any]] = {}

    focus_map = {
        _normalize_ticker_key(ticker, market=market): str(ticker).strip().upper()
        for ticker in focus_tickers
    }

    for rank, (_, row) in enumerate(result_df.reset_index(drop=True).iterrows(), start=1):
        entry = {
            "ticker": str(row.get("ticker") or "").strip().upper(),
            "score": _round_or_none(row.get("score")),
            "action": str(row.get("action") or "观望"),
            "reasons": str(row.get("reasons") or row.get("reason") or "").strip(),
            "rank": rank,
        }
        if not entry["ticker"]:
            continue
        leaders.append(entry)

        normalized = _normalize_ticker_key(entry["ticker"], market=market)
        original = focus_map.get(normalized)
        if original:
            matches[original] = entry

    top_scores = [float(item["score"]) for item in leaders if item.get("score") is not None]

    return {
        "market": market,
        "sample_size": len(universe),
        "result_count": len(leaders),
        "top_score_avg": round(sum(top_scores) / len(top_scores), 2) if top_scores else None,
        "leaders": leaders[:5],
        "matches": matches,
        "limitations": [],
    }


def build_shared_analysis_context(
    tickers: List[str],
    *,
    market: str = "cn",
) -> Dict[str, Any]:
    if market != "cn":
        return {"market": market, "limitations": []}

    context: Dict[str, Any] = {"market": market, "limitations": []}

    try:
        from core import market_review

        review = market_review.daily_review(market=market)
        context["market_review"] = review
        context["market_review_summary"] = summarize_market_review(review)
    except Exception as exc:  # pragma: no cover - 容错
        logger.debug("构建市场复盘共享上下文失败: %s", exc)
        context["limitations"].append("市场复盘摘要暂不可用。")

    scanner_summary = build_market_scanner_summary(tickers, market=market)
    context["scanner_summary"] = scanner_summary
    context["limitations"].extend(scanner_summary.get("limitations") or [])
    return context


def build_analysis_input(
    ticker: str,
    market: str = "cn",
    *,
    shared_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构建单标的分析输入上下文。"""
    days = 365
    price_df = load_price_data([ticker], days=days)
    if price_df is None or price_df.empty or ticker not in price_df.columns:
        raise ValueError(f"无法获取 {ticker} 的历史价格数据")

    series = price_df[ticker].dropna().sort_index()
    if series.empty:
        raise ValueError(f"{ticker} 历史价格数据为空")

    close = float(series.iloc[-1])
    ma5 = calculate_sma(series, 5).iloc[-1]
    ma10 = calculate_sma(series, 10).iloc[-1]
    ma20 = calculate_sma(series, 20).iloc[-1]

    bias = np.nan
    if ma20 and not np.isnan(ma20) and ma20 != 0:
        bias = (close - float(ma20)) / float(ma20) * 100.0

    trend_ok = False
    if not any(np.isnan(x) for x in (ma5, ma10, ma20)):
        trend_ok = bool(ma5 > ma10 > ma20)

    bias_threshold = get_bias_threshold()
    bias_risk = ""
    if not np.isnan(bias) and bias > bias_threshold:
        bias_risk = f"当前价格相对 MA20 乖离率为 {bias:.2f}%，高于阈值 {bias_threshold:.1f}%，存在追高风险。"

    asset_type = identify_asset_type(ticker)
    name = _infer_name_from_ticker(ticker)

    returns = {
        "5d": _round_or_none(_pct_change(series, 5)),
        "20d": _round_or_none(_pct_change(series, 20)),
        "60d": _round_or_none(_pct_change(series, 60)),
        "120d": _round_or_none(_pct_change(series, 120)),
    }
    volatility_20d = _round_or_none(_annualized_volatility(series, 20))
    range_20d = _range_snapshot(series, 20)
    range_60d = _range_snapshot(series, 60)

    market_context: Optional[Dict[str, Any]] = None
    market_review_summary: Dict[str, Any] = {}
    scanner_summary: Dict[str, Any] = {}
    profile: Dict[str, Any] = {}
    capital_flow: Dict[str, Any] = {}
    limitations: List[str] = []

    if market == "cn":
        if not tushare_provider.get_tushare_token():
            limitations.append("未配置 TUSHARE_TOKEN，估值、换手率和个股资金流上下文可能缺失。")
        try:
            market_context = tushare_provider.get_cn_market_context()
        except Exception as exc:  # pragma: no cover - 容错
            logger.debug("构建市场上下文失败 (%s): %s", ticker, exc)
            limitations.append("市场环境数据暂不可用。")

        try:
            profile = tushare_provider.get_cn_security_profile(ticker)
        except Exception as exc:  # pragma: no cover - 容错
            logger.debug("构建标的画像失败 (%s): %s", ticker, exc)
            limitations.append("标的基本资料和估值数据暂不可用。")

        try:
            capital_flow = tushare_provider.get_cn_security_moneyflow(ticker)
        except Exception as exc:  # pragma: no cover - 容错
            logger.debug("构建个股资金流失败 (%s): %s", ticker, exc)
            limitations.append("个股资金流数据暂不可用。")

        if not (profile.get("valuation") or {}):
            limitations.append("缺少 Tushare 每日指标数据，估值和活跃度判断只能依赖价格走势。")
        if profile.get("asset_type") == "stock" and not capital_flow:
            limitations.append("缺少个股资金流数据，无法确认主力资金连续性。")

    if shared_context:
        shared_market_review = shared_context.get("market_review_summary") or {}
        shared_scanner = shared_context.get("scanner_summary") or {}
        if isinstance(shared_market_review, dict):
            market_review_summary = shared_market_review
        if isinstance(shared_scanner, dict):
            scanner_summary = shared_scanner
        for item in shared_context.get("limitations") or []:
            if item not in limitations:
                limitations.append(str(item))

    meta = {
        "last_close": close,
        "ma5": float(ma5) if ma5 == ma5 else None,
        "ma10": float(ma10) if ma10 == ma10 else None,
        "ma20": float(ma20) if ma20 == ma20 else None,
        "bias": float(bias) if bias == bias else None,
        "bias_threshold": bias_threshold,
        "bias_risk": bias_risk or None,
        "trend_ok": trend_ok,
        "asset_type": asset_type,
        "history_start": _iso_text(series.index[0]),
        "history_end": _iso_text(series.index[-1]),
        "history_points": int(series.shape[0]),
        "returns": returns,
        "volatility_20d": volatility_20d,
        "range_20d": range_20d,
        "range_60d": range_60d,
        "market_context": market_context,
        "profile": profile or None,
        "capital_flow": capital_flow or None,
        "market_review_summary": market_review_summary or None,
        "scanner_summary": scanner_summary or None,
        "analysis_scope": {
            "task": "single_security_trade_decision",
            "market": market,
            "asset_type": asset_type,
            "history_points": int(series.shape[0]),
            "history_start": _iso_text(series.index[0]),
            "history_end": _iso_text(series.index[-1]),
            "uses_tushare_profile": bool(profile),
            "uses_tushare_valuation": bool((profile.get("valuation") or {})),
            "uses_tushare_moneyflow": bool(capital_flow),
            "uses_market_context": bool(market_context),
            "uses_market_review_summary": bool(market_review_summary),
            "uses_scanner_summary": bool(scanner_summary.get("leaders")),
        },
        "limitations": limitations,
    }

    analysis_brief = {
        "ticker": ticker,
        "name": name,
        "market": market,
        "asset_type": asset_type,
        "last_close": close,
        "trend": {
            "ma5": meta["ma5"],
            "ma10": meta["ma10"],
            "ma20": meta["ma20"],
            "trend_ok": trend_ok,
            "bias_pct": meta["bias"],
            "bias_threshold_pct": bias_threshold,
            "returns": returns,
            "volatility_20d_pct": volatility_20d,
            "range_20d": range_20d,
            "range_60d": range_60d,
        },
        "profile": profile or None,
        "market_context": market_context,
        "market_review_summary": market_review_summary or None,
        "capital_flow": capital_flow or None,
        "scanner_summary": scanner_summary or None,
        "limitations": limitations,
    }

    ctx_lines = [
        "【分析任务与数据口径】",
        "- 任务: 单标的交易决策，输出面向交易执行而不是长篇研报。",
        f"- 价格样本区间: {_iso_text(series.index[0])} 至 {_iso_text(series.index[-1])}，共 {series.shape[0]} 个交易日。",
        "- 数据来源: 历史收盘价 + Tushare 基本资料/每日指标/资金流（若可用）+ 市场环境摘要 + 可选新闻摘要。",
        "",
        "【标的画像】",
        f"- 标的代码: {ticker}",
        f"- 标的名称: {name}",
        f"- 市场类型: {asset_type} / {market}",
    ]
    ctx_lines.extend(_build_profile_lines(profile))

    ctx_lines.extend(
        [
            "",
            "【价格与趋势】",
            f"- 最近收盘价: {close:.2f}",
            f"- MA5 / MA10 / MA20: {_format_number(meta['ma5'])} / {_format_number(meta['ma10'])} / {_format_number(meta['ma20'])}",
            f"- MA 多头排列(MA5>MA10>MA20): {'是' if trend_ok else '否'}",
            f"- MA20 乖离率: {_format_pct(meta['bias'])}",
            f"- 5/20/60/120 日涨跌幅: {_format_pct(returns['5d'])} / {_format_pct(returns['20d'])} / {_format_pct(returns['60d'])} / {_format_pct(returns['120d'])}",
            f"- 20日年化波动率: {_format_number(volatility_20d, '%')}",
            (
                f"- 20日区间位置: {_format_number(range_20d.get('range_position_pct'), '%')}，"
                f"距20日高点 {_format_pct(range_20d.get('distance_to_high_pct'))}，"
                f"距20日低点 {_format_pct(range_20d.get('distance_to_low_pct'))}"
            ),
            (
                f"- 60日区间位置: {_format_number(range_60d.get('range_position_pct'), '%')}，"
                f"距60日高点 {_format_pct(range_60d.get('distance_to_high_pct'))}，"
                f"距60日低点 {_format_pct(range_60d.get('distance_to_low_pct'))}"
            ),
        ]
    )

    if bias_risk:
        ctx_lines.append(f"- 风险提示: {bias_risk}")

    ctx_lines.extend(["", "【估值与活跃度】"])
    ctx_lines.extend(_build_valuation_lines(profile.get("valuation") or {}))

    ctx_lines.extend(["", "【资金与市场环境】"])
    ctx_lines.extend(_build_capital_flow_lines(capital_flow))

    if market_context:
        calendar = market_context.get("calendar") or {}
        indices = market_context.get("indices") or []
        northbound = market_context.get("northbound") or {}

        trading_status = calendar.get("is_trading_day")
        if trading_status is True:
            ctx_lines.append("- 交易日状态: 今天是 A 股交易日。")
        elif trading_status is False:
            next_day = calendar.get("next_trading_day") or "未知"
            ctx_lines.append(f"- 交易日状态: 今天不是 A 股交易日，下一个交易日为 {next_day}。")

        if indices:
            market_lines: List[str] = []
            for item in indices[:3]:
                name_text = item.get("name") or "指数"
                value = item.get("value")
                pct = item.get("pct_change")
                if value is not None and pct is not None:
                    market_lines.append(f"{name_text} {float(value):.2f} ({float(pct):+.2f}%)")
            if market_lines:
                ctx_lines.append("- 大盘环境: " + "；".join(market_lines))

        if northbound.get("description"):
            ctx_lines.append(f"- {northbound['description']}")

    if market_review_summary:
        breadth = market_review_summary.get("breadth") or {}
        leading_sectors = market_review_summary.get("leading_sectors") or []
        lagging_sectors = market_review_summary.get("lagging_sectors") or []
        ctx_lines.extend(["", "【市场复盘摘要】"])

        breadth_lines: List[str] = []
        if breadth.get("up") is not None and breadth.get("down") is not None:
            breadth_lines.append(f"上涨/下跌家数 {breadth['up']}/{breadth['down']}")
        if breadth.get("advance_decline_ratio") is not None:
            breadth_lines.append(f"涨跌比 {float(breadth['advance_decline_ratio']):.2f}")
        if breadth.get("limit_up") is not None or breadth.get("limit_down") is not None:
            breadth_lines.append(
                f"涨停/跌停 {breadth.get('limit_up') if breadth.get('limit_up') is not None else '暂无'}/"
                f"{breadth.get('limit_down') if breadth.get('limit_down') is not None else '暂无'}"
            )
        if breadth.get("amplitude") is not None:
            breadth_lines.append(f"市场平均振幅 {_format_number(float(breadth['amplitude']), '%')}")
        if breadth.get("turn_rate") is not None:
            breadth_lines.append(f"市场平均换手率 {_format_number(float(breadth['turn_rate']), '%')}")
        if breadth_lines:
            ctx_lines.append("- 市场广度: " + "；".join(breadth_lines))

        if leading_sectors:
            lead_text = "；".join(
                f"{item.get('name', '板块')} {float(item.get('pct_change', 0)):+.2f}%"
                for item in leading_sectors
                if item.get("name") is not None and item.get("pct_change") is not None
            )
            if lead_text:
                ctx_lines.append(f"- 领涨板块: {lead_text}")

        if lagging_sectors:
            lag_text = "；".join(
                f"{item.get('name', '板块')} {float(item.get('pct_change', 0)):+.2f}%"
                for item in lagging_sectors
                if item.get("name") is not None and item.get("pct_change") is not None
            )
            if lag_text:
                ctx_lines.append(f"- 领跌板块: {lag_text}")

    if scanner_summary:
        ctx_lines.extend(["", "【市场扫描摘要】"])
        sample_size = scanner_summary.get("sample_size")
        result_count = scanner_summary.get("result_count")
        if sample_size:
            ctx_lines.append(f"- 扫描样本范围: 约 {sample_size} 只标的，综合策略候选 {result_count or 0} 只。")
        leaders = scanner_summary.get("leaders") or []
        if leaders:
            leader_text = "；".join(
                f"{item.get('ticker')} 第{item.get('rank')}名，评分 {float(item.get('score', 0)):.2f}，{item.get('action', '观望')}"
                for item in leaders[:3]
                if item.get("ticker")
            )
            if leader_text:
                ctx_lines.append(f"- 扫描头部候选: {leader_text}")

        match = (scanner_summary.get("matches") or {}).get(str(ticker).strip().upper())
        if not match:
            normalized = _normalize_ticker_key(ticker, market=market)
            for key, item in (scanner_summary.get("matches") or {}).items():
                if _normalize_ticker_key(key, market=market) == normalized:
                    match = item
                    break
        if match:
            ctx_lines.append(
                f"- 当前标的在本轮扫描中入选: 第{match.get('rank')}名，评分 {_format_number(match.get('score'))}，动作 {match.get('action') or '观望'}。"
            )
            if match.get("reasons"):
                ctx_lines.append(f"- 扫描命中理由: {match['reasons']}")
        else:
            ctx_lines.append("- 当前标的未进入本轮市场扫描头部候选。")

    news_summary = ""
    try:
        from core.search_service import search_news

        max_age = get_news_max_age_days()
        query = f"{ticker} 股票 最新新闻"
        news_items = search_news(query=query, max_age_days=max_age, limit=5)
        if news_items:
            lines = ["", "【新闻与舆情摘要】"]
            for i, news in enumerate(news_items[:3], start=1):
                title = (news.get("title") or "").strip()
                url = news.get("url") or ""
                snippet = (news.get("snippet") or "").strip().replace("\n", " ")
                source = news.get("source") or "新闻"
                if title:
                    if url:
                        lines.append(f"{i}. [{title}]({url}) - {source}")
                    else:
                        lines.append(f"{i}. {title} - {source}")
                if snippet:
                    lines.append(f"   摘要: {snippet}")
            news_summary = "\n".join(lines)
            ctx_lines.append(news_summary)
            meta["news_count"] = len(news_items)
    except Exception as exc:  # pragma: no cover - 搜索失败不影响主流程
        logger.debug("构建新闻上下文失败 (%s): %s", ticker, exc)

    if limitations:
        ctx_lines.extend(["", "【风险与限制】"])
        for item in limitations:
            ctx_lines.append(f"- {item}")

    text_context = "\n".join(ctx_lines)

    return {
        "ticker": ticker,
        "name": name,
        "market": market,
        "meta": meta,
        "analysis_brief": analysis_brief,
        "text_context": text_context,
        "news_summary": news_summary or None,
        "generated_at": datetime.now().isoformat(),
    }

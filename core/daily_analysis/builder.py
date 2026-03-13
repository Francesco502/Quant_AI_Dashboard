from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import numpy as np
import pandas as pd

from core.data_service import load_price_data, identify_asset_type
from core.technical_indicators import calculate_sma
from core import tushare_provider
from .config import get_bias_threshold, get_news_max_age_days


logger = logging.getLogger(__name__)


def _infer_name_from_ticker(ticker: str) -> str:
    """优先使用 Tushare 解析 A 股/基金名称，失败时回退为代码本身。"""
    try:
        name = tushare_provider.get_cn_security_name(ticker)
        if name:
            return name
    except Exception as e:  # pragma: no cover - 容错
        logger.debug("解析标的名称失败 (%s): %s", ticker, e)
    return ticker


def build_analysis_input(ticker: str, market: str = "cn") -> Dict[str, Any]:
    """构建单标的分析输入上下文

    返回结构：
    - ticker / name / market
    - meta：包含最新价格、MA5/10/20、乖离率等
    - text_context：汇总后的自然语言上下文，供 prompt 使用
    """
    days = 365
    price_df = load_price_data([ticker], days=days)
    if price_df is None or price_df.empty or ticker not in price_df.columns:
        raise ValueError(f"无法获取 {ticker} 的历史价格数据")

    series = price_df[ticker].dropna()
    if series.empty:
        raise ValueError(f"{ticker} 历史价格数据为空")

    # 计算基础指标
    close = series.iloc[-1]
    ma5 = calculate_sma(series, 5).iloc[-1]
    ma10 = calculate_sma(series, 10).iloc[-1]
    ma20 = calculate_sma(series, 20).iloc[-1]

    bias = np.nan
    if ma20 and not np.isnan(ma20) and ma20 != 0:
        bias = (close - ma20) / ma20 * 100.0

    trend_ok = False
    if not any(np.isnan(x) for x in (ma5, ma10, ma20)):
        trend_ok = bool(ma5 > ma10 > ma20)

    bias_threshold = get_bias_threshold()
    bias_risk = ""
    if not np.isnan(bias) and bias > bias_threshold:
        bias_risk = f"当前价格相对MA20 乖离率约为 {bias:.2f}%，高于阈值 {bias_threshold:.1f}%，存在追高风险。"

    asset_type = identify_asset_type(ticker)

    meta = {
        "last_close": float(close),
        "ma5": float(ma5) if ma5 == ma5 else None,
        "ma10": float(ma10) if ma10 == ma10 else None,
        "ma20": float(ma20) if ma20 == ma20 else None,
        "bias": float(bias) if bias == bias else None,
        "bias_threshold": bias_threshold,
        "bias_risk": bias_risk if bias_risk else None,
        "trend_ok": trend_ok,
        "asset_type": asset_type,
        "position_summary": None,  # 筹码分布：占位，后续可接入 AkShare/Tushare 等
        "history_start": series.index[0].isoformat() if hasattr(series.index[0], "isoformat") else str(series.index[0]),
        "history_end": series.index[-1].isoformat() if hasattr(series.index[-1], "isoformat") else str(series.index[-1]),
    }

    name = _infer_name_from_ticker(ticker)
    market_context = None
    if market == "cn":
        try:
            market_context = tushare_provider.get_cn_market_context()
            meta["market_context"] = market_context
        except Exception as e:  # pragma: no cover - 容错
            logger.debug("构建市场上下文失败 (%s): %s", ticker, e)

    # 构造给 LLM 的文本上下文（价格 + 技术面）
    ctx_lines = [
        f"标的代码: {ticker}",
        f"标的名称: {name}",
        f"市场类型: {asset_type} / {market}",
        f"最近收盘价: {close:.2f}",
        f"MA5: {ma5:.2f}  MA10: {ma10:.2f}  MA20: {ma20:.2f}",
        f"乖离率(BIAS) 相对 MA20: {bias:.2f}%" if not np.isnan(bias) else "乖离率(BIAS) 无法计算",
        f"均线多头排列(MA5>MA10>MA20): {'是' if trend_ok else '否'}",
    ]
    if bias_risk:
        ctx_lines.append(bias_risk)

    # 简要历史走势描述：近 20/60 日涨跌幅
    def _pct_change(window: int) -> str:
        if len(series) < window + 1:
            return "数据不足"
        pct = (series.iloc[-1] / series.iloc[-window - 1] - 1.0) * 100.0
        return f"{pct:.2f}%"

    ctx_lines.append(f"近20个交易日涨跌幅: {_pct_change(20)}")
    ctx_lines.append(f"近60个交易日涨跌幅: {_pct_change(60)}")

    if market_context:
        calendar = market_context.get("calendar") or {}
        indices = market_context.get("indices") or []
        northbound = market_context.get("northbound") or {}

        trading_status = calendar.get("is_trading_day")
        if trading_status is True:
            ctx_lines.append("当前市场状态: 今天是 A 股交易日。")
        elif trading_status is False:
            next_day = calendar.get("next_trading_day") or "未知"
            ctx_lines.append(f"当前市场状态: 今天不是 A 股交易日，下一个交易日为 {next_day}。")

        if indices:
            lines = []
            for item in indices[:3]:
                name_text = item.get("name") or "指数"
                value = item.get("value")
                pct = item.get("pct_change")
                if value is not None and pct is not None:
                    lines.append(f"{name_text} {value:.2f} ({pct:+.2f}%)")
            if lines:
                ctx_lines.append("大盘环境: " + "；".join(lines))

        if northbound.get("description"):
            ctx_lines.append(str(northbound["description"]))

    # 筹码分布：占位，若有数据可在此注入
    if meta.get("position_summary"):
        ctx_lines.append(f"筹码分布: {meta['position_summary']}")

    # Phase 2：接入新闻 / 舆情摘要（若已配置搜索服务）
    news_summary = ""
    try:
        from core.search_service import search_news

        max_age = get_news_max_age_days()
        query = f"{ticker} 股票 最新新闻"
        news_items = search_news(query=query, max_age_days=max_age, limit=5)
        if news_items:
            lines = ["【新闻与舆情摘要】"]
            for i, n in enumerate(news_items[:3], start=1):
                title = (n.get("title") or "").strip()
                url = n.get("url") or ""
                snippet = (n.get("snippet") or "").strip().replace("\n", " ")
                source = n.get("source") or "新闻"
                if title:
                    if url:
                        lines.append(f"{i}. [{title}]({url}) - {source}")
                    else:
                        lines.append(f"{i}. {title} - {source}")
                if snippet:
                    lines.append(f"   摘要: {snippet}")
            news_summary = "\n".join(lines)
            ctx_lines.append("")
            ctx_lines.append(news_summary)
            meta["news_count"] = len(news_items)
    except Exception as e:  # pragma: no cover - 搜索失败不影响主流程
        logger.debug("构建新闻上下文失败 (%s): %s", ticker, e)

    text_context = "\n".join(ctx_lines)

    return {
        "ticker": ticker,
        "name": name,
        "market": market,
        "meta": meta,
        "text_context": text_context,
        "news_summary": news_summary or None,
        "generated_at": datetime.now().isoformat(),
    }


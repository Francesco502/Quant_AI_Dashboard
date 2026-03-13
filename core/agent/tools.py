"""Agent 工具抽象与基础金融工具实现（Dexter 风格精简版）"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

import logging

import pandas as pd

from core.data_service import load_price_data
from core.market_review import daily_review
from core.search_service import search_news
from core import tushare_provider
from core.daily_analysis import run_daily_analysis
from core.daily_analysis.backtest import backtest_ticker


logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """单次工具调用的结果"""

    name: str
    args: Dict[str, Any]
    data: Dict[str, Any]


class BaseTool:
    """Agent 工具基类"""

    name: str
    description: str

    def run(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError


class PriceTool(BaseTool):
    """价格与基础技术指标工具"""

    name = "price"
    description = (
        "获取单只标的在指定天数内的收盘价序列和基础指标。"
        "适用于需要了解历史走势、涨跌幅、近期价格区间的场景。"
    )

    def run(self, *, ticker: str, days: int = 120) -> ToolResult:
        args = {"ticker": ticker, "days": days}
        try:
            df = load_price_data([ticker], days=days)
            series = df[ticker].dropna() if ticker in df.columns else pd.Series(dtype=float)
            if series.empty:
                data: Dict[str, Any] = {"error": f"no price data for {ticker}", "ticker": ticker}
            else:
                series = series.sort_index()
                points: List[Dict[str, Any]] = []
                for idx, val in series.items():
                    date_str = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
                    points.append({"date": date_str, "close": float(val)})
                data = {
                    "ticker": ticker,
                    "days": days,
                    "start_date": points[0]["date"],
                    "end_date": points[-1]["date"],
                    "last_close": float(series.iloc[-1]),
                    "series": points,
                }
        except Exception as e:
            logger.warning("PriceTool 失败: %s", e)
            data = {"error": str(e), "ticker": ticker}

        return ToolResult(name=self.name, args=args, data=data)


class MarketReviewTool(BaseTool):
    """大盘复盘工具"""

    name = "market_review"
    description = (
        "按市场类型（cn/us/both）获取大盘指数、涨跌概况、板块信息与北向资金等。"
        "适用于需要整体市场环境判断的场景。"
    )

    def run(self, *, market: str = "cn") -> ToolResult:
        args = {"market": market}
        try:
            data = daily_review(market=market)  # type: ignore[arg-type]
        except Exception as e:
            logger.warning("MarketReviewTool 失败: %s", e)
            data = {"error": str(e), "market": market}
        return ToolResult(name=self.name, args=args, data=data)


class NewsSearchTool(BaseTool):
    """新闻 / 舆情搜索工具"""

    name = "news"
    description = (
        "基于 Tavily 等数据源，搜索与指定标的相关的近期新闻与舆情摘要。"
        "适用于评估事件驱动风险、情绪变化等场景。"
    )

    def run(self, *, ticker: str, days: int = 3, limit: int = 5) -> ToolResult:
        args = {"ticker": ticker, "days": days, "limit": limit}
        try:
            query = f"{ticker} 股票 最新新闻"
            items = search_news(query=query, max_age_days=days, limit=limit)
            data: Dict[str, Any] = {
                "ticker": ticker,
                "days": days,
                "items": items,
            }
        except Exception as e:
            logger.warning("NewsSearchTool 失败: %s", e)
            data = {"error": str(e), "ticker": ticker}
        return ToolResult(name=self.name, args=args, data=data)


class DailyDecisionTool(BaseTool):
    """高阶决策工具：复用现有 daily_analysis 能力"""

    name = "daily_decision"
    description = (
        "调用现有 daily_analysis 流程，对单只标的进行完整的技术+舆情决策分析，"
        "输出结论、操作建议与风险提示。"
    )

    def run(self, *, ticker: str, market: str = "cn", model: str | None = None) -> ToolResult:
        args = {"ticker": ticker, "market": market, "model": model}
        try:
            out = run_daily_analysis(tickers=[ticker], market=market, include_market_review=False, model=model)
            results = out.get("results") or []
            first = results[0] if results else {}
            data: Dict[str, Any] = {
                "ticker": ticker,
                "market": market,
                "decision": first.get("decision") or {},
                "meta": first.get("meta") or {},
            }
        except Exception as e:
            logger.warning("DailyDecisionTool 失败: %s", e)
            data = {"error": str(e), "ticker": ticker, "market": market}
        return ToolResult(name=self.name, args=args, data=data)


class TradingContextTool(BaseTool):
    """交易上下文工具：提供标的名称与 A 股市场环境。"""

    name = "trading_context"
    description = (
        "返回标的基础身份信息、A 股是否交易日、下一个交易日、主要指数与北向资金摘要。"
        "适用于在生成结论前先建立结构化市场上下文，减少凭空猜测。"
    )

    def run(self, *, ticker: str, market: str = "cn") -> ToolResult:
        args = {"ticker": ticker, "market": market}
        try:
            data: Dict[str, Any] = {
                "ticker": ticker,
                "market": market,
                "name": tushare_provider.get_cn_security_name(ticker) or ticker,
                "market_context": tushare_provider.get_cn_market_context() if market == "cn" else {},
            }
        except Exception as e:
            logger.warning("TradingContextTool 失败: %s", e)
            data = {"error": str(e), "ticker": ticker, "market": market}
        return ToolResult(name=self.name, args=args, data=data)


class BacktestTool(BaseTool):
    """基于历史 LLM 决策的回测工具"""

    name = "backtest"
    description = (
        "对指定标的的历史 LLM 决策进行回测，"
        "返回方向胜率、止盈/止损命中率等指标，以及每次决策的评估明细。"
    )

    def run(self, *, ticker: str, horizon_days: int = 5) -> ToolResult:
        args = {"ticker": ticker, "horizon_days": horizon_days}
        try:
            data = backtest_ticker(ticker=ticker, horizon_days=horizon_days)
        except Exception as e:
            logger.warning("BacktestTool 失败: %s", e)
            data = {"error": str(e), "ticker": ticker}
        return ToolResult(name=self.name, args=args, data=data)


class FundamentalsTool(BaseTool):
    """基本面/估值信息工具（预留占位，待接入财报/估值数据源）"""

    name = "fundamentals"
    description = (
        "预留的基本面与估值数据工具，未来可接入财报、估值指标等数据源。"
        "当前实现返回占位结果，仅用于让 Agent 知道该能力尚未开通。"
    )

    def run(self, *, ticker: str) -> ToolResult:
        args = {"ticker": ticker}
        data: Dict[str, Any] = {
            "ticker": ticker,
            "error": "FundamentalsTool 尚未接入实际数据源，当前仅为占位实现。",
        }
        return ToolResult(name=self.name, args=args, data=data)


def get_default_tools() -> Mapping[str, BaseTool]:
    """返回默认可用工具映射：name -> 实例"""
    tools: List[BaseTool] = [
        PriceTool(),
        TradingContextTool(),
        MarketReviewTool(),
        NewsSearchTool(),
        DailyDecisionTool(),
        BacktestTool(),
        FundamentalsTool(),
    ]
    return {t.name: t for t in tools}


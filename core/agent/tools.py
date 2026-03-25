"""Agent tools used by the lightweight research agent."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Mapping

import pandas as pd

from core import tushare_provider
from core.daily_analysis import run_daily_analysis
from core.daily_analysis.backtest import backtest_ticker
from core.data_service import load_price_data
from core.market_review import daily_review
from core.search_service import search_news


logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    name: str
    args: Dict[str, Any]
    data: Dict[str, Any]


class BaseTool:
    name: str
    description: str

    def run(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError


class PriceTool(BaseTool):
    name = "price"
    description = "Get close-price history and simple price context for one ticker."

    def run(self, *, ticker: str, days: int = 120) -> ToolResult:
        args = {"ticker": ticker, "days": days}
        try:
            df = load_price_data([ticker], days=days)
            series = df[ticker].dropna() if ticker in df.columns else pd.Series(dtype=float)
            if series.empty:
                data: Dict[str, Any] = {"error": f"no price data for {ticker}", "ticker": ticker}
            else:
                series = series.sort_index()
                data = {
                    "ticker": ticker,
                    "days": days,
                    "start_date": series.index[0].isoformat() if hasattr(series.index[0], "isoformat") else str(series.index[0]),
                    "end_date": series.index[-1].isoformat() if hasattr(series.index[-1], "isoformat") else str(series.index[-1]),
                    "last_close": float(series.iloc[-1]),
                    "series": [
                        {
                            "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                            "close": float(val),
                        }
                        for idx, val in series.items()
                    ],
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("PriceTool failed: %s", exc)
            data = {"error": str(exc), "ticker": ticker}
        return ToolResult(name=self.name, args=args, data=data)


class MarketReviewTool(BaseTool):
    name = "market_review"
    description = "Get a structured market review for cn/hk/us."

    def run(self, *, market: str = "cn") -> ToolResult:
        args = {"market": market}
        try:
            data = daily_review(market=market)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            logger.warning("MarketReviewTool failed: %s", exc)
            data = {"error": str(exc), "market": market}
        return ToolResult(name=self.name, args=args, data=data)


class NewsSearchTool(BaseTool):
    name = "news"
    description = "Search recent ticker-related news and sentiment summaries."

    def run(self, *, ticker: str, days: int = 3, limit: int = 5) -> ToolResult:
        args = {"ticker": ticker, "days": days, "limit": limit}
        try:
            data = {
                "ticker": ticker,
                "days": days,
                "items": search_news(query=f"{ticker} 股票 最新新闻", max_age_days=days, limit=limit),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("NewsSearchTool failed: %s", exc)
            data = {"error": str(exc), "ticker": ticker}
        return ToolResult(name=self.name, args=args, data=data)


class DailyDecisionTool(BaseTool):
    name = "daily_decision"
    description = "Run the existing daily LLM analysis flow for one ticker."

    def run(self, *, ticker: str, market: str = "cn", model: str | None = None) -> ToolResult:
        args = {"ticker": ticker, "market": market, "model": model}
        try:
            out = run_daily_analysis(tickers=[ticker], market=market, include_market_review=False, model=model)
            results = out.get("results") or []
            first = results[0] if results else {}
            data = {
                "ticker": ticker,
                "market": market,
                "decision": first.get("decision") or {},
                "meta": first.get("meta") or {},
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("DailyDecisionTool failed: %s", exc)
            data = {"error": str(exc), "ticker": ticker, "market": market}
        return ToolResult(name=self.name, args=args, data=data)


class TradingContextTool(BaseTool):
    name = "trading_context"
    description = "Get trading-day context and a small market snapshot for one ticker."

    def run(self, *, ticker: str, market: str = "cn") -> ToolResult:
        args = {"ticker": ticker, "market": market}
        try:
            data = {
                "ticker": ticker,
                "market": market,
                "name": tushare_provider.get_cn_security_name(ticker) or ticker,
                "market_context": tushare_provider.get_cn_market_context() if market == "cn" else {},
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("TradingContextTool failed: %s", exc)
            data = {"error": str(exc), "ticker": ticker, "market": market}
        return ToolResult(name=self.name, args=args, data=data)


class BacktestTool(BaseTool):
    name = "backtest"
    description = "Backtest historical LLM decisions for one ticker."

    def run(self, *, ticker: str, horizon_days: int = 5) -> ToolResult:
        args = {"ticker": ticker, "horizon_days": horizon_days}
        try:
            data = backtest_ticker(ticker=ticker, horizon_days=horizon_days)
        except Exception as exc:  # noqa: BLE001
            logger.warning("BacktestTool failed: %s", exc)
            data = {"error": str(exc), "ticker": ticker}
        return ToolResult(name=self.name, args=args, data=data)


class FundamentalsTool(BaseTool):
    name = "fundamentals"
    description = "Get a basic A-share profile plus latest valuation fields when Tushare is configured."

    def run(self, *, ticker: str) -> ToolResult:
        args = {"ticker": ticker}
        try:
            profile = tushare_provider.get_cn_security_profile(ticker)
            if profile:
                data: Dict[str, Any] = profile
            else:
                data = {
                    "ticker": ticker,
                    "error": "No fundamentals data available. Configure TUSHARE_TOKEN to enable profile and valuation lookups.",
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("FundamentalsTool failed: %s", exc)
            data = {"ticker": ticker, "error": str(exc)}
        return ToolResult(name=self.name, args=args, data=data)


def get_default_tools() -> Mapping[str, BaseTool]:
    tools: List[BaseTool] = [
        PriceTool(),
        TradingContextTool(),
        MarketReviewTool(),
        NewsSearchTool(),
        DailyDecisionTool(),
        BacktestTool(),
        FundamentalsTool(),
    ]
    return {tool.name: tool for tool in tools}

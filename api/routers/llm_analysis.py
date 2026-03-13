"""LLM analysis API routes."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from core import llm_client, market_review
from core.daily_analysis import run_daily_analysis, run_daily_analysis_from_env
from core.daily_analysis.backtest import backtest_ticker
from core.data_service import load_price_data


router = APIRouter()


@router.get("/config")
async def llm_config() -> Dict[str, Any]:
    """Return active provider/model settings for frontend display."""
    if os.getenv("LLM_PROVIDER", "").strip().lower() == "gemini" and os.getenv("GEMINI_API_KEY"):
        return {
            "provider": "gemini",
            "model": os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
        }

    return {
        "provider": "openai_compat",
        "model": os.getenv("OPENAI_MODEL") or os.getenv("DASHSCOPE_MODEL") or llm_client.DEFAULT_OPENAI_MODEL,
        "base_url": os.getenv("OPENAI_BASE_URL") or os.getenv("DASHSCOPE_BASE_URL") or llm_client.DEFAULT_OPENAI_COMPAT_BASE_URL,
    }


class DashboardRequest(BaseModel):
    tickers: List[str] = Field(..., description="Ticker list.")
    market: str = Field("cn", description="Market: cn/hk/us")
    include_market_review: bool = Field(False, description="Attach market review in response.")
    model: Optional[str] = Field(None, description="Optional model override.")


@router.post("/dashboard")
async def dashboard(req: DashboardRequest) -> Dict[str, Any]:
    """Run multi-ticker decision dashboard analysis."""
    if not req.tickers:
        raise HTTPException(status_code=400, detail="tickers cannot be empty")
    try:
        return run_daily_analysis(
            tickers=req.tickers,
            market=req.market,
            include_market_review=req.include_market_review,
            model=req.model,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Decision analysis failed: {exc}") from exc


class RunDailyRequest(BaseModel):
    tickers: Optional[List[str]] = Field(None, description="Optional ticker override list.")


@router.post("/run-daily")
async def run_daily(
    req: Optional[RunDailyRequest] = Body(None),
    push: bool = Query(True, description="Whether to send configured notifications."),
) -> Dict[str, Any]:
    """Run daily analysis once."""
    try:
        tickers = (req.tickers if req else None) or None
        if tickers:
            return run_daily_analysis(tickers=tickers, include_market_review=True)
        return run_daily_analysis_from_env(include_market_review=True, send_push=push)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Run daily analysis failed: {exc}") from exc


@router.get("/backtest")
async def backtest(
    ticker: str,
    horizon_days: int = 5,
) -> Dict[str, Any]:
    """Backtest LLM decisions for one ticker."""
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker cannot be empty")
    try:
        return backtest_ticker(ticker=ticker, horizon_days=horizon_days)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}") from exc


class NaturalQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language question.")


def _extract_json(text: str) -> str:
    raw = text.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    return raw


@router.post("/natural-query")
async def natural_query(req: NaturalQueryRequest) -> Dict[str, Any]:
    """Natural language entrypoint for lightweight financial Q&A."""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query cannot be empty")

    messages = [
        {
            "role": "system",
            "content": (
                "Convert user query into JSON with keys: ticker, market, intent, days. "
                "intent must be one of decision, price_trend, market_review."
            ),
        },
        {"role": "user", "content": query},
    ]

    try:
        parsed = json.loads(_extract_json(llm_client.chat_completion(messages)))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Intent parsing failed: {exc}") from exc

    intent = str(parsed.get("intent") or "decision").strip().lower()
    ticker = str(parsed.get("ticker") or "").strip()
    market = str(parsed.get("market") or "cn").strip().lower()
    try:
        days = int(parsed.get("days") or 60)
    except Exception:
        days = 60

    response: Dict[str, Any] = {
        "query": query,
        "parsed": {"ticker": ticker, "market": market, "intent": intent, "days": days},
    }

    if intent in ("decision", "analysis", "price_trend"):
        if not ticker:
            raise HTTPException(status_code=400, detail="ticker is required for decision/price trend")
        try:
            response["analysis"] = run_daily_analysis(
                tickers=[ticker],
                market=market,
                include_market_review=False,
            )
        except Exception as exc:  # noqa: BLE001
            response["analysis_error"] = str(exc)

        if intent == "price_trend":
            try:
                frame = load_price_data([ticker], days=days)
                series = frame[ticker].dropna() if ticker in frame.columns else None
                if series is not None and not series.empty:
                    points = [
                        {
                            "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                            "close": float(val),
                        }
                        for idx, val in series.items()
                    ]
                    response["price_trend"] = {
                        "last_close": float(series.iloc[-1]),
                        "start_date": points[0]["date"],
                        "end_date": points[-1]["date"],
                        "series": points,
                    }
            except Exception as exc:  # noqa: BLE001
                response["price_trend_error"] = str(exc)
    elif intent == "market_review":
        try:
            response["market_review"] = market_review.daily_review(market=market)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            response["market_review_error"] = str(exc)
    else:
        response["warning"] = f"Unknown intent: {intent}"

    return response

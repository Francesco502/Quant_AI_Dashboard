"""Market review API routes — daily broad-market summary and shared analysis context."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from core.market_review import daily_review
from core.daily_analysis import builder


class MarketType(str, Enum):
    cn = "cn"
    us = "us"
    both = "both"


router = APIRouter()


def _build_daily_market_review(market: str) -> Dict[str, Any]:
    data = daily_review(market=market)
    shared_context = builder.build_shared_analysis_context([], market=market)
    data["shared_context"] = {
        "market_review_summary": shared_context.get("market_review_summary"),
        "scanner_summary": shared_context.get("scanner_summary"),
        "limitations": shared_context.get("limitations") or [],
    }
    return data


@router.get("/daily-review")
async def daily_market_review(
    market: MarketType = Query(MarketType.cn, description="Target market: cn, us, or both"),
) -> Dict[str, Any]:
    """Return a structured daily broad-market review for the selected market.

    The response includes index performance, breadth indicators, sector flows,
    and a shared analysis context suitable for downstream LLM consumption.
    """
    try:
        return await run_in_threadpool(_build_daily_market_review, market.value)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market review: {e}")

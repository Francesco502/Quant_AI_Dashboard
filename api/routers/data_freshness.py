"""Data freshness routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.auth import UserInDB, get_current_active_user
from core.data_freshness import get_price_freshness_batch


router = APIRouter(prefix="/data-freshness", tags=["数据新鲜度"])


class DataFreshnessItem(BaseModel):
    ticker: str
    source: str = "unknown"
    status: str
    is_stale: bool = False
    should_block: bool = False
    last_date: Optional[str] = None
    age_days: Optional[int] = None
    message: str = ""


class DataFreshnessResponse(BaseModel):
    status: str
    count: int
    stale_count: int
    items: List[DataFreshnessItem]


@router.get("/prices", response_model=DataFreshnessResponse)
async def get_price_data_freshness(
    tickers: str = Query(..., description="Comma separated tickers"),
    max_age_days: int = Query(default=5, ge=0, le=60),
    current_user: UserInDB = Depends(get_current_active_user),
) -> DataFreshnessResponse:
    del current_user
    ticker_list = [item.strip().upper() for item in tickers.split(",") if item.strip()]
    freshness = get_price_freshness_batch(ticker_list, max_age_days=max_age_days)
    items = [freshness[ticker] for ticker in ticker_list if ticker in freshness]
    return {
        "status": "success",
        "count": len(items),
        "stale_count": sum(1 for item in items if item.get("is_stale")),
        "items": items,
    }

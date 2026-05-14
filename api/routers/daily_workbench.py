"""Daily decision workbench routes."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import UserInDB, get_current_active_user
from core.daily_workbench import build_daily_workbench_snapshot


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/daily-workbench", tags=["日常决策工作台"])


class DataFreshnessItem(BaseModel):
    ticker: str
    source: str = "unknown"
    status: str
    is_stale: bool = False
    should_block: bool = False
    last_date: Optional[str] = None
    age_days: Optional[int] = None
    message: str = ""


class AssetSummary(BaseModel):
    asset_count: int
    total_market_value: float
    tickers: List[str]


class DataFreshnessSummary(BaseModel):
    stale_count: int
    items: List[DataFreshnessItem]


class PaperAccountSummary(BaseModel):
    found: bool
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    total_assets: float
    cash: float
    position_value: float
    recent_order_count: int
    recent_trade_count: int


class WorkbenchCard(BaseModel):
    href: str
    status: str
    description: str


class WorkbenchAction(BaseModel):
    kind: str
    title: str
    description: str
    href: str
    priority: str


class DailyWorkbenchSummaryResponse(BaseModel):
    as_of: str
    asset_summary: AssetSummary
    data_freshness: DataFreshnessSummary
    paper_account: PaperAccountSummary
    market_review: WorkbenchCard
    scan_summary: WorkbenchCard
    backtest_summary: WorkbenchCard
    next_actions: List[WorkbenchAction]


@router.get("/summary", response_model=DailyWorkbenchSummaryResponse)
async def get_daily_workbench_summary(
    current_user: UserInDB = Depends(get_current_active_user),
) -> DailyWorkbenchSummaryResponse:
    try:
        if current_user.id is None:
            raise HTTPException(status_code=401, detail="Unable to resolve current user id")
        return build_daily_workbench_snapshot(user_id=int(current_user.id))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to build daily workbench summary: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

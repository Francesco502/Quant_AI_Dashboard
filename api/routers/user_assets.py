"""User asset ledger routes."""

from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import UserInDB, get_current_active_user
from core.user_assets import get_user_asset_service


logger = logging.getLogger(__name__)
router = APIRouter()


def _require_user_id(current_user: UserInDB) -> int:
    user_id = getattr(current_user, "id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Unable to resolve current user id")
    return int(user_id)


class DcaRuleRequest(BaseModel):
    enabled: bool = False
    frequency: Literal["weekly", "monthly"] = "weekly"
    weekday: Optional[int] = Field(default=None, ge=0, le=6)
    monthday: Optional[int] = Field(default=None, ge=1, le=31)
    amount: float = Field(default=0.0, ge=0.0)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    shift_to_next_trading_day: bool = True


class AssetUpsertRequest(BaseModel):
    ticker: str
    asset_name: Optional[str] = None
    asset_category: Optional[str] = None
    asset_style: Optional[str] = None
    asset_type: Optional[str] = None
    units: float = Field(default=0.0, ge=0.0)
    avg_cost: float = Field(default=0.0, ge=0.0)
    trade_date: Optional[str] = None
    notes: Optional[str] = None
    dca_rule: Optional[DcaRuleRequest] = None


class AssetTransactionRequest(BaseModel):
    transaction_type: Literal["BUY", "SELL", "ADJUSTMENT_IN", "ADJUSTMENT_OUT"] = "BUY"
    quantity: float = Field(..., gt=0)
    price: float = Field(default=0.0, ge=0.0)
    amount: Optional[float] = Field(default=None, ge=0.0)
    fee: float = Field(default=0.0, ge=0.0)
    trade_date: Optional[str] = None
    note: Optional[str] = None


@router.get("/assets")
async def get_asset_overview(
    sync_dca: bool = Query(True, description="Whether to auto-apply due DCA rules."),
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        return get_user_asset_service().get_overview(user_id, sync_dca=sync_dca)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get user asset overview: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/assets")
async def upsert_asset(
    request: AssetUpsertRequest,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        payload: Dict[str, Any] = request.model_dump()
        if request.dca_rule is not None:
            payload["dca_rule"] = request.dca_rule.model_dump()
        return get_user_asset_service().upsert_asset(user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to upsert user asset: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/assets/{ticker}")
async def update_asset(
    ticker: str,
    request: AssetUpsertRequest,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        payload: Dict[str, Any] = request.model_dump()
        if request.dca_rule is not None:
            payload["dca_rule"] = request.dca_rule.model_dump()
        return get_user_asset_service().update_asset(user_id, ticker, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to update user asset: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/assets/{ticker}")
async def delete_asset(
    ticker: str,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        deleted = get_user_asset_service().delete_asset(user_id, ticker)
        return {"success": deleted, "ticker": ticker}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to delete user asset: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/assets/transactions")
async def list_transactions(
    ticker: Optional[str] = Query(default=None),
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        items = get_user_asset_service().list_transactions(user_id, ticker=ticker)
        return {"transactions": items, "count": len(items)}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to list asset transactions: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/assets/{ticker}/transactions")
async def add_transaction(
    ticker: str,
    request: AssetTransactionRequest,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        payload = request.model_dump()
        return get_user_asset_service().add_transaction(user_id, ticker, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to add asset transaction: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/assets/reconcile")
async def reconcile_due_dca(
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        result = get_user_asset_service().reconcile_due_dca(user_id)
        overview = get_user_asset_service().get_overview(user_id, sync_dca=False)
        return {"reconcile": result, **overview}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to reconcile DCA rules: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

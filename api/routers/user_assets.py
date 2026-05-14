"""User asset ledger routes."""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from api.auth import UserInDB, get_current_active_user
from core.review_audit import get_review_audit_service
from core.user_assets import get_user_asset_service


logger = logging.getLogger(__name__)
router = APIRouter()


def _require_user_id(current_user: UserInDB) -> int:
    user_id = getattr(current_user, "id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Unable to resolve current user id")
    return int(user_id)


def _record_asset_audit(
    current_user: UserInDB,
    *,
    action: str,
    resource: str,
    resource_type: str = "user_asset",
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
) -> None:
    try:
        get_review_audit_service().record_event(
            user=current_user.username,
            action=action,
            resource=resource,
            resource_type=resource_type,
            details=details or {},
            success=success,
            error_message=error_message,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to write asset audit event", exc_info=True)


def _parse_csv_float(value: Any, default: float = 0.0) -> float:
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value: {value}") from exc


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
    sync_dca: bool = Query(False, description="Whether to auto-apply due DCA rules."),
    refresh_market: bool = Query(False, description="Whether to refresh external market quotes now."),
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        service = get_user_asset_service()
        return await run_in_threadpool(
            service.get_overview,
            user_id,
            sync_dca=sync_dca,
            force_refresh=refresh_market,
            refresh_market=refresh_market,
        )
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
        result = get_user_asset_service().upsert_asset(user_id, payload)
        _record_asset_audit(
            current_user,
            action="USER_ASSET_UPSERT",
            resource=request.ticker,
            details={"units": request.units, "avg_cost": request.avg_cost, "asset_type": request.asset_type},
        )
        return result
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
        result = get_user_asset_service().update_asset(user_id, ticker, payload)
        _record_asset_audit(
            current_user,
            action="USER_ASSET_UPDATE",
            resource=ticker,
            details={"next_ticker": request.ticker, "units": request.units, "avg_cost": request.avg_cost},
        )
        return result
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
        _record_asset_audit(
            current_user,
            action="USER_ASSET_DELETE",
            resource=ticker,
            details={"deleted": deleted},
            success=deleted,
        )
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


@router.post("/assets/import-csv")
async def import_assets_csv(
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        raw = await file.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("gbk")

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "ticker" not in {name.strip() for name in reader.fieldnames if name}:
            raise HTTPException(status_code=400, detail="CSV must include a ticker column")

        service = get_user_asset_service()
        imported_count = 0
        errors = []

        for line_no, row in enumerate(reader, start=2):
            ticker = str(row.get("ticker") or "").strip().upper()
            if not ticker:
                errors.append({"line": line_no, "error": "ticker is required"})
                continue
            try:
                payload = {
                    "ticker": ticker,
                    "asset_name": (row.get("asset_name") or row.get("name") or ticker).strip(),
                    "asset_category": (row.get("asset_category") or "").strip() or None,
                    "asset_style": (row.get("asset_style") or "").strip() or None,
                    "asset_type": (row.get("asset_type") or "").strip() or None,
                    "units": _parse_csv_float(row.get("units"), 0.0),
                    "avg_cost": _parse_csv_float(row.get("avg_cost"), 0.0),
                    "trade_date": (row.get("trade_date") or "").strip() or None,
                    "notes": (row.get("notes") or "").strip() or None,
                }
                service.upsert_asset(user_id, payload)
                imported_count += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({"line": line_no, "ticker": ticker, "error": str(exc)})

        overview = service.get_overview(user_id, sync_dca=False)
        _record_asset_audit(
            current_user,
            action="USER_ASSET_IMPORT_CSV",
            resource=file.filename or "assets.csv",
            details={"imported_count": imported_count, "error_count": len(errors)},
            success=imported_count > 0,
            error_message=None if imported_count > 0 else "No assets imported",
        )
        return {"imported_count": imported_count, "errors": errors, **overview}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to import user assets csv: %s", exc, exc_info=True)
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
        result = get_user_asset_service().add_transaction(user_id, ticker, payload)
        _record_asset_audit(
            current_user,
            action="USER_ASSET_TRANSACTION",
            resource=ticker,
            resource_type="user_asset_transaction",
            details={
                "transaction_type": request.transaction_type,
                "quantity": request.quantity,
                "price": request.price,
                "amount": request.amount,
            },
        )
        return result
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
        _record_asset_audit(
            current_user,
            action="USER_ASSET_RECONCILE_DCA",
            resource="dca",
            details=result,
        )
        return {"reconcile": result, **overview}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to reconcile DCA rules: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

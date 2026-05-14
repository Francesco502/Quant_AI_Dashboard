"""External market data routes."""

from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.auth import UserInDB
from api.dependencies import require_permission
from core.data_service import (
    get_economic_summary,
    get_external_features,
    get_flow_summary,
    get_industry_summary,
    get_sentiment_summary,
    load_external_data,
    load_price_data,
    merge_price_with_external,
)
from core.rbac import Permission


router = APIRouter()


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            return _to_jsonable(value.item())
        except Exception:  # noqa: BLE001
            return value
    if hasattr(value, "isoformat") and callable(getattr(value, "isoformat")):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            return value
    return value


class ExternalDataRequest(BaseModel):
    economic: bool = True
    industry: bool = True
    sentiment: bool = True
    flow: bool = True
    start_date: str = Query("2010-01-01", description="Start date")
    end_date: str | None = Query(None, description="End date")


@router.get("/economic", deprecated=True)
async def get_economic_data(
    start_date: str = Query("2010-01-01", description="Start date"),
    end_date: str | None = Query(None, description="End date"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    try:
        return {"data": _to_jsonable(get_economic_summary(start_date=start_date, end_date=end_date))}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load economic data: {exc}") from exc


@router.get("/industry", deprecated=True)
async def get_industry_data(
    start_date: str = Query("2010-01-01", description="Start date"),
    end_date: str | None = Query(None, description="End date"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    try:
        return {"data": _to_jsonable(get_industry_summary(start_date=start_date, end_date=end_date))}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load industry data: {exc}") from exc


@router.get("/sentiment", deprecated=True)
async def get_sentiment_data(
    start_date: str = Query("2010-01-01", description="Start date"),
    end_date: str | None = Query(None, description="End date"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    try:
        return {"data": _to_jsonable(get_sentiment_summary(start_date=start_date, end_date=end_date))}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load sentiment data: {exc}") from exc


@router.get("/flow", deprecated=True)
async def get_flow_data(
    start_date: str = Query("2010-01-01", description="Start date"),
    end_date: str | None = Query(None, description="End date"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    try:
        return {"data": _to_jsonable(get_flow_summary(start_date=start_date, end_date=end_date))}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load flow data: {exc}") from exc


@router.post("/all", deprecated=True)
async def get_all_external_data(
    request: ExternalDataRequest,
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    try:
        external_data = load_external_data(
            economic=request.economic,
            industry=request.industry,
            sentiment=request.sentiment,
            flow=request.flow,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        return {"data": _to_jsonable(external_data)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load external data: {exc}") from exc


@router.post("/merge", deprecated=True)
async def merge_price_with_external_data(
    request: ExternalDataRequest,
    tickers: List[str] = Query(..., description="Tickers to merge"),
    days: int = Query(365, description="Price lookback days"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    try:
        price_df = load_price_data(tickers=tickers, days=days)
        if price_df.empty:
            raise HTTPException(status_code=400, detail="Unable to load price data.")

        external_data = load_external_data(
            economic=request.economic,
            industry=request.industry,
            sentiment=request.sentiment,
            flow=request.flow,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        merged_df = merge_price_with_external(
            price_df=price_df,
            external_data=external_data,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        return {"data": merged_df.to_dict(orient="split")}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to merge external data: {exc}") from exc


@router.post("/features", deprecated=True)
async def get_external_features_endpoint(
    request: ExternalDataRequest,
    tickers: List[str] = Query(..., description="Tickers"),
    days: int = Query(365, description="Price lookback days"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    try:
        price_df = load_price_data(tickers=tickers, days=days)
        if price_df.empty:
            raise HTTPException(status_code=400, detail="Unable to load price data.")

        features_df = get_external_features(price_df, start_date=request.start_date, end_date=request.end_date)
        return {"data": features_df.to_dict(orient="split")}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to build external features: {exc}") from exc

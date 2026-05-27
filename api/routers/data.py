"""
数据获取 API 路由
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from starlette.concurrency import run_in_threadpool
from api.dependencies import require_permission, log_access
from api.auth import get_current_active_user, UserInDB
from core.rbac import Permission
from core.audit_log import AuditAction
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import math
import pandas as pd

from core.data_service import load_price_data, load_ohlcv_data

router = APIRouter()

MAX_DATA_TICKERS = 100
MAX_DATA_DAYS = 3650


class DataRequest(BaseModel):
    """数据请求模型"""
    tickers: List[str] = Field(..., min_length=1, max_length=MAX_DATA_TICKERS)
    days: int = Field(365, ge=1, le=MAX_DATA_DAYS)
    data_sources: Optional[List[str]] = None
    alpha_vantage_key: Optional[str] = None
    tushare_token: Optional[str] = None


def _serialize_price_points(series: pd.Series) -> List[dict]:
    points: List[dict] = []
    for date, price in series.items():
        try:
            numeric_price = float(price)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric_price):
            continue
        points.append({"date": str(date), "price": numeric_price})
    return points


def _reject_client_api_keys(request: DataRequest) -> None:
    if request.alpha_vantage_key or request.tushare_token:
        raise HTTPException(
            status_code=400,
            detail="数据源 API Key 只能通过后端环境变量配置，不能由客户端请求传入。",
        )


def _parse_ticker_query(tickers: str) -> List[str]:
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="至少提供一个标的代码")
    if len(ticker_list) > MAX_DATA_TICKERS:
        raise HTTPException(status_code=400, detail=f"标的数量不能超过 {MAX_DATA_TICKERS}")
    return ticker_list


@router.post("/prices", deprecated=True)
async def get_prices(
    request: DataRequest,
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA))
):
    """获取价格数据（需要VIEW_DATA权限）"""
    del current_user
    try:
        _reject_client_api_keys(request)
        price_data = await run_in_threadpool(
            load_price_data,
            tickers=request.tickers,
            days=request.days,
            data_sources=request.data_sources,
        )

        if price_data is None or price_data.empty:
            raise HTTPException(status_code=400, detail="无法加载价格数据")

        # 转换为字典格式
        result = {}
        for ticker in price_data.columns:
            result[ticker] = _serialize_price_points(price_data[ticker])

        return {
            "data": result,
            "tickers": list(price_data.columns),
            "date_range": {
                "start": str(price_data.index.min()),
                "end": str(price_data.index.max()),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取价格数据失败: {str(e)}")


@router.get("/prices")
async def get_prices_get(
    tickers: str = Query(..., description="标的代码，逗号分隔"),
    days: int = Query(365, ge=1, le=MAX_DATA_DAYS, description="历史天数"),
    data_sources: Optional[str] = Query(None, description="数据源，逗号分隔"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """获取价格数据（GET方式）"""
    del current_user
    try:
        ticker_list = _parse_ticker_query(tickers)
        data_source_list = (
            [s.strip() for s in data_sources.split(",")] if data_sources else ["AkShare"]
        )

        price_data = await run_in_threadpool(
            load_price_data,
            tickers=ticker_list, days=days, data_sources=data_source_list
        )

        if price_data is None or price_data.empty:
            raise HTTPException(status_code=400, detail="无法加载价格数据")

        result = {}
        for ticker in price_data.columns:
            result[ticker] = _serialize_price_points(price_data[ticker])

        return {
            "data": result,
            "tickers": list(price_data.columns),
            "date_range": {
                "start": str(price_data.index.min()),
                "end": str(price_data.index.max()),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取价格数据失败: {str(e)}")


@router.post("/ohlcv", deprecated=True)
async def get_ohlcv(
    request: DataRequest,
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """获取OHLCV数据"""
    del current_user
    try:
        _reject_client_api_keys(request)
        ohlcv_data = await run_in_threadpool(
            load_ohlcv_data,
            tickers=request.tickers,
            days=request.days,
            data_sources=request.data_sources,
        )

        if not ohlcv_data:
            raise HTTPException(status_code=400, detail="无法加载OHLCV数据")

        # load_ohlcv_data returns Dict[str, pd.DataFrame] — one per ticker.
        result: Dict[str, Any] = {}
        for ticker, df in ohlcv_data.items():
            if df is not None and not df.empty:
                result[ticker] = df.reset_index().to_dict("records")

        return {"data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取OHLCV数据失败: {str(e)}")

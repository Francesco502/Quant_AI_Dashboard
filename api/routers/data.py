"""
数据获取 API 路由
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from api.dependencies import require_permission, log_access
from api.auth import get_current_active_user, UserInDB
from core.rbac import Permission
from core.audit_log import AuditAction
from typing import List, Optional
from pydantic import BaseModel
import pandas as pd

from core.data_service import load_price_data, load_ohlcv_data

router = APIRouter()


class DataRequest(BaseModel):
    """数据请求模型"""
    tickers: List[str]
    days: int = 365
    data_sources: Optional[List[str]] = None
    alpha_vantage_key: Optional[str] = None
    tushare_token: Optional[str] = None


@router.post("/prices")
async def get_prices(
    request: DataRequest,
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA))
):
    """获取价格数据（需要VIEW_DATA权限）"""
    try:
        price_data = load_price_data(
            tickers=request.tickers,
            days=request.days,
            data_sources=request.data_sources,
            alpha_vantage_key=request.alpha_vantage_key,
            tushare_token=request.tushare_token,
        )

        if price_data is None or price_data.empty:
            raise HTTPException(status_code=400, detail="无法加载价格数据")

        # 转换为字典格式
        result = {}
        for ticker in price_data.columns:
            result[ticker] = [
                {"date": str(date), "price": float(price)}
                for date, price in price_data[ticker].items()
            ]

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
    days: int = Query(365, description="历史天数"),
    data_sources: Optional[str] = Query(None, description="数据源，逗号分隔"),
):
    """获取价格数据（GET方式）"""
    try:
        ticker_list = [t.strip() for t in tickers.split(",")]
        data_source_list = (
            [s.strip() for s in data_sources.split(",")] if data_sources else ["AkShare"]
        )

        price_data = load_price_data(
            tickers=ticker_list, days=days, data_sources=data_source_list
        )

        if price_data is None or price_data.empty:
            raise HTTPException(status_code=400, detail="无法加载价格数据")

        result = {}
        for ticker in price_data.columns:
            result[ticker] = [
                {"date": str(date), "price": float(price)}
                for date, price in price_data[ticker].items()
            ]

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


@router.post("/ohlcv")
async def get_ohlcv(request: DataRequest):
    """获取OHLCV数据"""
    try:
        ohlcv_data = load_ohlcv_data(
            tickers=request.tickers,
            days=request.days,
            data_sources=request.data_sources,
            alpha_vantage_key=request.alpha_vantage_key,
            tushare_token=request.tushare_token,
        )

        if ohlcv_data is None or ohlcv_data.empty:
            raise HTTPException(status_code=400, detail="无法加载OHLCV数据")

        # 转换为字典格式
        result = {}
        if isinstance(ohlcv_data.columns, pd.MultiIndex):
            for ticker in ohlcv_data.columns.levels[0]:
                ticker_data = ohlcv_data[ticker]
                result[ticker] = ticker_data.to_dict("records")
        else:
            # 单标的情况
            ticker = request.tickers[0] if request.tickers else "unknown"
            result[ticker] = ohlcv_data.to_dict("records")

        return {"data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取OHLCV数据失败: {str(e)}")


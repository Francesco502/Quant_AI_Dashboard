"""外部数据源 API 路由

提供宏观经济数据、行业轮动数据、市场情绪数据和资金流向数据的 API 接口。
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from api.dependencies import require_permission, log_access
from api.auth import get_current_active_user, UserInDB
from core.rbac import Permission
from core.audit_log import AuditAction
from typing import List, Optional
from pydantic import BaseModel
import pandas as pd

from core.data_service import (
    load_external_data,
    merge_price_with_external,
    get_external_features,
    get_economic_summary,
    get_industry_summary,
    get_sentiment_summary,
    get_flow_summary,
)

router = APIRouter()


class ExternalDataRequest(BaseModel):
    """外部数据请求模型"""
    economic: bool = True
    industry: bool = True
    sentiment: bool = True
    flow: bool = True
    start_date: str = Query("2010-01-01", description="开始日期")
    end_date: str = Query(None, description="结束日期")


@router.get("/economic")
async def get_economic_data(
    start_date: str = Query("2010-01-01", description="开始日期"),
    end_date: str = Query(None, description="结束日期"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """获取宏观经济数据（需要VIEW_DATA权限）"""
    try:
        economic_data = get_economic_summary(start_date=start_date, end_date=end_date)
        return {"data": economic_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取宏观经济数据失败: {str(e)}")


@router.get("/industry")
async def get_industry_data(
    start_date: str = Query("2010-01-01", description="开始日期"),
    end_date: str = Query(None, description="结束日期"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """获取行业轮动数据（需要VIEW_DATA权限）"""
    try:
        industry_data = get_industry_summary(start_date=start_date, end_date=end_date)
        return {"data": industry_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取行业轮动数据失败: {str(e)}")


@router.get("/sentiment")
async def get_sentiment_data(
    start_date: str = Query("2010-01-01", description="开始日期"),
    end_date: str = Query(None, description="结束日期"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """获取市场情绪数据（需要VIEW_DATA权限）"""
    try:
        sentiment_data = get_sentiment_summary(start_date=start_date, end_date=end_date)
        return {"data": sentiment_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取市场情绪数据失败: {str(e)}")


@router.get("/flow")
async def get_flow_data(
    start_date: str = Query("2010-01-01", description="开始日期"),
    end_date: str = Query(None, description="结束日期"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """获取资金流向数据（需要VIEW_DATA权限）"""
    try:
        flow_data = get_flow_summary(start_date=start_date, end_date=end_date)
        return {"data": flow_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取资金流向数据失败: {str(e)}")


@router.post("/all")
async def get_all_external_data(
    request: ExternalDataRequest,
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """获取所有外部数据（需要VIEW_DATA权限）"""
    try:
        external_data = load_external_data(
            economic=request.economic,
            industry=request.industry,
            sentiment=request.sentiment,
            flow=request.flow,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        return {"data": external_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取外部数据失败: {str(e)}")


@router.post("/merge")
async def merge_price_with_external_data(
    request: ExternalDataRequest,
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """获取外部数据（需要VIEW_DATA权限）"""
    try:
        external_data = load_external_data(
            economic=request.economic,
            industry=request.industry,
            sentiment=request.sentiment,
            flow=request.flow,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        return {"data": external_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取外部数据失败: {str(e)}")


@router.post("/features")
async def get_external_features_endpoint(
    request: ExternalDataRequest,
    tickers: List[str] = Query(..., description="标的代码列表"),
    days: int = Query(365, description="历史天数"),
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """获取外部数据特征（需要VIEW_DATA权限）"""
    try:
        from core.data_service import load_price_data
        price_df = load_price_data(tickers=tickers, days=days)
        if price_df.empty:
            raise HTTPException(status_code=400, detail="无法获取价格数据")

        features_df = get_external_features(price_df, start_date=request.start_date, end_date=request.end_date)
        return {"data": features_df.to_dict(orient="split")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取外部数据特征失败: {str(e)}")

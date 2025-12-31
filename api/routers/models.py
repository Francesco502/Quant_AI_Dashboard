"""
模型管理 API 路由
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict

from core.advanced_forecasting import ModelManager, ModelRegistry

router = APIRouter()


@router.get("/registry")
async def get_model_registry():
    """获取模型注册表"""
    try:
        manager = ModelManager()
        registry = manager.registry

        return {
            "models": registry.models,
            "production_models": registry.production_models,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型注册表失败: {str(e)}")


@router.get("/production/{ticker}")
async def get_production_model(ticker: str):
    """获取指定标的的生产模型"""
    try:
        manager = ModelManager()
        registry = manager.registry

        model_id = registry.get_production_model(ticker)
        if not model_id:
            raise HTTPException(status_code=404, detail=f"{ticker} 无生产模型")

        model_info = registry.get_model_info(model_id)
        if not model_info:
            raise HTTPException(status_code=404, detail="模型信息不存在")

        return model_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取生产模型失败: {str(e)}")


@router.get("/history/{ticker}")
async def get_model_history(ticker: str):
    """获取指定标的的模型历史"""
    try:
        manager = ModelManager()
        registry = manager.registry

        history = registry.list_model_history(ticker)
        return {"ticker": ticker, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型历史失败: {str(e)}")


@router.get("/available")
async def get_available_models():
    """获取可用模型列表"""
    try:
        from core.advanced_forecasting import get_available_models

        models = get_available_models()
        return models
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取可用模型列表失败: {str(e)}")


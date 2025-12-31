"""
策略管理 API 路由
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from pydantic import BaseModel

from core.strategy_manager import get_strategy_manager
from core.strategy_framework import BaseStrategy
from core.data_service import load_price_data

router = APIRouter()


class StrategyConfig(BaseModel):
    """策略配置模型"""
    strategy_id: str
    type: str
    version: str = "v1.0"
    params: Dict


class StrategyResponse(BaseModel):
    """策略响应模型"""
    strategy_id: str
    type: str
    version: str
    config: Dict


@router.get("/", response_model=List[Dict])
async def list_strategies():
    """获取所有策略列表"""
    try:
        manager = get_strategy_manager()
        strategies = manager.list_strategies()
        return strategies
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略列表失败: {str(e)}")


@router.get("/{strategy_id}", response_model=Dict)
async def get_strategy(strategy_id: str):
    """获取指定策略详情"""
    try:
        manager = get_strategy_manager()
        strategy = manager.get_strategy(strategy_id)
        if strategy is None:
            raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")
        return strategy.get_config()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略失败: {str(e)}")


@router.post("/", response_model=Dict)
async def create_strategy(config: StrategyConfig):
    """创建新策略"""
    try:
        manager = get_strategy_manager()
        strategy_dict = config.dict()
        success = manager.add_strategy(strategy_dict)
        if not success:
            raise HTTPException(status_code=400, detail="创建策略失败")
        return {"status": "success", "strategy_id": config.strategy_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建策略失败: {str(e)}")


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """删除策略"""
    try:
        manager = get_strategy_manager()
        success = manager.remove_strategy(strategy_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")
        return {"status": "success", "message": f"策略 {strategy_id} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除策略失败: {str(e)}")


@router.post("/{strategy_id}/generate-signals")
async def generate_signals(
    strategy_id: str,
    tickers: List[str],
    days: int = 365,
    data_sources: Optional[List[str]] = None,
):
    """使用指定策略生成信号"""
    try:
        manager = get_strategy_manager()
        strategy = manager.get_strategy(strategy_id)
        if strategy is None:
            raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

        # 加载价格数据
        price_data = load_price_data(
            tickers=tickers,
            days=days,
            data_sources=data_sources or ["AkShare"],
        )

        if price_data is None or price_data.empty:
            raise HTTPException(status_code=400, detail="无法加载价格数据")

        # 生成信号
        signals = strategy.generate_signals(price_data, strategy_manager=manager)

        if signals.empty:
            return {"signals": [], "message": "未生成有效信号"}

        # 转换为字典列表
        signals_list = signals.to_dict("records")
        return {"signals": signals_list, "count": len(signals_list)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成信号失败: {str(e)}")


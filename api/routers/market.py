"""市场相关 API 路由（大盘复盘等）"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from core.market_review import daily_review


router = APIRouter()


@router.get("/daily-review")
async def daily_market_review(
    market: str = Query("cn", description="市场类型：cn/us/both"),
) -> Dict[str, Any]:
    """获取指定市场的大盘复盘摘要"""
    try:
        data = daily_review(market=market)  # type: ignore[arg-type]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取大盘复盘失败: {e}")


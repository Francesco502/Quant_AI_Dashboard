"""Agent 研究相关 API 路由"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.agent import run_agent


router = APIRouter()


class ResearchRequest(BaseModel):
    """Agent 深度研究请求"""

    query: str = Field(..., description="自然语言研究问题，如：比较 600519 和 000858 的估值与风险点")
    model: Optional[str] = Field(
        None,
        description="可选，本次请求使用的 LLM 模型名；留空使用服务端默认配置",
    )


@router.post("/research")
async def research(req: ResearchRequest) -> Dict[str, Any]:
    """使用 Agent 执行一次深度研究任务"""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query 不能为空")
    try:
        result = run_agent(query=req.query, model=req.model)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 研究执行失败: {e}") from e


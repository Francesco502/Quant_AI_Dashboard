"""Agent research API routes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import llm_client
from core.agent import run_agent


router = APIRouter()


class ResearchRequest(BaseModel):
    """Agent deep research request."""

    query: str = Field(..., description="Natural-language research question.")
    model: Optional[str] = Field(
        None,
        description="Optional per-request LLM model override.",
    )


@router.post("/research")
async def research(req: ResearchRequest) -> Dict[str, Any]:
    """Execute one agent research task."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")
    if not llm_client.is_available():
        status = llm_client.get_status()
        detail = status.get("error") or "Agent research requires a configured LLM provider."
        raise HTTPException(status_code=503, detail=str(detail))
    try:
        return run_agent(query=req.query, model=req.model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Agent research failed: {exc}") from exc

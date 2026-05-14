"""Agent research API routes."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import llm_client
from core.agent import run_agent


router = APIRouter()


def _is_timeout_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "timeout" in text or "timed out" in text


def _timeout_fallback(query: str, exc: Exception) -> Dict[str, Any]:
    return {
        "answer": (
            "LLM provider timed out before the agent workflow completed. "
            "Use this as a conservative placeholder: review valuation pressure, "
            "earnings durability, sector policy changes, liquidity, and position sizing "
            f"before acting on `{query.strip()}`."
        ),
        "iterations": 0,
        "tools_used": [],
        "tool_results": [],
        "scratchpad_path": None,
        "degraded": True,
        "error": str(exc),
    }


class ResearchRequest(BaseModel):
    """Agent deep research request."""

    query: str = Field(..., description="Natural-language research question.")
    model: Optional[str] = Field(
        None,
        description="Optional per-request LLM model override.",
    )
    max_iterations: int = Field(
        1,
        ge=1,
        le=3,
        description="Maximum planning/tool iterations for this request.",
    )
    mode: Literal["quick", "deep"] = Field(
        "quick",
        description="Quick mode avoids heavier research tools; deep mode enables the full tool set.",
    )


@router.post("/research")
def research(req: ResearchRequest) -> Dict[str, Any]:
    """Execute one agent research task."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")
    if not llm_client.is_available():
        status = llm_client.get_status()
        detail = status.get("error") or "Agent research requires a configured LLM provider."
        raise HTTPException(status_code=503, detail=str(detail))
    try:
        tool_names = None
        if req.mode == "quick":
            tool_names = ["price", "fundamentals"]
        return run_agent(
            query=req.query,
            model=req.model,
            max_iterations=req.max_iterations,
            tool_names=tool_names,
        )
    except Exception as exc:  # noqa: BLE001
        if _is_timeout_error(exc):
            return _timeout_fallback(req.query, exc)
        raise HTTPException(status_code=500, detail=f"Agent research failed: {exc}") from exc

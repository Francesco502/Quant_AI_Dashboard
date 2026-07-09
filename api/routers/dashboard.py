"""Lightweight v3 dashboard summary API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter

from core.version import VERSION


router = APIRouter()


def _asset_pool_summary() -> dict[str, Any]:
    return {"count": 0, "items": []}


def _personal_assets_summary() -> dict[str, Any]:
    return {"count": 0, "total_value": None}


def _paper_account_summary() -> dict[str, Any]:
    return {"enabled": True, "equity": None}


def _auto_trading_summary() -> dict[str, Any]:
    return {"enabled": False, "guarded": True}


def _market_review_summary() -> dict[str, Any]:
    return {"state": "not_loaded", "items": []}


def _price_preview_summary() -> dict[str, Any]:
    return {"count": 0, "items": []}


SECTION_BUILDERS: dict[str, Callable[[], dict[str, Any]]] = {
    "asset_pool": _asset_pool_summary,
    "personal_assets": _personal_assets_summary,
    "paper_account": _paper_account_summary,
    "auto_trading": _auto_trading_summary,
    "market_review": _market_review_summary,
    "price_preview": _price_preview_summary,
}


@router.get("/summary")
async def get_dashboard_summary() -> dict[str, Any]:
    sections: dict[str, Any] = {}
    partial_failures: dict[str, str] = {}

    for name, builder in SECTION_BUILDERS.items():
        try:
            sections[name] = builder()
        except Exception as exc:  # noqa: BLE001
            sections[name] = None
            partial_failures[name] = str(exc)

    return {
        "status": "partial" if partial_failures else "success",
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "partial_failures": partial_failures,
    }

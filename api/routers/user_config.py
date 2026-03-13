"""User configuration routes."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import UserInDB, get_current_active_user
from core.user_config import UserPreferences, get_user_config_manager


logger = logging.getLogger(__name__)
router = APIRouter()


def _require_user_id(current_user: UserInDB) -> int:
    user_id = getattr(current_user, "id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Unable to resolve current user id")
    return int(user_id)


class WatchlistRequest(BaseModel):
    ticker: str
    note: Optional[str] = None


class StrategyConfigRequest(BaseModel):
    config: Dict


class PreferencesRequest(BaseModel):
    default_strategy: Optional[str] = None
    risk_tolerance: Optional[str] = None
    notification_enabled: Optional[bool] = None


@router.get("/watchlist")
async def get_watchlist(current_user: UserInDB = Depends(get_current_active_user)):
    try:
        user_id = _require_user_id(current_user)
        manager = get_user_config_manager()
        watchlist = manager.get_watchlist(user_id)
        return {"watchlist": watchlist, "count": len(watchlist)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get watchlist: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watchlist")
async def add_watchlist(
    request: WatchlistRequest,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        manager = get_user_config_manager()
        success = manager.add_watchlist(user_id, request.ticker, request.note)
        return {"success": success, "ticker": request.ticker}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to add watchlist item: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/watchlist/{ticker}")
async def remove_watchlist(
    ticker: str,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        manager = get_user_config_manager()
        success = manager.remove_watchlist(user_id, ticker)
        return {"success": success, "ticker": ticker}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to remove watchlist item: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preferences")
async def get_preferences(current_user: UserInDB = Depends(get_current_active_user)):
    try:
        user_id = _require_user_id(current_user)
        manager = get_user_config_manager()
        prefs = manager.get_preferences(user_id)
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
        return {"user_id": user_id, **asdict(prefs)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get preferences: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preferences")
async def save_preferences(
    request: PreferencesRequest,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        manager = get_user_config_manager()
        prefs = manager.get_preferences(user_id) or UserPreferences(user_id=user_id)

        if request.default_strategy is not None:
            prefs.default_strategy = request.default_strategy
        if request.risk_tolerance is not None:
            prefs.risk_tolerance = request.risk_tolerance
        if request.notification_enabled is not None:
            prefs.notification_enabled = request.notification_enabled

        success = manager.save_preferences(prefs)
        return {"success": success, "preferences": asdict(prefs)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save preferences: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies")
async def get_strategy_configs(current_user: UserInDB = Depends(get_current_active_user)):
    try:
        user_id = _require_user_id(current_user)
        manager = get_user_config_manager()
        preset_strategies = ["all", "ma", "rsi", "trend", "breakout", "value"]
        configs = []
        for strategy in preset_strategies:
            config = manager.get_strategy_config(user_id, strategy)
            configs.append({"strategy_name": strategy, "config": config})
        return {"strategies": configs}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get strategy configs: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategies/{strategy_name}")
async def save_strategy_config(
    strategy_name: str,
    request: StrategyConfigRequest,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        user_id = _require_user_id(current_user)
        manager = get_user_config_manager()
        success = manager.add_strategy_config(user_id, strategy_name, request.config)
        return {"success": success, "strategy_name": strategy_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save strategy config: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

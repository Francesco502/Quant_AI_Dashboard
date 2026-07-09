"""Persisted market-refresh task queue used by worker status endpoints."""

from __future__ import annotations

import os
from typing import Optional

from core.data_store import BASE_DIR
from core.tasks.base_store import BaseTaskStore


class MarketRefreshTaskStore(BaseTaskStore):
    def __init__(self, db_path: str):
        super().__init__(db_path=db_path, table_name="market_refresh_tasks")


_store_instance: Optional[MarketRefreshTaskStore] = None
_store_path: Optional[str] = None


def get_market_refresh_task_store() -> MarketRefreshTaskStore:
    global _store_instance, _store_path
    configured_path = os.getenv("MARKET_REFRESH_TASK_DB_PATH") or os.path.join(BASE_DIR, "market_refresh_tasks.db")
    if _store_instance is None or _store_path != configured_path:
        _store_instance = MarketRefreshTaskStore(configured_path)
        _store_path = configured_path
    return _store_instance


def reset_market_refresh_task_store_for_tests() -> None:
    global _store_instance, _store_path
    _store_instance = None
    _store_path = None

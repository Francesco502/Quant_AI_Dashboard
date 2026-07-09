"""Persisted prediction task queue used by worker status endpoints."""

from __future__ import annotations

import os
from typing import Optional

from core.data_store import BASE_DIR
from core.tasks.base_store import BaseTaskStore


class PredictionTaskStore(BaseTaskStore):
    def __init__(self, db_path: str):
        super().__init__(db_path=db_path, table_name="prediction_tasks")


_store_instance: Optional[PredictionTaskStore] = None
_store_path: Optional[str] = None


def get_prediction_task_store() -> PredictionTaskStore:
    global _store_instance, _store_path
    configured_path = os.getenv("PREDICTION_TASK_DB_PATH") or os.path.join(BASE_DIR, "prediction_tasks.db")
    if _store_instance is None or _store_path != configured_path:
        _store_instance = PredictionTaskStore(configured_path)
        _store_path = configured_path
    return _store_instance


def reset_prediction_task_store_for_tests() -> None:
    global _store_instance, _store_path
    _store_instance = None
    _store_path = None

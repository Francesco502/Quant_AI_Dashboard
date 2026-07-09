"""Persisted v3 scan task queue."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Optional

from core.data_store import BASE_DIR
from core.tasks.base_store import BaseTask, BaseTaskLookup, BaseTaskRequest, BaseTaskStore


@dataclass(frozen=True)
class ScanTaskRequest(BaseTaskRequest):
    payload: dict[str, Any]

    def normalized(self) -> dict[str, Any]:
        data = super().normalized()
        for field_name in ("tickers", "selector_names"):
            if field_name in data and data[field_name] is not None:
                data[field_name] = sorted({str(item).strip() for item in data[field_name] if str(item).strip()})
        return data


ScanTask = BaseTask
ScanTaskLookup = BaseTaskLookup


class ScanTaskStore(BaseTaskStore):
    def __init__(self, db_path: str):
        super().__init__(db_path=db_path, table_name="scan_tasks")


_store_instance: Optional[ScanTaskStore] = None
_store_path: Optional[str] = None


def get_scan_task_store() -> ScanTaskStore:
    global _store_instance, _store_path
    configured_path = os.getenv("SCAN_TASK_DB_PATH") or os.path.join(BASE_DIR, "scan_tasks.db")
    if _store_instance is None or _store_path != configured_path:
        _store_instance = ScanTaskStore(configured_path)
        _store_path = configured_path
    return _store_instance


def reset_scan_task_store_for_tests() -> None:
    global _store_instance, _store_path
    _store_instance = None
    _store_path = None

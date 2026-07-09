"""Persisted v3 backtest task queue."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Optional

from core.data_store import BASE_DIR
from core.tasks.base_store import BaseTask, BaseTaskLookup, BaseTaskRequest, BaseTaskStore


@dataclass(frozen=True)
class BacktestTaskRequest(BaseTaskRequest):
    payload: dict[str, Any]

    def normalized(self) -> dict[str, Any]:
        data = super().normalized()
        if "tickers" in data:
            data["tickers"] = sorted({str(item).strip().upper() for item in data.get("tickers", []) if str(item).strip()})
        if isinstance(data.get("param_grid"), dict):
            data["param_grid"] = {
                str(key): sorted(values, key=lambda item: str(item))
                for key, values in sorted(data["param_grid"].items())
            }
        if isinstance(data.get("params"), dict):
            data["params"] = {str(key): data["params"][key] for key in sorted(data["params"])}
        return data


BacktestTask = BaseTask
BacktestTaskLookup = BaseTaskLookup


class BacktestTaskStore(BaseTaskStore):
    def __init__(self, db_path: str):
        super().__init__(db_path=db_path, table_name="backtest_tasks")


_store_instance: Optional[BacktestTaskStore] = None
_store_path: Optional[str] = None


def get_backtest_task_store() -> BacktestTaskStore:
    global _store_instance, _store_path
    configured_path = os.getenv("BACKTEST_TASK_DB_PATH") or os.path.join(BASE_DIR, "backtest_tasks.db")
    if _store_instance is None or _store_path != configured_path:
        _store_instance = BacktestTaskStore(configured_path)
        _store_path = configured_path
    return _store_instance


def reset_backtest_task_store_for_tests() -> None:
    global _store_instance, _store_path
    _store_instance = None
    _store_path = None

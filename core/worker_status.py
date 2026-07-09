"""Runtime worker status helpers for single-container and worker deployments."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Optional


PREDICTION_WORKER = "prediction"
MARKET_REFRESH_WORKER = "market_refresh"
SCAN_WORKER = "scan"
BACKTEST_WORKER = "backtest"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _heartbeat_dir() -> Path:
    configured = os.getenv("WORKER_HEARTBEAT_DIR", "").strip()
    if configured:
        return Path(configured)
    from .data_store import BASE_DIR

    return Path(BASE_DIR) / "worker_heartbeats"


def _heartbeat_path(worker_name: str) -> Path:
    safe_name = "".join(ch for ch in worker_name if ch.isalnum() or ch in {"_", "-"}).strip("_-")
    return _heartbeat_dir() / f"{safe_name or 'worker'}.json"


def write_worker_heartbeat(
    worker_name: str,
    *,
    status: str = "idle",
    task_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    path = _heartbeat_path(worker_name)
    payload = {
        "worker": worker_name,
        "status": status,
        "task_id": task_id,
        "detail": detail,
        "updated_at": _now().isoformat(),
        "pid": os.getpid(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def read_worker_heartbeat(worker_name: str, *, stale_after_seconds: Optional[float] = None) -> dict[str, Any]:
    stale_after = float(stale_after_seconds if stale_after_seconds is not None else os.getenv("WORKER_HEARTBEAT_STALE_SECONDS", "45"))
    path = _heartbeat_path(worker_name)
    if not path.exists():
        return {
            "worker": worker_name,
            "online": False,
            "state": "offline",
            "stale": False,
            "updated_at": None,
            "age_seconds": None,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        updated = datetime.fromisoformat(str(payload.get("updated_at")))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age_seconds = max(0.0, (_now() - updated.astimezone(timezone.utc)).total_seconds())
        stale = age_seconds > max(1.0, stale_after)
        return {
            **payload,
            "online": not stale,
            "state": "stale" if stale else str(payload.get("status") or "online"),
            "stale": stale,
            "age_seconds": round(age_seconds, 1),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "worker": worker_name,
            "online": False,
            "state": "unreadable",
            "stale": True,
            "updated_at": None,
            "age_seconds": None,
            "error": str(exc),
        }


def prediction_external_worker_mode() -> bool:
    return os.getenv("PREDICTION_TASK_EXECUTION_MODE", "").strip().lower() == "external_worker"


def market_refresh_external_worker_mode() -> bool:
    return os.getenv("MARKET_REFRESH_TASK_EXECUTION_MODE", "").strip().lower() == "external_worker"


def prediction_single_container_inline_enabled() -> bool:
    return os.getenv("PREDICTION_SINGLE_CONTAINER_INLINE_FALLBACK", "true").strip().lower() in {"1", "true", "yes", "on"}


def market_refresh_single_container_inline_enabled() -> bool:
    return os.getenv("MARKET_REFRESH_SINGLE_CONTAINER_INLINE_FALLBACK", "true").strip().lower() in {"1", "true", "yes", "on"}

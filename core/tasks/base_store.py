"""Shared SQLite task-store lifecycle primitives."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from typing import Any, Optional


TASK_PENDING = "pending"
TASK_RUNNING = "running"
TASK_SUCCEEDED = "succeeded"
TASK_FAILED = "failed"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_json_value(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def parse_utc_datetime(value: str | datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_identifier(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", str(value or "")).strip("_")
    if not safe:
        raise ValueError("table_name cannot be empty")
    return safe


@dataclass(frozen=True)
class BaseTaskRequest:
    payload: dict[str, Any]

    def normalized(self) -> dict[str, Any]:
        normalized = _normalize_json_value(self.payload)
        return normalized if isinstance(normalized, dict) else {"value": normalized}


@dataclass
class BaseTask:
    task_id: str
    request_hash: str
    request_date: str
    request: dict[str, Any]
    status: str
    result: Optional[dict[str, Any]]
    error_message: Optional[str]
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[float] = None
    attempts: int = 0

    def to_api(self, *, cache_hit: bool = False) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "request_hash": self.request_hash,
            "request_date": self.request_date,
            "status": self.status,
            "request": self.request,
            "result": self.result,
            "error_message": self.error_message,
            "cache_hit": cache_hit,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "attempts": self.attempts,
        }


@dataclass
class BaseTaskLookup:
    task: BaseTask
    created: bool
    cache_hit: bool


class BaseTaskStore:
    """Common persisted task lifecycle for worker-backed queues."""

    def __init__(self, *, db_path: str, table_name: str):
        self.db_path = db_path
        self.table_name = _safe_identifier(table_name)
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    task_id TEXT PRIMARY KEY,
                    request_hash TEXT UNIQUE NOT NULL,
                    request_date TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    duration_ms REAL,
                    attempts INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_status ON {self.table_name}(status)"
            )
            conn.commit()

    def make_request_hash(self, request: BaseTaskRequest, request_date: Optional[date] = None) -> str:
        payload = request.normalized()
        payload["request_date"] = (request_date or date.today()).isoformat()
        return hashlib.sha256(json_dumps(payload).encode("utf-8")).hexdigest()

    def get_or_create_task(
        self,
        request: BaseTaskRequest,
        *,
        request_date: Optional[date] = None,
        force_refresh: bool = False,
    ) -> BaseTaskLookup:
        normalized = request.normalized()
        day = (request_date or date.today()).isoformat()
        base_hash = self.make_request_hash(request, request_date=request_date)
        request_hash = f"{base_hash}:{uuid.uuid4().hex}" if force_refresh else base_hash
        with self._lock, closing(self._connect()) as conn:
            if not force_refresh:
                row = conn.execute(
                    f"SELECT * FROM {self.table_name} WHERE request_hash = ?",
                    (request_hash,),
                ).fetchone()
                if row:
                    task = self._row_to_task(row)
                    return BaseTaskLookup(task=task, created=False, cache_hit=task.status == TASK_SUCCEEDED)

            task_id = uuid.uuid4().hex
            now = utc_now_iso()
            conn.execute(
                f"""
                INSERT INTO {self.table_name} (
                    task_id, request_hash, request_date, request_json,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, request_hash, day, json_dumps(normalized), TASK_PENDING, now, now),
            )
            conn.commit()
            row = conn.execute(f"SELECT * FROM {self.table_name} WHERE task_id = ?", (task_id,)).fetchone()
        return BaseTaskLookup(task=self._row_to_task(row), created=True, cache_hit=False)

    def get_task(self, task_id: str) -> Optional[BaseTask]:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(f"SELECT * FROM {self.table_name} WHERE task_id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def claim_next_pending(self, *, max_attempts: int = 3) -> Optional[BaseTask]:
        now = utc_now_iso()
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                f"""
                SELECT * FROM {self.table_name}
                WHERE status = ? AND attempts < ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (TASK_PENDING, max(1, int(max_attempts))),
            ).fetchone()
            if row is None:
                return None
            updated = conn.execute(
                f"""
                UPDATE {self.table_name}
                SET status = ?, started_at = COALESCE(started_at, ?), updated_at = ?,
                    attempts = attempts + 1
                WHERE task_id = ? AND status = ?
                """,
                (TASK_RUNNING, now, now, row["task_id"], TASK_PENDING),
            )
            conn.commit()
            if updated.rowcount != 1:
                return None
            claimed = conn.execute(f"SELECT * FROM {self.table_name} WHERE task_id = ?", (row["task_id"],)).fetchone()
        return self._row_to_task(claimed) if claimed else None

    def requeue_stale_running(
        self,
        *,
        stale_after_seconds: float = 1800,
        max_attempts: int = 3,
        now: str | datetime | None = None,
    ) -> int:
        cutoff = parse_utc_datetime(now) - timedelta(seconds=max(1.0, float(stale_after_seconds)))
        current = utc_now_iso()
        changed = 0
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT task_id, attempts FROM {self.table_name} WHERE status = ? AND updated_at < ?",
                (TASK_RUNNING, cutoff.isoformat()),
            ).fetchall()
            for row in rows:
                attempts = int(row["attempts"] or 0)
                if attempts >= max(1, int(max_attempts)):
                    conn.execute(
                        f"""
                        UPDATE {self.table_name}
                        SET status = ?, error_message = ?, finished_at = ?, updated_at = ?
                        WHERE task_id = ?
                        """,
                        (TASK_FAILED, "Task exceeded retry limit after stale worker recovery", current, current, row["task_id"]),
                    )
                else:
                    conn.execute(
                        f"""
                        UPDATE {self.table_name}
                        SET status = ?, error_message = ?, started_at = NULL, updated_at = ?
                        WHERE task_id = ?
                        """,
                        (TASK_PENDING, "Task was requeued after stale worker recovery", current, row["task_id"]),
                    )
                changed += 1
            conn.commit()
        return changed

    def mark_succeeded(self, task_id: str, result: dict[str, Any], *, duration_ms: Optional[float] = None) -> None:
        now = utc_now_iso()
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                f"""
                UPDATE {self.table_name}
                SET status = ?, result_json = ?, error_message = NULL,
                    duration_ms = ?, finished_at = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (TASK_SUCCEEDED, json_dumps(result), duration_ms, now, now, task_id),
            )
            conn.commit()

    def mark_completed(self, task_id: str, result: dict[str, Any], *, duration_ms: Optional[float] = None) -> None:
        self.mark_succeeded(task_id, result, duration_ms=duration_ms)

    def mark_failed(self, task_id: str, error_message: str, *, duration_ms: Optional[float] = None) -> None:
        now = utc_now_iso()
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                f"""
                UPDATE {self.table_name}
                SET status = ?, error_message = ?, duration_ms = ?, finished_at = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (TASK_FAILED, str(error_message), duration_ms, now, now, task_id),
            )
            conn.commit()

    def get_status_summary(self) -> dict[str, Any]:
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT status, COUNT(*) AS count FROM {self.table_name} GROUP BY status"
            ).fetchall()
            latest = conn.execute(
                f"SELECT task_id, status, error_message, updated_at FROM {self.table_name} ORDER BY updated_at DESC LIMIT 5"
            ).fetchall()
        counts = {TASK_PENDING: 0, TASK_RUNNING: 0, TASK_SUCCEEDED: 0, TASK_FAILED: 0}
        counts.update({str(row["status"]): int(row["count"]) for row in rows})
        return {
            "counts": counts,
            "pending": counts.get(TASK_PENDING, 0),
            "running": counts.get(TASK_RUNNING, 0),
            "succeeded": counts.get(TASK_SUCCEEDED, 0),
            "failed": counts.get(TASK_FAILED, 0),
            "latest": [dict(row) for row in latest],
        }

    def _row_to_task(self, row: sqlite3.Row) -> BaseTask:
        result = json.loads(row["result_json"]) if row["result_json"] else None
        return BaseTask(
            task_id=row["task_id"],
            request_hash=row["request_hash"],
            request_date=row["request_date"],
            request=json.loads(row["request_json"]),
            status=row["status"],
            result=result,
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            duration_ms=row["duration_ms"],
            attempts=int(row["attempts"] or 0),
        )

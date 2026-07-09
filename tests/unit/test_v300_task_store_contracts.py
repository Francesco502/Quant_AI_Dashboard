"""Contracts for the v3 shared task-store base."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from core.tasks.base_store import (
    BaseTaskRequest,
    BaseTaskStore,
    TASK_FAILED,
    TASK_PENDING,
    TASK_RUNNING,
    TASK_SUCCEEDED,
)


def _request(**update) -> BaseTaskRequest:
    payload = {"user_id": 1, "kind": "scan", "params": {"b": 2, "a": 1}}
    payload.update(update)
    return BaseTaskRequest(payload)


def test_base_task_store_request_hash_is_deterministic(tmp_path):
    store = BaseTaskStore(db_path=str(tmp_path / "tasks.db"), table_name="v300_tasks")

    first = store.make_request_hash(_request(params={"b": 2, "a": 1}), request_date=date(2026, 6, 26))
    second = store.make_request_hash(_request(params={"a": 1, "b": 2}), request_date=date(2026, 6, 26))

    assert first == second


def test_base_task_store_reuses_same_day_task(tmp_path):
    store = BaseTaskStore(db_path=str(tmp_path / "tasks.db"), table_name="v300_tasks")

    first = store.get_or_create_task(_request(), request_date=date(2026, 6, 26))
    second = store.get_or_create_task(_request(), request_date=date(2026, 6, 26))

    assert first.created is True
    assert second.created is False
    assert first.task.task_id == second.task.task_id


def test_base_task_store_claims_oldest_pending(tmp_path):
    store = BaseTaskStore(db_path=str(tmp_path / "tasks.db"), table_name="v300_tasks")
    first = store.get_or_create_task(_request(kind="scan"), request_date=date(2026, 6, 26)).task
    store.get_or_create_task(_request(kind="backtest"), request_date=date(2026, 6, 26))

    claimed = store.claim_next_pending()

    assert claimed is not None
    assert claimed.task_id == first.task_id
    assert claimed.status == TASK_RUNNING
    assert claimed.attempts == 1


def test_base_task_store_requeues_stale_running_until_retry_limit(tmp_path):
    store = BaseTaskStore(db_path=str(tmp_path / "tasks.db"), table_name="v300_tasks")
    task = store.get_or_create_task(_request(), request_date=date(2026, 6, 26)).task
    store.claim_next_pending()

    now = datetime.now(timezone.utc) + timedelta(hours=1)
    changed = store.requeue_stale_running(stale_after_seconds=1, max_attempts=2, now=now)
    requeued = store.get_task(task.task_id)

    assert changed == 1
    assert requeued is not None
    assert requeued.status == TASK_PENDING

    store.claim_next_pending()
    store.requeue_stale_running(stale_after_seconds=1, max_attempts=2, now=now + timedelta(hours=1))
    failed = store.get_task(task.task_id)

    assert failed is not None
    assert failed.status == TASK_FAILED
    assert "retry limit" in (failed.error_message or "")


def test_base_task_store_result_survives_restart(tmp_path):
    db_path = str(tmp_path / "tasks.db")
    store = BaseTaskStore(db_path=db_path, table_name="v300_tasks")
    task = store.get_or_create_task(_request(), request_date=date(2026, 6, 26)).task

    store.mark_succeeded(task.task_id, {"rows": [1, 2, 3]}, duration_ms=12.5)
    restarted = BaseTaskStore(db_path=db_path, table_name="v300_tasks").get_task(task.task_id)

    assert restarted is not None
    assert restarted.status == TASK_SUCCEEDED
    assert restarted.result == {"rows": [1, 2, 3]}
    assert restarted.duration_ms == 12.5

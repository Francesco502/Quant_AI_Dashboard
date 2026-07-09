#!/usr/bin/env python
"""External worker for v3 persisted market-scan tasks."""

from __future__ import annotations

import os
import time
from pathlib import Path

from core.data_store import BASE_DIR
from core.features.snapshot_store import FeatureSnapshotStore
from core.scan_tasks import get_scan_task_store
from core.scanner.batch_scan import scan_latest_snapshot
from core.worker_status import SCAN_WORKER, write_worker_heartbeat


POLL_SECONDS = float(os.getenv("SCAN_WORKER_POLL_SECONDS", "2"))
FEATURE_VERSION = os.getenv("FEATURE_VERSION", "v300")


def _run_task(task) -> dict:
    request = task.request or {}
    market = str(request.get("market") or "CN")
    limit = int(request.get("top_n") or request.get("limit") or 20)
    strategy_config = request.get("strategy_config") or {
        "params": {"min_score": float(request.get("min_score") or 0.0)}
    }
    store = FeatureSnapshotStore(os.getenv("FEATURE_SNAPSHOT_DIR") or Path(BASE_DIR) / "feature_snapshots")
    rows = scan_latest_snapshot(
        store=store,
        market=market,
        feature_version=FEATURE_VERSION,
        strategy_config=strategy_config,
        limit=limit,
    )
    return {"status": "success", "count": len(rows), "data": rows, "execution_mode": "snapshot_fast_path"}


def main() -> int:
    task_store = get_scan_task_store()
    write_worker_heartbeat(SCAN_WORKER, status="starting")
    while True:
        task_store.requeue_stale_running()
        task = task_store.claim_next_pending()
        if task is None:
            write_worker_heartbeat(SCAN_WORKER, status="idle")
            time.sleep(POLL_SECONDS)
            continue

        started = time.perf_counter()
        write_worker_heartbeat(SCAN_WORKER, status="running", task_id=task.task_id)
        try:
            result = _run_task(task)
            task_store.mark_succeeded(task.task_id, result, duration_ms=(time.perf_counter() - started) * 1000.0)
            write_worker_heartbeat(SCAN_WORKER, status="idle", task_id=task.task_id, detail="task succeeded")
        except Exception as exc:  # noqa: BLE001
            task_store.mark_failed(task.task_id, str(exc), duration_ms=(time.perf_counter() - started) * 1000.0)
            write_worker_heartbeat(SCAN_WORKER, status="idle", task_id=task.task_id, detail=f"task failed: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())

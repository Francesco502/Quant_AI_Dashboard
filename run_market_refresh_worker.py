#!/usr/bin/env python
"""External worker skeleton for v3 market data refresh tasks."""

from __future__ import annotations

import os
import time

from core.market_refresh_tasks import get_market_refresh_task_store
from core.worker_status import MARKET_REFRESH_WORKER, write_worker_heartbeat


POLL_SECONDS = float(os.getenv("MARKET_REFRESH_WORKER_POLL_SECONDS", "10"))


def main() -> int:
    task_store = get_market_refresh_task_store()
    write_worker_heartbeat(MARKET_REFRESH_WORKER, status="starting")
    while True:
        task_store.requeue_stale_running()
        task = task_store.claim_next_pending()
        if task is None:
            write_worker_heartbeat(MARKET_REFRESH_WORKER, status="idle")
            time.sleep(POLL_SECONDS)
            continue

        started = time.perf_counter()
        write_worker_heartbeat(MARKET_REFRESH_WORKER, status="running", task_id=task.task_id)
        try:
            task_store.mark_succeeded(
                task.task_id,
                {"status": "success", "message": "market refresh task accepted", "request": task.request},
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )
            write_worker_heartbeat(MARKET_REFRESH_WORKER, status="idle", task_id=task.task_id)
        except Exception as exc:  # noqa: BLE001
            task_store.mark_failed(task.task_id, str(exc), duration_ms=(time.perf_counter() - started) * 1000.0)
            write_worker_heartbeat(MARKET_REFRESH_WORKER, status="idle", task_id=task.task_id, detail=str(exc))


if __name__ == "__main__":
    raise SystemExit(main())

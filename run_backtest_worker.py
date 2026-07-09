#!/usr/bin/env python
"""External worker for v3 persisted backtest tasks."""

from __future__ import annotations

import os
import time

import pandas as pd

from core.backtest_engine import BacktestEngine
from core.backtest_tasks import get_backtest_task_store
from core.data_service import load_price_data
from core.strategy_catalog import get_strategy_definition
from core.worker_status import BACKTEST_WORKER, write_worker_heartbeat


POLL_SECONDS = float(os.getenv("BACKTEST_WORKER_POLL_SECONDS", "2"))


def _load_prices(request: dict) -> pd.DataFrame:
    tickers = [str(item).strip() for item in request.get("tickers", []) if str(item).strip()]
    start_date = pd.Timestamp(request.get("start_date"))
    end_date = pd.Timestamp(request.get("end_date")) if request.get("end_date") else pd.Timestamp.today()
    days = max(30, int((end_date - start_date).days) + 100)
    price_data = load_price_data(tickers, days=days)
    price_data.index = pd.to_datetime(price_data.index)
    price_data = price_data[price_data.index >= start_date]
    if request.get("end_date"):
        price_data = price_data[price_data.index <= end_date]
    return price_data


def _signals_to_frame(payload: dict) -> pd.DataFrame:
    signals = payload or {}
    dates = pd.to_datetime(signals.get("dates") or [])
    columns = [str(item) for item in signals.get("columns") or []]
    values = signals.get("values") or []
    return pd.DataFrame(values, index=dates, columns=columns)


def _serialize_result(result: dict) -> dict:
    payload = dict(result)
    equity_curve = payload.get("equity_curve")
    if isinstance(equity_curve, pd.DataFrame):
        curve = equity_curve.reset_index()
        if "date" in curve.columns:
            curve["date"] = pd.to_datetime(curve["date"]).dt.strftime("%Y-%m-%d")
        payload["equity_curve"] = curve.to_dict(orient="records")
    return payload


def _run_task(task) -> dict:
    request = task.request or {}
    price_data = _load_prices(request)
    engine = BacktestEngine(initial_capital=float(request.get("initial_capital") or 100000.0))

    if request.get("precomputed_signals"):
        result = engine.run_precomputed_signals(
            price_data,
            _signals_to_frame(request["precomputed_signals"]),
            target_type=str(request.get("target_type") or "shares"),
        )
        return _serialize_result(result)

    strategy_conf = get_strategy_definition(str(request.get("strategy_id") or ""))
    if strategy_conf is None:
        raise ValueError(f"Strategy not found: {request.get('strategy_id')}")
    result = engine.run(price_data, strategy_conf.func, request.get("params") or {}, collect_profile=True)
    return _serialize_result(result)


def main() -> int:
    task_store = get_backtest_task_store()
    write_worker_heartbeat(BACKTEST_WORKER, status="starting")
    while True:
        task_store.requeue_stale_running()
        task = task_store.claim_next_pending()
        if task is None:
            write_worker_heartbeat(BACKTEST_WORKER, status="idle")
            time.sleep(POLL_SECONDS)
            continue

        started = time.perf_counter()
        write_worker_heartbeat(BACKTEST_WORKER, status="running", task_id=task.task_id)
        try:
            result = _run_task(task)
            task_store.mark_succeeded(task.task_id, result, duration_ms=(time.perf_counter() - started) * 1000.0)
            write_worker_heartbeat(BACKTEST_WORKER, status="idle", task_id=task.task_id, detail="task succeeded")
        except Exception as exc:  # noqa: BLE001
            task_store.mark_failed(task.task_id, str(exc), duration_ms=(time.perf_counter() - started) * 1000.0)
            write_worker_heartbeat(BACKTEST_WORKER, status="idle", task_id=task.task_id, detail=f"task failed: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())

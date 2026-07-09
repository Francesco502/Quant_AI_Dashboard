#!/usr/bin/env python
"""Deployment readiness checks for v3.0.0 worker-backed workloads."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Iterable

from core.data_store import BASE_DIR
from core.features.snapshot_store import FeatureSnapshotStore
from core.worker_status import (
    BACKTEST_WORKER,
    MARKET_REFRESH_WORKER,
    PREDICTION_WORKER,
    SCAN_WORKER,
    read_worker_heartbeat,
)


DEFAULT_MARKETS = ("CN", "HK")
DEFAULT_WORKERS = (SCAN_WORKER, BACKTEST_WORKER)


def _parse_as_of(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _snapshot_state(
    store: FeatureSnapshotStore,
    *,
    market: str,
    feature_version: str,
    snapshot_max_age_days: int,
) -> dict[str, Any]:
    snapshot = store.read(market=market, feature_version=feature_version)
    if snapshot is None:
        return {"state": "missing", "market": market, "feature_version": feature_version}

    as_of_date = _parse_as_of(snapshot.metadata.get("as_of_date"))
    if as_of_date is None:
        return {
            "state": "stale",
            "market": market,
            "feature_version": feature_version,
            "as_of_date": snapshot.metadata.get("as_of_date"),
            "reason": "snapshot has no valid as_of_date",
        }

    age_days = max(0, (date.today() - as_of_date).days)
    state = "fresh" if age_days <= int(snapshot_max_age_days) else "stale"
    return {
        "state": state,
        "market": market,
        "feature_version": feature_version,
        "as_of_date": as_of_date.isoformat(),
        "age_days": age_days,
        "row_count": snapshot.metadata.get("row_count", len(snapshot.frame)),
        "ticker_count": snapshot.metadata.get("ticker_count"),
    }


def build_report(
    *,
    feature_store_dir: str | Path | None = None,
    markets: Iterable[str] = DEFAULT_MARKETS,
    feature_version: str = "v300",
    worker_names: Iterable[str] = DEFAULT_WORKERS,
    snapshot_max_age_days: int = 3,
    strict: bool = False,
) -> dict[str, Any]:
    store_dir = Path(feature_store_dir or os.getenv("FEATURE_SNAPSHOT_DIR") or Path(BASE_DIR) / "feature_snapshots")
    store = FeatureSnapshotStore(store_dir)
    checks: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strict": bool(strict),
        "workers": {},
        "feature_snapshots": {},
    }
    issues: list[str] = []

    for worker_name in worker_names:
        heartbeat = read_worker_heartbeat(worker_name)
        checks["workers"][worker_name] = heartbeat
        if strict and not heartbeat.get("online"):
            issues.append(f"{worker_name} worker offline")

    for market in markets:
        state = _snapshot_state(
            store,
            market=market,
            feature_version=feature_version,
            snapshot_max_age_days=snapshot_max_age_days,
        )
        checks["feature_snapshots"][market] = state
        if strict and state.get("state") != "fresh":
            issues.append(f"{market} feature snapshot {state.get('state')}")

    return {
        "ready": not issues,
        "version": "3.0.0",
        "checks": checks,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Fail when workers or snapshots are missing/stale.")
    parser.add_argument("--feature-store-dir", default=None)
    parser.add_argument("--feature-version", default="v300")
    parser.add_argument("--markets", default="CN,HK")
    parser.add_argument(
        "--workers",
        default="scan,backtest",
        help="Comma-separated worker names. Use prediction,market_refresh,scan,backtest for full deployment.",
    )
    parser.add_argument("--snapshot-max-age-days", type=int, default=3)
    args = parser.parse_args()

    report = build_report(
        feature_store_dir=args.feature_store_dir,
        markets=tuple(item.strip() for item in args.markets.split(",") if item.strip()),
        feature_version=args.feature_version,
        worker_names=tuple(item.strip() for item in args.workers.split(",") if item.strip()),
        snapshot_max_age_days=args.snapshot_max_age_days,
        strict=args.strict,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

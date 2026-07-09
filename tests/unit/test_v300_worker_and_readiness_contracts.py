"""Worker, readiness, and Docker contracts for v3.0.0."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.features.snapshot_store import FeatureSnapshotStore
from core.worker_status import write_worker_heartbeat
from scripts import deployment_readiness_check


ROOT = Path(__file__).resolve().parents[2]


def test_worker_compose_includes_all_v3_worker_profiles():
    source = (ROOT / "docker-compose.worker.yml").read_text(encoding="utf-8")

    for text in [
        "ai-worker:",
        "market-refresh-worker:",
        "scan-worker:",
        "backtest-worker:",
        "run_prediction_worker.py",
        "run_market_refresh_worker.py",
        "run_scan_worker.py",
        "run_backtest_worker.py",
        "SCAN_TASK_DB_PATH",
        "BACKTEST_TASK_DB_PATH",
        "SCAN_WORKER_POLL_SECONDS",
        "BACKTEST_WORKER_POLL_SECONDS",
        "mem_limit:",
    ]:
        assert text in source


def test_optimized_dockerfile_builds_native_kernel_only_when_requested():
    dockerfile = (ROOT / "Dockerfile.optimized").read_text(encoding="utf-8")
    worker_compose = (ROOT / "docker-compose.worker.yml").read_text(encoding="utf-8")

    assert "ARG INSTALL_NATIVE_KERNEL=false" in dockerfile
    assert "requirements.native.txt" in dockerfile
    assert "quant_kernel" in dockerfile
    assert "maturin" in dockerfile
    assert 'if [ "$INSTALL_NATIVE_KERNEL" = "true" ]' in dockerfile
    assert "QUANT_NATIVE_KERNEL=auto" in dockerfile
    assert "INSTALL_NATIVE_KERNEL:" in worker_compose


def test_readiness_reports_missing_worker_and_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKER_HEARTBEAT_DIR", str(tmp_path / "heartbeats"))

    report = deployment_readiness_check.build_report(
        feature_store_dir=tmp_path / "features",
        markets=("CN",),
        feature_version="v300",
        worker_names=("scan", "backtest"),
        strict=True,
    )

    assert report["ready"] is False
    assert report["checks"]["workers"]["scan"]["state"] == "offline"
    assert report["checks"]["feature_snapshots"]["CN"]["state"] == "missing"
    assert any("scan worker offline" in issue for issue in report["issues"])


def test_readiness_accepts_fresh_worker_heartbeats_and_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKER_HEARTBEAT_DIR", str(tmp_path / "heartbeats"))
    write_worker_heartbeat("scan", status="idle")
    write_worker_heartbeat("backtest", status="idle")
    FeatureSnapshotStore(tmp_path / "features").write(
        pd.DataFrame(
            {
                "ticker": ["AAPL", "MSFT"],
                "date": [pd.Timestamp("2026-06-26"), pd.Timestamp("2026-06-26")],
                "close": [10.0, 20.0],
            }
        ),
        market="CN",
        feature_version="v300",
    )

    report = deployment_readiness_check.build_report(
        feature_store_dir=tmp_path / "features",
        markets=("CN",),
        feature_version="v300",
        worker_names=("scan", "backtest"),
        snapshot_max_age_days=9999,
        strict=True,
    )

    assert report["ready"] is True
    assert report["checks"]["workers"]["scan"]["online"] is True
    assert report["checks"]["feature_snapshots"]["CN"]["state"] == "fresh"
    assert report["issues"] == []

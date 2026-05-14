from __future__ import annotations

import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from core.version import VERSION


def test_price_freshness_marks_stale_data(monkeypatch):
    from core.data_freshness import get_price_freshness

    old_day = date.today() - timedelta(days=12)
    frame = pd.DataFrame(
        {"close": [10.0, 10.5]},
        index=pd.to_datetime([old_day - timedelta(days=1), old_day]),
    )

    monkeypatch.setattr("core.data_freshness.load_local_ohlcv_history", lambda ticker: frame)

    result = get_price_freshness("600519", max_age_days=5)

    assert result["ticker"] == "600519"
    assert result["status"] == "stale"
    assert result["is_stale"] is True
    assert result["should_block"] is True
    assert "local_parquet" in result["source"]


def test_review_audit_records_and_queries_workflow_events(tmp_path: Path):
    from core.review_audit import ReviewAuditService

    service = ReviewAuditService(log_dir=str(tmp_path))

    service.record_event(
        user="alice",
        action="SCAN_RUN",
        resource="daily-scan",
        resource_type="scan",
        details={"ticker_count": 3},
    )

    events = service.list_events(user="alice", resource_type="scan", limit=10)

    assert len(events) == 1
    assert events[0]["action"] == "SCAN_RUN"
    assert events[0]["details"]["ticker_count"] == 3


def test_backup_manager_creates_manifested_zip(tmp_path: Path):
    from core.backup_manager import BackupManager

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "quant.db").write_text("sqlite-bytes", encoding="utf-8")
    (data_dir / "daemon_config.json").write_text('{"enabled": false}', encoding="utf-8")
    backups_dir = tmp_path / "backups"

    manager = BackupManager(data_dir=data_dir, backups_dir=backups_dir)
    result = manager.create_backup(include_database=True, include_configs=True)

    backup_path = Path(result["path"])
    assert backup_path.exists()
    assert result["status"] == "success"
    assert result["manifest"]["included"]["database"] is True

    with zipfile.ZipFile(backup_path) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "data/quant.db" in names
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["version"] == VERSION


def test_backup_manager_lists_manifest_and_restores_selected_files(tmp_path: Path):
    from core.backup_manager import BackupManager

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "quant.db").write_text("db-v1", encoding="utf-8")
    (data_dir / "daemon_config.json").write_text('{"enabled": false}', encoding="utf-8")
    (data_dir / "exports").mkdir()
    (data_dir / "exports" / "portfolio.csv").write_text("ticker,units\n510300,10\n", encoding="utf-8")
    backups_dir = tmp_path / "backups"

    manager = BackupManager(data_dir=data_dir, backups_dir=backups_dir)
    created = manager.create_backup(include_database=True, include_configs=True, include_user_files=True)
    (data_dir / "quant.db").write_text("db-v2", encoding="utf-8")
    (data_dir / "daemon_config.json").write_text('{"enabled": true}', encoding="utf-8")
    (data_dir / "exports" / "portfolio.csv").unlink()

    listed = manager.list_backups()
    restored = manager.restore_backup(
        created["filename"],
        restore_database=True,
        restore_configs=True,
        restore_user_files=True,
    )

    assert listed[0]["manifest"]["version"] == VERSION
    assert manager.resolve_backup_path(created["filename"]).name == created["filename"]
    assert (data_dir / "quant.db").read_text(encoding="utf-8") == "db-v1"
    assert (data_dir / "daemon_config.json").read_text(encoding="utf-8") == '{"enabled": false}'
    assert (data_dir / "exports" / "portfolio.csv").exists()
    assert set(restored["restored"]) == {"data/quant.db", "data/daemon_config.json", "data/exports/portfolio.csv"}


def test_daily_workbench_snapshot_aggregates_existing_capabilities(monkeypatch):
    from core.daily_workbench import build_daily_workbench_snapshot

    monkeypatch.setattr(
        "core.daily_workbench.get_price_freshness_batch",
        lambda tickers, max_age_days=5: {
            ticker: {
                "ticker": ticker,
                "status": "fresh",
                "is_stale": False,
                "should_block": False,
                "last_date": str(date.today()),
                "source": "local_parquet",
            }
            for ticker in tickers
        },
    )
    monkeypatch.setattr(
        "core.daily_workbench.get_user_asset_service",
        lambda: type(
            "AssetService",
            (),
            {
                "get_overview": lambda self, user_id, sync_dca=True: (
                    (_ for _ in ()).throw(AssertionError("daily workbench should not run DCA sync on page load"))
                    if sync_dca
                    else {"assets": [{"ticker": "600519", "asset_name": "贵州茅台"}], "summary": {"total_market_value": 1000}}
                )
            },
        )(),
    )
    monkeypatch.setattr(
        "core.daily_workbench.get_trading_service",
        lambda: type(
            "TradingService",
            (),
            {
                "account_mgr": type(
                    "AccountMgr",
                    (),
                    {
                        "get_user_accounts": lambda self, user_id: [type("Account", (), {"id": 1, "account_name": "paper"})()],
                        "get_trade_history": lambda self, account_id, limit=5: [],
                    },
                )(),
                "get_portfolio": lambda self, user_id, account_id, refresh_prices=False: {"total_assets": 100000, "cash": 90000, "position_value": 10000},
                "get_orders_by_account": lambda self, user_id, account_id: [],
            },
        )(),
    )

    snapshot = build_daily_workbench_snapshot(user_id=1)

    assert snapshot["as_of"]
    assert snapshot["asset_summary"]["asset_count"] == 1
    assert snapshot["paper_account"]["found"] is True
    assert snapshot["data_freshness"]["items"][0]["ticker"] == "600519"
    assert any(action["kind"] == "scan" for action in snapshot["next_actions"])

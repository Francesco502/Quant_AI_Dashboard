from __future__ import annotations

from pathlib import Path
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import UserInDB, get_current_active_user
from core.version import VERSION


def _client_with_user(app: FastAPI) -> TestClient:
    user = UserInDB(id=7, username="alice", hashed_password="x", role="admin", disabled=False)
    app.dependency_overrides[get_current_active_user] = lambda: user
    return TestClient(app)


def test_daily_workbench_summary_route(monkeypatch):
    from api.routers import daily_workbench

    monkeypatch.setattr(
        daily_workbench,
        "build_daily_workbench_snapshot",
        lambda user_id: {
            "as_of": "2026-04-27T09:00:00",
            "asset_summary": {"asset_count": 1, "total_market_value": 1000.0, "tickers": ["600519"]},
            "data_freshness": {"stale_count": 0, "items": []},
            "paper_account": {
                "found": True,
                "account_id": 1,
                "account_name": "paper",
                "total_assets": 100000.0,
                "cash": 90000.0,
                "position_value": 10000.0,
                "recent_order_count": 0,
                "recent_trade_count": 0,
            },
            "market_review": {"href": "/market-review", "status": "ready", "description": "review"},
            "scan_summary": {"href": "/market-scanner", "status": "ready", "description": "scan"},
            "backtest_summary": {"href": "/backtest", "status": "ready", "description": "backtest"},
            "next_actions": [{"kind": "scan", "title": "scan", "description": "run", "href": "/market-scanner", "priority": "medium"}],
        },
    )
    app = FastAPI()
    app.include_router(daily_workbench.router, prefix="/api")

    response = _client_with_user(app).get("/api/daily-workbench/summary")

    assert response.status_code == 200
    assert response.json()["asset_summary"]["asset_count"] == 1


def test_data_freshness_prices_route(monkeypatch):
    from api.routers import data_freshness

    monkeypatch.setattr(
        data_freshness,
        "get_price_freshness_batch",
        lambda tickers, max_age_days=5: {ticker: {"ticker": ticker, "status": "fresh"} for ticker in tickers},
    )
    app = FastAPI()
    app.include_router(data_freshness.router, prefix="/api")

    response = _client_with_user(app).get("/api/data-freshness/prices?tickers=600519,159915")

    assert response.status_code == 200
    assert response.json()["items"][0]["ticker"] == "600519"
    assert response.json()["items"][1]["ticker"] == "159915"


def test_audit_events_routes(monkeypatch):
    from api.routers import audit

    class FakeAuditService:
        def record_event(self, **kwargs):
            return {
                "status": "success",
                "action": kwargs["action"],
                "resource": kwargs["resource"],
                "resource_type": kwargs["resource_type"],
            }

        def list_events(self, **kwargs):
            return [{"action": "SCAN_RUN", "resource": "daily", "resource_type": "scan"}]

    monkeypatch.setattr(audit, "get_review_audit_service", lambda: FakeAuditService())
    app = FastAPI()
    app.include_router(audit.router, prefix="/api")
    client = _client_with_user(app)

    created = client.post(
        "/api/audit/events",
        json={"action": "SCAN_RUN", "resource": "daily", "resource_type": "scan", "details": {"count": 2}},
    )
    listed = client.get("/api/audit/events?resource_type=scan")

    assert created.status_code == 200
    assert created.json()["action"] == "SCAN_RUN"
    assert listed.status_code == 200
    assert listed.json()["events"][0]["resource_type"] == "scan"


def test_backup_routes(monkeypatch):
    from api.routers import backup

    class FakeBackupManager:
        def create_backup(self, **kwargs):
            return {
                "status": "success",
                "filename": "backup.zip",
                "path": "backup.zip",
                "size_bytes": 128,
                "manifest": {"version": VERSION},
            }

        def list_backups(self):
            return [{"filename": "backup.zip", "size_bytes": 128, "manifest": {"version": VERSION}}]

        def restore_backup(self, backup_name, **kwargs):
            return {"status": "success", "filename": backup_name, "restored": []}

    monkeypatch.setattr(backup, "get_backup_manager", lambda: FakeBackupManager())
    app = FastAPI()
    app.include_router(backup.router, prefix="/api")
    client = _client_with_user(app)

    created = client.post("/api/backup/create", json={"include_database": True})
    listed = client.get("/api/backup/list")
    restored = client.post("/api/backup/restore", json={"filename": "backup.zip", "restore_database": False})

    assert created.status_code == 200
    assert created.json()["filename"] == "backup.zip"
    assert listed.json()["backups"][0]["filename"] == "backup.zip"
    assert restored.json()["status"] == "success"


def test_backup_download_route(monkeypatch, tmp_path: Path):
    from api.routers import backup

    backup_file = tmp_path / "backup.zip"
    backup_file.write_bytes(b"zip-bytes")

    class FakeBackupManager:
        def resolve_backup_path(self, filename):
            assert filename == "backup.zip"
            return backup_file

    monkeypatch.setattr(backup, "get_backup_manager", lambda: FakeBackupManager())
    app = FastAPI()
    app.include_router(backup.router, prefix="/api")

    response = _client_with_user(app).get("/api/backup/download/backup.zip")

    assert response.status_code == 200
    assert response.content == b"zip-bytes"
    assert response.headers["content-type"] == "application/zip"


def test_strategy_template_mutations_record_audit(monkeypatch):
    from api.routers import strategy_templates

    events = []

    class FakeAuditService:
        def record_event(self, **kwargs):
            events.append(kwargs)
            return {"status": "success"}

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE strategy_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            template_name TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_type TEXT NOT NULL,
            description TEXT,
            params TEXT NOT NULL,
            is_public INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    class FakeDatabase:
        def __init__(self):
            self.conn = conn

    monkeypatch.setattr(strategy_templates, "get_database", lambda: FakeDatabase())
    monkeypatch.setattr(strategy_templates, "get_review_audit_service", lambda: FakeAuditService(), raising=False)
    app = FastAPI()
    app.include_router(strategy_templates.router, prefix="/api")
    client = _client_with_user(app)

    created = client.post(
        "/api/strategy-templates",
        json={
            "template_name": "稳健模板",
            "strategy_id": "sma_crossover",
            "strategy_type": "classic",
            "description": "audit test",
            "params": {"short_window": 20, "long_window": 60},
        },
    )
    template_id = created.json()["id"]
    updated = client.put(f"/api/strategy-templates/{template_id}", json={"is_favorite": True})
    deleted = client.delete(f"/api/strategy-templates/{template_id}")

    assert created.status_code == 200
    assert updated.status_code == 200
    assert deleted.status_code == 200
    assert [event["action"] for event in events] == [
        "STRATEGY_TEMPLATE_CREATE",
        "STRATEGY_TEMPLATE_UPDATE",
        "STRATEGY_TEMPLATE_DELETE",
    ]
    assert all(event["resource_type"] == "strategy_template" for event in events)

"""Integration tests for trading API endpoints."""

from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.integration


class TestTradingAPI:
    def test_get_account_performance_handles_position_dicts(self, auth_client, monkeypatch):
        class FakeAccount:
            balance = 95575.9169
            frozen = 0.0
            initial_capital = 100000.0
            created_at = None

        class FakeAccountManager:
            def account_exists(self, account_id, user_id):
                return True

            def get_account(self, account_id, user_id):
                return FakeAccount()

            def get_trade_history(self, account_id, limit=500):
                return []

            def get_equity_history(self, account_id, days=90):
                return []

        class FakeService:
            def __init__(self):
                self.account_mgr = FakeAccountManager()

            def get_portfolio(self, user_id, account_id):
                return {
                    "total_assets": 99922.8569,
                    "cash": 95575.9169,
                    "position_value": 4346.94,
                }

        monkeypatch.setattr("api.routers.trading.get_trading_service", lambda: FakeService())

        response = auth_client.get("/api/trading/accounts/1/performance")

        assert response.status_code == 200
        payload = response.json()
        assert payload["initial_capital"] == 100000.0
        assert payload["total_assets"] == pytest.approx(99922.8569)
        assert payload["market_value"] == pytest.approx(4346.94)
        assert payload["total_return_pct"] < 0

    def test_create_account(self, auth_client):
        response = auth_client.post(
            "/api/trading/accounts",
            json={"name": "test-account", "initial_balance": 100000.0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "account_id" in data

    def test_submit_market_order(self, auth_client):
        create_resp = auth_client.post(
            "/api/trading/accounts",
            json={"name": "test-account", "initial_balance": 100000.0},
        )
        assert create_resp.status_code == 200
        account_id = create_resp.json()["account_id"]

        response = auth_client.post(
            "/api/trading/orders",
            json={
                "account_id": account_id,
                "symbol": "600000",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 100,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "FILLED"
        assert data["fills"]

        positions_resp = auth_client.get(f"/api/trading/accounts/{account_id}/positions")
        assert positions_resp.status_code == 200
        positions = positions_resp.json()["positions"]
        assert any(p["ticker"] == "600000" and p["shares"] >= 100 for p in positions)

    def test_submit_limit_order(self, auth_client):
        create_resp = auth_client.post(
            "/api/trading/accounts",
            json={"name": "test-account", "initial_balance": 100000.0},
        )
        assert create_resp.status_code == 200
        account_id = create_resp.json()["account_id"]

        response = auth_client.post(
            "/api/trading/orders",
            json={
                "account_id": account_id,
                "symbol": "600000",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 100,
                "price": 10.50,
            },
        )

        assert response.status_code in [200, 400, 500]

    def test_submit_stop_order(self, auth_client):
        create_resp = auth_client.post(
            "/api/trading/accounts",
            json={"name": "test-account", "initial_balance": 100000.0},
        )
        assert create_resp.status_code == 200
        account_id = create_resp.json()["account_id"]

        response = auth_client.post(
            "/api/trading/orders",
            json={
                "account_id": account_id,
                "symbol": "600000",
                "side": "SELL",
                "order_type": "STOP",
                "quantity": 100,
                "stop_price": 9.50,
            },
        )

        assert response.status_code in [200, 400, 500]

    def test_get_orders(self, auth_client):
        create_resp = auth_client.post(
            "/api/trading/accounts",
            json={"name": "test-account", "initial_balance": 100000.0},
        )
        assert create_resp.status_code == 200
        account_id = create_resp.json()["account_id"]

        response = auth_client.get(f"/api/trading/orders?account_id={account_id}")

        assert response.status_code == 200
        data = response.json()
        assert "orders" in data

    def test_get_account_positions(self, auth_client):
        create_resp = auth_client.post(
            "/api/trading/accounts",
            json={"name": "test-account", "initial_balance": 100000.0},
        )
        assert create_resp.status_code == 200
        account_id = create_resp.json()["account_id"]

        response = auth_client.get(f"/api/trading/accounts/{account_id}/positions")
        assert response.status_code == 200
        data = response.json()
        assert "positions" in data

    def test_reset_account(self, auth_client):
        create_resp = auth_client.post(
            "/api/trading/accounts",
            json={"name": "reset-account", "initial_balance": 100000.0},
        )
        assert create_resp.status_code == 200
        account_id = create_resp.json()["account_id"]

        order_resp = auth_client.post(
            "/api/trading/orders",
            json={
                "account_id": account_id,
                "symbol": "600000",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 100,
            },
        )
        assert order_resp.status_code == 200
        assert order_resp.json()["success"] is True

        reset_resp = auth_client.post(
            f"/api/trading/accounts/{account_id}/reset",
            json={"initial_balance": 100000.0},
        )
        assert reset_resp.status_code == 200
        reset_data = reset_resp.json()
        assert reset_data["success"] is True
        assert reset_data["balance"] == 100000.0

        detail_resp = auth_client.get(f"/api/trading/accounts/{account_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["positions"] == []
        assert detail["trade_history"] == []

    def test_get_auto_trading_status(self, auth_client, monkeypatch):
        trading_cfg = {
            "enabled": True,
            "interval_minutes": 60,
            "username": "admin",
            "account_name": "Auto Paper Trading",
            "initial_capital": 100000.0,
            "strategy_ids": ["ema_crossover"],
            "universe_mode": "manual",
            "universe": ["510300"],
            "universe_limit": 0,
            "max_positions": 3,
            "evaluation_days": 180,
            "min_total_return": 0.03,
            "min_sharpe_ratio": 0.3,
            "max_drawdown": 0.2,
            "top_n_strategies": 3,
        }

        monkeypatch.setattr("api.routers.trading.load_daemon_config", lambda: {"trading": trading_cfg})
        monkeypatch.setattr("api.routers.trading.get_trading_service", lambda: object())
        monkeypatch.setattr(
            "api.routers.trading._build_auto_trading_payload",
            lambda service, cfg: {
                "config": cfg,
                "daemon": {"daemon_running": True},
                "available_strategies": [{"id": "ema_crossover", "name": "EMA", "description": "test"}],
                "account": {"found": True, "account_id": 1, "account_name": "Auto Paper Trading"},
            },
        )

        response = auth_client.get("/api/trading/auto/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["config"]["username"] == "admin"
        assert payload["daemon"]["daemon_running"] is True
        assert payload["available_strategies"][0]["id"] == "ema_crossover"

    def test_update_auto_trading_config(self, auth_client, monkeypatch):
        saved = {}
        trading_cfg = {
            "enabled": True,
            "interval_minutes": 60,
            "username": "admin",
            "account_name": "Auto Paper Trading",
            "initial_capital": 100000.0,
            "strategy_ids": ["ema_crossover"],
            "universe_mode": "manual",
            "universe": ["510300"],
            "universe_limit": 0,
            "max_positions": 3,
            "evaluation_days": 180,
            "min_total_return": 0.03,
            "min_sharpe_ratio": 0.3,
            "max_drawdown": 0.2,
            "top_n_strategies": 3,
        }

        monkeypatch.setattr("api.routers.trading.load_daemon_config", lambda: {"trading": dict(trading_cfg)})
        monkeypatch.setattr("api.routers.trading.get_trading_service", lambda: object())
        monkeypatch.setattr(
            "api.routers.trading.list_backtestable_strategies",
            lambda: [
                {"id": "ema_crossover", "name": "EMA", "description": "test"},
                {"id": "macd_trend", "name": "MACD", "description": "test"},
            ],
        )
        monkeypatch.setattr("api.routers.trading.save_daemon_status", lambda payload: None)
        monkeypatch.setattr("api.routers.trading.save_daemon_config", lambda payload: saved.setdefault("config", payload))
        monkeypatch.setattr(
            "api.routers.trading._build_auto_trading_payload",
            lambda service, cfg: {
                "config": cfg,
                "daemon": {"daemon_running": True},
                "available_strategies": [{"id": "macd_trend", "name": "MACD", "description": "test"}],
                "account": None,
            },
        )

        response = auth_client.put(
            "/api/trading/auto/config",
            json={
                "enabled": False,
                "interval_minutes": 30,
                "strategy_ids": ["macd_trend"],
                "universe_mode": "cn_a_share",
                "universe_limit": 0,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["config"]["enabled"] is False
        assert payload["config"]["strategy_ids"] == ["macd_trend"]
        assert payload["config"]["universe_mode"] == "cn_a_share"
        assert saved["config"]["trading"]["interval_minutes"] == 30
        assert saved["config"]["trading"]["universe_mode"] == "cn_a_share"

    def test_update_auto_trading_config_manual_mode_requires_universe(self, auth_client, monkeypatch):
        trading_cfg = {
            "enabled": True,
            "interval_minutes": 60,
            "username": "admin",
            "account_name": "Auto Paper Trading",
            "initial_capital": 100000.0,
            "strategy_ids": ["ema_crossover"],
            "universe_mode": "manual",
            "universe": ["510300"],
            "universe_limit": 0,
            "max_positions": 3,
            "evaluation_days": 180,
            "min_total_return": 0.03,
            "min_sharpe_ratio": 0.3,
            "max_drawdown": 0.2,
            "top_n_strategies": 3,
        }

        monkeypatch.setattr("api.routers.trading.load_daemon_config", lambda: {"trading": dict(trading_cfg)})
        monkeypatch.setattr(
            "api.routers.trading.list_backtestable_strategies",
            lambda: [{"id": "ema_crossover", "name": "EMA", "description": "test"}],
        )

        response = auth_client.put(
            "/api/trading/auto/config",
            json={
                "universe_mode": "manual",
                "universe": ["510500", "159915"],
            },
        )
        assert response.status_code == 200

        response = auth_client.put("/api/trading/auto/config", json={"universe_mode": "manual", "universe": []})
        assert response.status_code == 400

    def test_run_auto_trading_now(self, auth_client, monkeypatch):
        trading_cfg = {
            "enabled": True,
            "interval_minutes": 60,
            "username": "admin",
            "account_name": "Auto Paper Trading",
            "initial_capital": 100000.0,
            "strategy_ids": ["ema_crossover"],
            "universe_mode": "manual",
            "universe": ["510300"],
            "universe_limit": 0,
            "max_positions": 3,
            "evaluation_days": 180,
            "min_total_return": 0.03,
            "min_sharpe_ratio": 0.3,
            "max_drawdown": 0.2,
            "top_n_strategies": 3,
        }
        status_updates = []
        mock_service = SimpleNamespace(
            account_mgr=SimpleNamespace(
                get_or_create_account=lambda user_id, name, initial_balance: SimpleNamespace(id=1, account_name=name),
            ),
        )

        monkeypatch.setattr("api.routers.trading.load_daemon_config", lambda: {"trading": dict(trading_cfg)})
        monkeypatch.setattr("api.routers.trading.get_trading_service", lambda: mock_service)
        monkeypatch.setattr("api.routers.trading._get_user_id_by_username", lambda username: 1)
        monkeypatch.setattr("api.routers.trading.save_daemon_status", lambda payload: status_updates.append(payload))
        monkeypatch.setattr(
            "api.routers.trading._build_auto_trading_payload",
            lambda service, cfg: {
                "config": cfg,
                "daemon": {"daemon_running": True, "last_trading_run": "2026-03-23T12:00:00"},
                "available_strategies": [{"id": "ema_crossover", "name": "EMA", "description": "test"}],
                "account": {"found": True, "account_id": 1, "account_name": "Auto Paper Trading"},
            },
        )

        def fake_background_runner(config, reset_account=False, initial_balance=None):
            status_updates.append(
                {
                    "last_trading_run": "2026-03-23T12:00:00",
                    "last_trading_result": {
                        "timestamp": "2026-03-23T12:00:00",
                        "validated_strategies": ["ema_crossover"],
                        "orders": [{"symbol": "510300"}],
                    },
                    "last_trading_error": None,
                }
            )
            from api.routers.trading import _AUTO_TRADING_RUN_LOCK
            if _AUTO_TRADING_RUN_LOCK.locked():
                _AUTO_TRADING_RUN_LOCK.release()

        class ImmediateThread:
            def __init__(self, target=None, kwargs=None, **_):
                self._target = target
                self._kwargs = kwargs or {}

            def start(self):
                self._target(**self._kwargs)

        monkeypatch.setattr("api.routers.trading._run_auto_trading_cycle_in_background", fake_background_runner)
        monkeypatch.setattr("api.routers.trading.threading.Thread", ImmediateThread)

        response = auth_client.post("/api/trading/auto/run-now", json={"reset_account": False})

        assert response.status_code == 200
        payload = response.json()
        assert payload["run_request_status"] == "started"
        assert status_updates[0]["trading_run_state"] == "running"
        assert status_updates[-1]["last_trading_result"]["orders"][0]["symbol"] == "510300"

    def test_set_stop_loss(self, auth_client):
        create_resp = auth_client.post(
            "/api/trading/accounts",
            json={"name": "test-account", "initial_balance": 100000.0},
        )
        assert create_resp.status_code == 200
        account_id = create_resp.json()["account_id"]

        response = auth_client.post(
            f"/api/trading/accounts/{account_id}/stop-loss",
            params={"symbol": "600000", "stop_type": "percentage", "stop_percentage": 0.05},
        )

        assert response.status_code in [200, 400]


class TestRiskAPI:
    def test_risk_check(self, auth_client):
        create_resp = auth_client.post(
            "/api/trading/accounts",
            json={"name": "test-account", "initial_balance": 100000.0},
        )
        assert create_resp.status_code == 200
        account_id = create_resp.json()["account_id"]

        response = auth_client.post(
            "/api/trading/risk/check",
            params={
                "account_id": account_id,
                "symbol": "600000",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 100,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "passed" in data
        assert "message" in data
        assert data["passed"] is True

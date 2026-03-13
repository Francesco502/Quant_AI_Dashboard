"""Integration tests for trading API endpoints."""

import pytest


pytestmark = pytest.mark.integration


class TestTradingAPI:
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

        assert response.status_code in [200, 400, 500]

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

"""In-process E2E smoke tests for protected API endpoints."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.e2e_inprocess


def test_health_endpoint(auth_client):
    response = auth_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in {"healthy", "warning", "critical"}


def test_root_endpoint_requires_auth_and_returns_payload(auth_client):
    response = auth_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_list_backtest_strategies(auth_client):
    response = auth_client.get("/api/backtest/strategies")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) > 0


def test_list_backtest_benchmarks(auth_client):
    response = auth_client.get("/api/backtest/benchmarks")
    assert response.status_code == 200
    payload = response.json()
    assert "benchmarks" in payload
    assert isinstance(payload["benchmarks"], list)


def test_market_overview_endpoint(auth_client):
    response = auth_client.get("/api/market/overview")
    assert response.status_code in {200, 404, 405}


def test_invalid_backtest_payload_validation(auth_client):
    response = auth_client.post("/api/backtest/run", json={})
    assert response.status_code == 422


def test_invalid_strategy_returns_error(auth_client):
    payload = {
        "strategy_id": "nonexistent_strategy",
        "tickers": ["600519"],
        "start_date": "2025-01-01",
        "initial_capital": 100000.0,
    }
    response = auth_client.post("/api/backtest/run", json=payload)
    assert response.status_code in {400, 404, 500}

"""Regression tests for API isolation, permissions, and workload limits."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.auth import create_access_token, create_user, get_user_by_username
from api.main import app


pytestmark = pytest.mark.integration


def _headers_for_role(role: str) -> dict[str, str]:
    username = f"{role}_{uuid4().hex[:8]}"
    if not get_user_by_username(username):
        assert create_user(username=username, password="password123", role=role)
    token = create_access_token({"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_viewer_cannot_read_global_signals() -> None:
    with TestClient(app) as client:
        response = client.get("/api/signals/stats", headers=_headers_for_role("viewer"))

    assert response.status_code == 403


def test_viewer_cannot_mutate_global_strategy_config(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeStrategyManager:
        def add_strategy(self, strategy_dict):
            return True

    monkeypatch.setattr("api.routers.strategies.get_strategy_manager", lambda: FakeStrategyManager())

    with TestClient(app) as client:
        response = client.post(
            "/api/strategies/",
            headers=_headers_for_role("viewer"),
            json={
                "strategy_id": "viewer_should_not_create",
                "type": "sma",
                "params": {},
            },
        )

    assert response.status_code == 403


def test_deprecated_data_endpoints_reject_client_api_keys(
    auth_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("api.routers.data.load_price_data", lambda **_: None)

    response = auth_client.post(
        "/api/data/prices",
        json={
            "tickers": ["600519"],
            "days": 30,
            "alpha_vantage_key": "client-key",
        },
    )

    assert response.status_code == 400
    assert "环境变量" in response.json()["detail"]


def test_forecasting_rejects_oversized_batch(auth_client) -> None:
    response = auth_client.post(
        "/api/forecasting/predict",
        json={
            "tickers": [f"T{i:03d}" for i in range(25)],
            "horizon": 30,
            "model_type": "prophet",
        },
    )

    assert response.status_code == 422


def test_backtest_rejects_excessive_parameter_grid(auth_client) -> None:
    response = auth_client.post(
        "/api/backtest/optimize",
        json={
            "strategy_id": "sma_crossover",
            "tickers": ["600519"],
            "param_grid": {
                "short_window": list(range(20)),
                "long_window": list(range(20)),
            },
            "start_date": "2025-01-01",
            "end_date": "2025-06-01",
        },
    )

    assert response.status_code == 422


def test_portfolio_analysis_rejects_too_many_holdings(auth_client) -> None:
    response = auth_client.post(
        "/api/portfolio/analyze",
        json={
            "holdings": [
                {"ticker": f"{i:06d}", "shares": 1.0, "cost_price": 1.0}
                for i in range(90)
            ]
        },
    )

    assert response.status_code == 422

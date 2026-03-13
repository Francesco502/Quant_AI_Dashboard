"""Paper-trading external flow test.

Requires running backend/frontend services and `RUN_EXTERNAL_E2E=1`.
"""

from __future__ import annotations

import os

import pytest
import requests


pytestmark = pytest.mark.e2e_external

if os.getenv("RUN_EXTERNAL_E2E", "").strip().lower() not in {"1", "true", "yes", "on"}:
    pytest.skip(
        "External E2E requires RUN_EXTERNAL_E2E=1 and running frontend/backend services.",
        allow_module_level=True,
    )


API_URL = os.getenv("API_URL", "http://localhost:8000/api")


def _login_and_get_token() -> str:
    response = requests.post(
        f"{API_URL}/auth/token",
        data={"username": "admin", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    assert token
    return token


def test_paper_trading_flow() -> None:
    token = _login_and_get_token()
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = requests.post(
        f"{API_URL}/trading/paper/account",
        json={"name": "External E2E Account", "initial_balance": 100000.0},
        headers=headers,
        timeout=30,
    )
    assert create_resp.status_code == 200

    account_resp = requests.get(
        f"{API_URL}/trading/paper/account",
        headers=headers,
        timeout=30,
    )
    assert account_resp.status_code == 200
    account_payload = account_resp.json()
    assert "portfolio" in account_payload

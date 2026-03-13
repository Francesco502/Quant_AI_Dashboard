"""Paper-trading external flow test.

Requires running backend/frontend services and `RUN_EXTERNAL_E2E=1`.
"""

from __future__ import annotations

import os
import uuid

import pytest
import requests


pytestmark = pytest.mark.e2e_external

if os.getenv("RUN_EXTERNAL_E2E", "").strip().lower() not in {"1", "true", "yes", "on"}:
    pytest.skip(
        "External E2E requires RUN_EXTERNAL_E2E=1 and running frontend/backend services.",
        allow_module_level=True,
    )


API_URL = os.getenv("API_URL", "http://localhost:8685/api")
TEST_LOGIN_USERNAME = os.getenv("TEST_LOGIN_USERNAME", "")
TEST_LOGIN_PASSWORD = os.getenv("TEST_LOGIN_PASSWORD", "")


def _ensure_login_credentials() -> tuple[str, str]:
    if TEST_LOGIN_USERNAME and TEST_LOGIN_PASSWORD:
        return TEST_LOGIN_USERNAME, TEST_LOGIN_PASSWORD

    username = f"paper_{uuid.uuid4().hex[:8]}"
    password = "PaperTrading123!"
    response = requests.post(
        f"{API_URL}/auth/register",
        json={"username": username, "password": password},
        timeout=20,
    )
    response.raise_for_status()
    return username, password


def _login_and_get_token() -> str:
    username, password = _ensure_login_credentials()
    response = requests.post(
        f"{API_URL}/auth/token",
        data={"username": username, "password": password},
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
        f"{API_URL}/trading/accounts",
        json={"name": "External E2E Account", "initial_balance": 100000.0},
        headers=headers,
        timeout=30,
    )
    assert create_resp.status_code == 200
    account_id = create_resp.json()["account_id"]

    account_resp = requests.get(
        f"{API_URL}/trading/accounts/{account_id}/positions",
        headers=headers,
        timeout=30,
    )
    assert account_resp.status_code == 200
    account_payload = account_resp.json()
    assert "positions" in account_payload

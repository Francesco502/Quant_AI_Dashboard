"""Release validation tests that rely on externally running services.

These tests are intentionally excluded from default CI and local quick runs.
Enable with `RUN_EXTERNAL_E2E=1`.
"""

from __future__ import annotations

import os
import uuid

import pytest
import requests
from playwright.sync_api import sync_playwright


pytestmark = pytest.mark.e2e_external

if os.getenv("RUN_EXTERNAL_E2E", "").strip().lower() not in {"1", "true", "yes", "on"}:
    pytest.skip(
        "External E2E requires RUN_EXTERNAL_E2E=1 and running frontend/backend services.",
        allow_module_level=True,
    )


API_URL = os.getenv("API_URL", "http://localhost:8685/api")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8686")
TEST_LOGIN_USERNAME = os.getenv("TEST_LOGIN_USERNAME", "")
TEST_LOGIN_PASSWORD = os.getenv("TEST_LOGIN_PASSWORD", "")


def _ensure_login_credentials() -> tuple[str, str]:
    if TEST_LOGIN_USERNAME and TEST_LOGIN_PASSWORD:
        return TEST_LOGIN_USERNAME, TEST_LOGIN_PASSWORD

    username = f"e2e_{uuid.uuid4().hex[:8]}"
    password = "ReleaseValidation123!"
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


def test_api_health() -> None:
    response = requests.get(f"{API_URL}/health", timeout=20)
    assert response.status_code == 200
    assert response.json().get("status") in {"healthy", "warning", "critical"}


def test_login_api() -> None:
    token = _login_and_get_token()
    assert isinstance(token, str) and len(token) > 10


def test_protected_endpoint_with_token() -> None:
    token = _login_and_get_token()
    response = requests.get(
        f"{API_URL}/backtest/strategies",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_login_ui_stores_token() -> None:
    username, password = _ensure_login_credentials()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{FRONTEND_URL}/login")
        page.wait_for_load_state("networkidle")

        page.fill('input[id="username"]', username)
        page.fill('input[id="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(1500)

        token = page.evaluate("localStorage.getItem('token')")
        assert token is not None
        browser.close()

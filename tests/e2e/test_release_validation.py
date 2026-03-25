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
EXPECT_RELEASE_READY = os.getenv("EXPECT_RELEASE_READY", "").strip().lower() in {"1", "true", "yes", "on"}
FRONTEND_STATIC_EXPORT = os.getenv("FRONTEND_STATIC_EXPORT", "").strip().lower() in {"1", "true", "yes", "on"}


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


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_login_and_get_token()}"}


def _health_payload() -> dict:
    response = requests.get(f"{API_URL}/health", timeout=20)
    response.raise_for_status()
    return response.json()


def _frontend_page_url(path: str) -> str:
    normalized = path.strip().lstrip("/")
    if FRONTEND_STATIC_EXPORT:
        if not normalized:
            return f"{FRONTEND_URL.rstrip('/')}/index.html"
        return f"{FRONTEND_URL.rstrip('/')}/{normalized}.html"
    return f"{FRONTEND_URL.rstrip('/')}/{normalized}"


def test_api_health() -> None:
    payload = _health_payload()
    assert payload.get("status") in {"healthy", "warning", "critical"}


def test_health_exposes_security_readiness() -> None:
    payload = _health_payload()
    security = payload.get("security")

    assert isinstance(security, dict)
    assert "ready" in security
    assert "issues" in security
    assert "strict_mode" in security

    if EXPECT_RELEASE_READY:
        assert security["ready"] is True, security["issues"]


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


def test_protected_endpoint_requires_token() -> None:
    response = requests.get(f"{API_URL}/backtest/strategies", timeout=20)
    assert response.status_code == 401


def test_llm_runtime_validation_matches_config() -> None:
    headers = _auth_headers()
    config_response = requests.get(
        f"{API_URL}/llm-analysis/config",
        headers=headers,
        timeout=20,
    )
    assert config_response.status_code == 200
    config = config_response.json()

    provider_ready = bool(config.get("configured") and config.get("available"))

    health_response = requests.get(
        f"{API_URL}/llm-analysis/health-check",
        headers=headers,
        timeout=60,
    )
    agent_response = requests.post(
        f"{API_URL}/agent/research",
        headers=headers,
        json={"query": "总结 600519 的两条核心风险。"},
        timeout=60,
    )

    if provider_ready:
        assert health_response.status_code == 200
        assert health_response.json().get("status") == "ok"
        assert agent_response.status_code == 200
    else:
        assert health_response.status_code == 503
        assert agent_response.status_code == 503


def test_login_ui_stores_token() -> None:
    username, password = _ensure_login_credentials()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(_frontend_page_url("login"))
        page.wait_for_load_state("networkidle")

        page.fill('input[id="username"]', username)
        page.fill('input[id="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(1500)

        token = page.evaluate("localStorage.getItem('token')")
        assert token is not None
        browser.close()

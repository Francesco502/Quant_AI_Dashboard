"""UI smoke tests for externally running frontend app."""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect


pytestmark = [pytest.mark.e2e, pytest.mark.e2e_external]

if os.getenv("RUN_EXTERNAL_E2E", "").strip().lower() not in {"1", "true", "yes", "on"}:
    pytest.skip(
        "UI E2E requires RUN_EXTERNAL_E2E=1 and running frontend app.",
        allow_module_level=True,
    )


BASE_URL = os.getenv("FRONTEND_URL", "http://localhost:8686")
ADMIN_USERNAME = os.getenv("TEST_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "admin123")


def _login(page: Page) -> None:
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")
    page.locator("#username").fill(ADMIN_USERNAME)
    page.locator("#password").fill(ADMIN_PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_function("() => !!localStorage.getItem('token')", timeout=15000)
    page.wait_for_function("() => window.location.pathname === '/'", timeout=30000)


def test_dashboard_loads(page: Page) -> None:
    _login(page)
    expect(page.locator("body")).to_contain_text("今日状态")


def test_trading_page_loads(page: Page) -> None:
    _login(page)
    page.goto(f"{BASE_URL}/trading")
    page.wait_for_load_state("networkidle")
    expect(page.locator("body")).to_contain_text("模拟交易工作台")

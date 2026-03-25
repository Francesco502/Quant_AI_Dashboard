"""UI smoke tests for auth flow and main pages with running local services."""

from __future__ import annotations

import os
import uuid

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


def _login(page: Page, username: str, password: str) -> None:
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.get_by_role("button", name="Login").click()
    page.wait_for_load_state("networkidle")
    expect(page).to_have_url(f"{BASE_URL}/")


def test_register_then_login_new_user(page: Page) -> None:
    username = f"ui_{uuid.uuid4().hex[:8]}"
    password = "StrongPass123!"

    page.goto(f"{BASE_URL}/register")
    page.wait_for_load_state("networkidle")
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#confirmPassword").fill(password)
    page.get_by_role("button", name="注册").click()

    expect(page.get_by_text("注册成功! 正在跳转到登录页面...")).to_be_visible()
    page.wait_for_url(f"{BASE_URL}/login", timeout=5000)

    _login(page, username, password)


def test_admin_login_and_settings_health(page: Page) -> None:
    _login(page, ADMIN_USERNAME, ADMIN_PASSWORD)

    page.goto(f"{BASE_URL}/settings")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("系统健康 (System Health)")).to_be_visible()
    expect(page.get_by_text("API 服务 (API Server)")).to_be_visible()
    expect(page.get_by_text("离线 (Offline)")).not_to_be_visible()


@pytest.mark.parametrize(
    "route,expected_text",
    [
        ("/", "市场概览"),
        ("/market", "市场"),
        ("/trading", "Trading"),
        ("/backtest", "Backtest"),
        ("/portfolio", "Portfolio"),
        ("/strategies", "Strategies"),
    ],
)
def test_main_pages_render_without_fatal_error(page: Page, route: str, expected_text: str) -> None:
    _login(page, ADMIN_USERNAME, ADMIN_PASSWORD)

    page.goto(f"{BASE_URL}{route}")
    page.wait_for_load_state("networkidle")

    expect(page.locator("body")).to_contain_text(expected_text)
    expect(page.locator("body")).not_to_contain_text("Application error")
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")

"""UI smoke tests for auth flow and main pages with running local services."""

from __future__ import annotations

from functools import lru_cache
import os
import uuid

import pytest
from playwright.sync_api import Page, expect

from api.auth import create_access_token, create_user, get_user_by_username


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
    page.locator('button[type="submit"]').click()
    page.wait_for_function(
        "() => !!(sessionStorage.getItem('token') || localStorage.getItem('token'))",
        timeout=15000,
    )
    page.wait_for_function("() => window.location.pathname === '/'", timeout=30000)


@lru_cache(maxsize=8)
def _fetch_session(username: str, password: str) -> tuple[str, str, str]:
    user = get_user_by_username(username)
    if not user:
        create_user(
            username=username,
            password=password,
            role="admin" if username == ADMIN_USERNAME else "viewer",
        )
        user = get_user_by_username(username)

    role = getattr(user, "role", None) or ("admin" if username == ADMIN_USERNAME else "viewer")
    token = create_access_token({"sub": username, "role": role})
    return token, username, role


def _seed_auth_session(page: Page, username: str, password: str) -> None:
    token, resolved_username, resolved_role = _fetch_session(username, password)
    page.goto(f"{BASE_URL}/login")
    page.evaluate(
        """([nextToken, nextUsername, nextRole]) => {
            sessionStorage.setItem("token", nextToken);
            localStorage.removeItem("token");
            localStorage.setItem("user", nextUsername);
            localStorage.setItem("userRole", nextRole || "viewer");
        }""",
        [token, resolved_username, resolved_role],
    )


def test_register_then_login_new_user(page: Page) -> None:
    username = f"ui_{uuid.uuid4().hex[:8]}"
    password = "StrongPass123!"

    page.goto(f"{BASE_URL}/register")
    page.wait_for_load_state("domcontentloaded")
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#confirmPassword").fill(password)
    page.locator('button[type="submit"]').click()
    page.wait_for_function("() => window.location.pathname === '/login'", timeout=15000)

    _login(page, username, password)


def test_admin_login_and_settings_health(page: Page) -> None:
    _login(page, ADMIN_USERNAME, ADMIN_PASSWORD)

    page.goto(f"{BASE_URL}/settings")
    page.wait_for_load_state("domcontentloaded")

    expect(page.locator("body")).to_contain_text("系统设置")
    expect(page.locator("body")).to_contain_text("初始化向导")
    expect(page.locator("body")).to_contain_text("数据源优先级")
    expect(page.locator("body")).to_contain_text("备份管理")
    expect(page.locator("body")).not_to_contain_text("离线")


@pytest.mark.parametrize(
    "route,expected_text",
    [
        ("/", "今日状态"),
        ("/daily-workbench", "日常决策工作台"),
        ("/market", "技术与风险分析"),
        ("/trading", "模拟交易工作台"),
        ("/backtest", "回测中心"),
        ("/portfolio", "个人资产"),
        ("/strategies", "量化策略工作台"),
    ],
)
def test_main_pages_render_without_fatal_error(page: Page, route: str, expected_text: str) -> None:
    _seed_auth_session(page, ADMIN_USERNAME, ADMIN_PASSWORD)

    page.goto(f"{BASE_URL}{route}")
    page.wait_for_load_state("domcontentloaded")

    expect(page.locator("body")).to_contain_text(expected_text)
    expect(page.locator("body")).not_to_contain_text("Application error")
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")

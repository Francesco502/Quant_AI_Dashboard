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


def test_dashboard_loads(page: Page) -> None:
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")
    expect(page).to_have_url(f"{BASE_URL}/")


def test_trading_page_loads(page: Page) -> None:
    page.goto(f"{BASE_URL}/trading")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading", name="Trading Center")).to_be_visible()

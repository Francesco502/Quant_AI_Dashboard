"""Release-check script contracts for v3.0.0."""

from __future__ import annotations

from pathlib import Path

import scripts.release_check as release_check


class _FakeChromium:
    def __init__(self, executable_path: str) -> None:
        self.executable_path = executable_path


class _FakePlaywright:
    def __init__(self, executable_path: str) -> None:
        self.chromium = _FakeChromium(executable_path)

    def __enter__(self) -> "_FakePlaywright":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_default_frontend_url_uses_localhost_to_match_next_dev_origin(monkeypatch):
    monkeypatch.delenv("FRONTEND_URL", raising=False)

    env = release_check._build_env()

    assert release_check.DEFAULT_FRONTEND_URL == "http://localhost:8686"
    assert env["FRONTEND_URL"] == "http://localhost:8686"


def test_release_check_requires_llm_ready_by_default(monkeypatch):
    monkeypatch.delenv("EXPECT_LLM_READY", raising=False)

    env = release_check._build_env()

    assert env["EXPECT_LLM_READY"] == "1"


def test_playwright_preflight_reports_missing_chromium(monkeypatch, tmp_path):
    missing = tmp_path / "missing-chromium"
    monkeypatch.setattr(
        release_check,
        "sync_playwright",
        lambda: _FakePlaywright(str(missing)),
    )

    failures = release_check._playwright_preflight()

    assert any("playwright install chromium" in item for item in failures)


def test_playwright_preflight_accepts_existing_chromium(monkeypatch, tmp_path):
    existing = tmp_path / "chromium"
    existing.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        release_check,
        "sync_playwright",
        lambda: _FakePlaywright(str(existing)),
    )

    assert release_check._playwright_preflight() == []

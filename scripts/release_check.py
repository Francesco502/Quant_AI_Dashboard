#!/usr/bin/env python
"""Run the release-oriented external E2E suite with explicit opt-in flags."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional release-check dependency
    sync_playwright = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REPORT_PATH = ROOT / "output" / "reports" / "release_check_report.txt"
DEFAULT_API_URL = "http://127.0.0.1:8685/api"
DEFAULT_FRONTEND_URL = "http://localhost:8686"
TEST_FILES = [
    "tests/e2e/test_release_validation.py",
    "tests/e2e/test_ui.py",
    "tests/e2e/test_ui_auth_and_pages.py",
]


def _build_env() -> dict[str, str]:
    env = os.environ.copy()

    api_url = env.get("API_URL", DEFAULT_API_URL)
    frontend_url = env.get("FRONTEND_URL", DEFAULT_FRONTEND_URL)
    generated_user = False
    admin_username = env.get("TEST_ADMIN_USERNAME", "").strip()
    admin_password = env.get("TEST_ADMIN_PASSWORD", "").strip()
    if not admin_username or not admin_password:
        generated_user = True
        admin_username = f"release_e2e_{uuid.uuid4().hex[:8]}"
        admin_password = f"ReleaseValidation-{uuid.uuid4().hex[:12]}!"

    env["RUN_EXTERNAL_E2E"] = "1"
    env["API_URL"] = api_url
    env["FRONTEND_URL"] = frontend_url
    env.setdefault("EXPECT_LLM_READY", "1")
    env.setdefault("TEST_ADMIN_USERNAME", admin_username)
    env.setdefault("TEST_ADMIN_PASSWORD", admin_password)
    if generated_user:
        env["RELEASE_CHECK_GENERATED_USER"] = "1"

    if not env.get("TEST_LOGIN_USERNAME") and env.get("TEST_ADMIN_USERNAME"):
        env["TEST_LOGIN_USERNAME"] = env["TEST_ADMIN_USERNAME"]
    if not env.get("TEST_LOGIN_PASSWORD") and env.get("TEST_ADMIN_PASSWORD"):
        env["TEST_LOGIN_PASSWORD"] = env["TEST_ADMIN_PASSWORD"]

    hosts = {
        urlparse(api_url).hostname or "",
        urlparse(frontend_url).hostname or "",
    }
    if hosts.issubset({"127.0.0.1", "localhost"}):
        existing_no_proxy = [item.strip() for item in env.get("NO_PROXY", "").split(",") if item.strip()]
        for host in ("127.0.0.1", "localhost"):
            if host not in existing_no_proxy:
                existing_no_proxy.append(host)
        env["NO_PROXY"] = ",".join(existing_no_proxy)
        env["no_proxy"] = env["NO_PROXY"]
        for proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            env.pop(proxy_key, None)

    return env


def _ensure_generated_test_user(env: dict[str, str]) -> None:
    if env.get("RELEASE_CHECK_GENERATED_USER") != "1":
        return
    try:
        from api.auth import create_user, get_user_by_username

        username = env["TEST_ADMIN_USERNAME"]
        password = env["TEST_ADMIN_PASSWORD"]
        if not get_user_by_username(username):
            create_user(username=username, password=password, role="admin")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to create generated release-check user: {exc}") from exc


def _playwright_preflight() -> list[str]:
    if sync_playwright is None:
        return ["Playwright is not installed; run: python -m pip install playwright && playwright install chromium"]

    try:
        with sync_playwright() as playwright:
            executable_path = Path(playwright.chromium.executable_path)
            if not executable_path.exists():
                return [
                    "Playwright Chromium executable is missing; run: playwright install chromium "
                    "or pin Playwright to the browser revision used by CI."
                ]
    except Exception as exc:  # noqa: BLE001
        return [f"Playwright preflight failed: {exc}; run: playwright install chromium"]
    return []


def _build_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "pytest",
        *TEST_FILES,
        "-q",
        "-m",
        "e2e_external",
        "--timeout=60",
        "-o",
        "addopts=--strict-markers --tb=short --disable-warnings",
    ]


def _preflight(api_url: str, frontend_url: str) -> list[str]:
    failures: list[str] = []
    targets = [
        ("backend", f"{api_url}/health"),
        ("frontend", f"{frontend_url}/login"),
    ]

    for label, url in targets:
        try:
            with urlopen(url, timeout=10) as response:
                status = getattr(response, "status", 200)
                if status >= 400:
                    failures.append(f"{label} check failed: {url} returned HTTP {status}")
        except URLError as exc:
            failures.append(f"{label} check failed: {url} is not reachable ({exc.reason})")
        except Exception as exc:  # pragma: no cover - defensive
            failures.append(f"{label} check failed: {url} raised {exc}")

    return failures


def _write_report(command: list[str], result: subprocess.CompletedProcess[str], api_url: str, frontend_url: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "Release external E2E report",
        "=" * 60,
        f"cwd: {ROOT}",
        f"api_url: {api_url}",
        f"frontend_url: {frontend_url}",
        f"command: {' '.join(command)}",
        f"exit_code: {result.returncode}",
        "",
        "stdout:",
        result.stdout.rstrip(),
        "",
        "stderr:",
        result.stderr.rstrip(),
        "",
        "ready: yes" if result.returncode == 0 else "ready: no",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _safe_print(text: str, *, stderr: bool = False) -> None:
    stream = sys.stderr if stderr else sys.stdout
    payload = text.encode(stream.encoding or "utf-8", errors="replace")
    stream.buffer.write(payload)
    stream.flush()


def main() -> int:
    env = _build_env()
    command = _build_command()
    api_url = env["API_URL"]
    frontend_url = env["FRONTEND_URL"]

    print("Running release validation against external services...")
    print(f"API_URL={api_url}")
    print(f"FRONTEND_URL={frontend_url}")
    print(f"Report -> {REPORT_PATH}")

    try:
        _ensure_generated_test_user(env)
    except Exception as exc:  # noqa: BLE001
        result = subprocess.CompletedProcess(command, 1, "", str(exc))
        _write_report(command, result, api_url, frontend_url)
        _safe_print(str(exc) + "\n", stderr=True)
        return 1

    preflight_failures = _preflight(api_url, frontend_url)
    preflight_failures.extend(_playwright_preflight())
    if preflight_failures:
        stderr = "Preflight failed before pytest execution.\n" + "\n".join(preflight_failures)
        result = subprocess.CompletedProcess(command, 1, "", stderr)
        _write_report(command, result, api_url, frontend_url)
        _safe_print(stderr + "\n", stderr=True)
        print(f"Saved report to {REPORT_PATH}")
        return 1

    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    _write_report(command, result, api_url, frontend_url)
    if result.stdout:
        _safe_print(result.stdout)
    if result.stderr:
        _safe_print(result.stderr, stderr=True)
    print(f"\nSaved report to {REPORT_PATH}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

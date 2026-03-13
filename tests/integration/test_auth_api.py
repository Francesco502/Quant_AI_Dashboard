"""Integration tests for auth middleware and RBAC endpoints."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from api.auth import (
    authenticate_user,
    bootstrap_admin_from_env,
    create_access_token,
    create_user,
    get_user_by_username,
)
from api.main import app


pytestmark = pytest.mark.integration


def _bearer_headers(username: str, role: str) -> dict[str, str]:
    token = create_access_token({"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_cors_preflight_not_blocked_by_auth() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/trading/accounts",
            headers={
                "Origin": "http://localhost:8686",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code in {200, 204}
    assert response.status_code != 401


def test_unauthorized_cors_response_keeps_origin_header() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/stz/asset-pool",
            headers={"Origin": "http://127.0.0.1:8686"},
        )

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8686"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_auth_me_for_regular_user_returns_permission_list() -> None:
    username = f"itest_{uuid.uuid4().hex[:8]}"
    assert create_user(username=username, password="password123", role="viewer")

    with TestClient(app) as client:
        response = client.get("/api/auth/me", headers=_bearer_headers(username, "viewer"))

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == username
    assert body["role"] == "viewer"
    assert isinstance(body["permissions"], list)
    assert "view_data" in body["permissions"]


def test_auth_permissions_for_admin_not_downgraded_to_viewer() -> None:
    if not get_user_by_username("admin"):
        assert create_user(username="admin", password="admin123", role="admin")

    with TestClient(app) as client:
        response = client.get("/api/auth/permissions", headers=_bearer_headers("admin", "admin"))

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    assert "manage_user" in body["permissions"]


def test_bootstrap_admin_requires_explicit_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    username = f"bootstrap_noenv_{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("APP_ADMIN_USERNAME", username)
    monkeypatch.delenv("APP_LOGIN_PASSWORD", raising=False)
    monkeypatch.delenv("APP_LOGIN_PASSWORD_HASH", raising=False)

    assert bootstrap_admin_from_env() is False
    assert get_user_by_username(username) is None


def test_bootstrap_admin_creates_configured_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    username = f"bootstrap_{uuid.uuid4().hex[:8]}"
    password = "ReleaseReady123!"
    monkeypatch.setenv("APP_ADMIN_USERNAME", username)
    monkeypatch.setenv("APP_LOGIN_PASSWORD", password)
    monkeypatch.delenv("APP_LOGIN_PASSWORD_HASH", raising=False)

    assert bootstrap_admin_from_env() is True

    user = get_user_by_username(username)
    assert user is not None
    assert user.role == "admin"
    assert authenticate_user(username, password) is not None

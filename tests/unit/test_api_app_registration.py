from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import AuthenticationMiddleware
from api.middleware import PerformanceMiddleware, RateLimitMiddleware
from api.router_registry import register_api_routes
from api.routers import monitoring


def _route_paths(app: FastAPI) -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_optimized_app_uses_shared_security_middlewares():
    from api.main_optimized import app

    middleware_classes = {entry.cls for entry in app.user_middleware}

    assert AuthenticationMiddleware in middleware_classes
    assert RateLimitMiddleware in middleware_classes
    assert PerformanceMiddleware in middleware_classes


def test_legacy_accounts_routes_are_not_registered_by_default():
    app = FastAPI()

    register_api_routes(app)

    assert "/api/accounts/paper" not in _route_paths(app)
    assert "/api/legacy/accounts/paper" not in _route_paths(app)


def test_legacy_accounts_routes_are_isolated_when_enabled():
    app = FastAPI()

    register_api_routes(app, include_legacy_accounts=True)

    paths = _route_paths(app)
    assert "/api/accounts/paper" not in paths
    assert "/api/legacy/accounts/paper" in paths


def test_monitoring_restart_requires_auth_without_global_middleware():
    app = FastAPI()
    app.include_router(monitoring.router, prefix="/api")

    response = TestClient(app).post("/api/monitoring/restart")

    assert response.status_code in {401, 403}

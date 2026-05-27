"""Tests for API audit middleware attribution and sanitization."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.audit_log import APIAuditMiddleware


@pytest.mark.asyncio
async def test_api_audit_middleware_logs_user_after_auth_state_is_set(monkeypatch):
    recorded = {}

    class FakeAuditLogger:
        def log_api_access(self, **kwargs):
            recorded.update(kwargs)

    monkeypatch.setattr("core.audit_log.get_audit_logger", lambda: FakeAuditLogger())

    async def inner_app(scope, receive, send):
        scope.setdefault("state", {})["current_user"] = SimpleNamespace(username="alice")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = APIAuditMiddleware(inner_app)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/protected",
        "query_string": b"",
        "headers": [
            (b"host", b"testserver"),
            (b"authorization", b"Bearer secret-token"),
            (b"cookie", b"session=secret"),
        ],
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "server": ("testserver", 80),
        "state": {},
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        return None

    await middleware(scope, receive, send)

    assert recorded["user"] == "alice"
    assert "authorization" not in recorded["details"]["headers"]
    assert "cookie" not in recorded["details"]["headers"]

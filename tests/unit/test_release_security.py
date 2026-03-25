"""Release security guardrail tests."""

from api.auth import DEFAULT_SECRET_KEY, get_auth_security_issues
from api.main import get_security_readiness_issues


def test_default_secret_key_is_flagged():
    issues = get_auth_security_issues(secret_key=DEFAULT_SECRET_KEY)

    assert any("SECRET_KEY" in issue for issue in issues)


def test_release_security_requires_explicit_cors(monkeypatch):
    monkeypatch.setattr("api.main.validate_auth_security", lambda strict=False: [])
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("API_EXPECT_SAME_ORIGIN", raising=False)

    issues = get_security_readiness_issues(cors_origins=[])

    assert any("CORS_ORIGINS" in issue for issue in issues)


def test_release_security_accepts_same_origin_deployments(monkeypatch):
    monkeypatch.setattr("api.main.validate_auth_security", lambda strict=False: [])
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("API_EXPECT_SAME_ORIGIN", "true")

    issues = get_security_readiness_issues(cors_origins=[])

    assert issues == []

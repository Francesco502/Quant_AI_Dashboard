"""Release hardening tests for LLM client defaults."""

from __future__ import annotations

from core import llm_client


def test_build_config_without_api_key_falls_back_to_dummy(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("DASHSCOPE_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("DASHSCOPE_MODEL", raising=False)

    config = llm_client._build_config_from_env()

    assert config.provider == "dummy"
    assert config.api_key == ""


def test_build_config_uses_configured_openai_compatible_key(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "custom-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")

    config = llm_client._build_config_from_env()

    assert config.provider == "openai_compat"
    assert config.api_key == "test-key"
    assert config.model == "custom-model"
    assert config.base_url == "https://example.com/v1"

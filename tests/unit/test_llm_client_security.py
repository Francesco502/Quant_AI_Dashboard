"""Release hardening tests for LLM client defaults."""

from __future__ import annotations

import pytest

from core import llm_client


def test_build_config_without_api_key_returns_unconfigured_dummy_config(monkeypatch) -> None:
    llm_client.reset_client_cache()
    try:
        for key in [
            "LLM_PROVIDER",
            "OPENAI_API_KEY",
            "DASHSCOPE_API_KEY",
            "OPENAI_BASE_URL",
            "DASHSCOPE_BASE_URL",
            "OPENAI_MODEL",
            "DASHSCOPE_MODEL",
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_MODEL",
            "OPENROUTER_API_KEY",
            "OPENROUTER_MODEL",
            "OLLAMA_BASE_URL",
            "OLLAMA_MODEL",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = llm_client._build_config_from_env()

        assert config.provider == "dummy"
        assert config.api_key == ""
    finally:
        llm_client.reset_client_cache()


def test_build_config_uses_configured_openai_compatible_key(monkeypatch) -> None:
    llm_client.reset_client_cache()
    try:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_MODEL", "custom-model")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")

        config = llm_client._build_config_from_env()

        assert config.provider == "openai_compat"
        assert config.api_key == "test-key"
        assert config.model == "custom-model"
        assert config.base_url == "https://example.com/v1"
    finally:
        llm_client.reset_client_cache()


def test_status_reports_unavailable_provider_initialization(monkeypatch) -> None:
    llm_client.reset_client_cache()
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fail_init(config):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr(llm_client, "OpenAICompatibleClient", fail_init)

    try:
        status = llm_client.get_status()

        assert status["configured"] is True
        assert status["available"] is False
        assert "boom" in status["error"]
    finally:
        llm_client.reset_client_cache()


def test_build_request_config_uses_dashscope_key_for_openai_override(monkeypatch) -> None:
    llm_client.reset_client_cache()
    try:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

        config = llm_client.build_request_config(
            provider="openai_compat",
            base_url="https://coding.dashscope.aliyuncs.com/v1",
            model="qwen3.5-plus",
        )

        assert config is not None
        assert config.provider == "openai_compat"
        assert config.api_key == "dashscope-key"
        assert config.base_url == "https://coding.dashscope.aliyuncs.com/v1"
    finally:
        llm_client.reset_client_cache()


def test_build_request_config_marks_anthropic_without_key_as_unconfigured(monkeypatch) -> None:
    llm_client.reset_client_cache()
    try:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        config = llm_client.build_request_config(
            provider="anthropic",
            base_url="https://api.anthropic.com",
            model="claude-test",
        )
        status = llm_client.get_status(config)

        assert config is not None
        assert status["provider"] == "anthropic"
        assert status["configured"] is False
        assert status["available"] is False
    finally:
        llm_client.reset_client_cache()


def test_explicit_provider_does_not_silently_fall_back_to_other_keys(monkeypatch) -> None:
    llm_client.reset_client_cache()
    try:
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

        config = llm_client._build_config_from_env()
        status = llm_client.get_status()

        assert config.provider == "gemini"
        assert config.api_key == ""
        assert status["configured"] is False
        assert status["selection_mode"] == "explicit"
    finally:
        llm_client.reset_client_cache()


def test_explicit_openai_provider_uses_dashscope_key_and_reports_explicit_mode(monkeypatch) -> None:
    llm_client.reset_client_cache()
    try:
        monkeypatch.setenv("LLM_PROVIDER", "openai_compat")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://coding.dashscope.aliyuncs.com/v1")
        monkeypatch.setenv("OPENAI_MODEL", "qwen3.5-plus")

        config = llm_client._build_config_from_env()
        status = llm_client.get_status()

        assert config.provider == "openai_compat"
        assert config.api_key == "dashscope-key"
        assert config.base_url == "https://coding.dashscope.aliyuncs.com/v1"
        assert status["selection_mode"] == "explicit"
    finally:
        llm_client.reset_client_cache()


def test_dummy_client_raises_instead_of_returning_placeholder() -> None:
    with pytest.raises(RuntimeError, match="not configured or unavailable"):
        llm_client.DummyLLMClient().chat_completion([{"role": "user", "content": "ping"}])


def test_get_client_raises_when_provider_initialization_fails(monkeypatch) -> None:
    llm_client.reset_client_cache()
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fail_init(config):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr(llm_client, "OpenAICompatibleClient", fail_init)

    try:
        with pytest.raises(RuntimeError, match="boom"):
            llm_client.get_client()
    finally:
        llm_client.reset_client_cache()

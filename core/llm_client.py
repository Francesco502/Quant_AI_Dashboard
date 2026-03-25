"""Unified LLM client adapter."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

Message = Dict[str, str]

DEFAULT_OPENAI_COMPAT_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
DEFAULT_OPENAI_MODEL = "doubao-seed-1-6-thinking"
DEFAULT_OPENAI_API_KEY = ""
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"
DEFAULT_GEMINI_MODEL = "gemini-1.5-pro"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-3.5-turbo"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama2"

OPENAI_PROVIDER_ALIASES = {
    "openai",
    "openai_compat",
    "openai-compatible",
    "openai_compatible",
    "dashscope",
    "aliyun",
    "volcengine",
    "ark",
}
ANTHROPIC_PROVIDER_ALIASES = {
    "anthropic",
    "anthropic_compat",
    "anthropic-compatible",
    "anthropic_compatible",
    "claude",
}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: Optional[str] = None


class BaseLLMClient:
    def chat_completion(self, messages: List[Message], *, model: Optional[str] = None) -> str:
        raise NotImplementedError


class OpenAICompatibleClient(BaseLLMClient):
    def __init__(self, config: LLMConfig) -> None:
        try:
            from openai import OpenAI  # type: ignore[import]
        except Exception as exc:  # noqa: BLE001
            raise ImportError("openai package is required for OpenAI-compatible providers") from exc

        kwargs = {"api_key": config.api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = OpenAI(**kwargs)
        self._model = config.model

    def chat_completion(self, messages: List[Message], *, model: Optional[str] = None) -> str:
        response = self._client.chat.completions.create(
            model=model or self._model,
            messages=messages,
        )
        content = response.choices[0].message.content or ""
        if isinstance(content, list):
            content = "".join(str(part) for part in content)
        return str(content)


class GeminiClient(BaseLLMClient):
    def __init__(self, config: LLMConfig) -> None:
        try:
            import google.generativeai as genai  # type: ignore[import]
        except Exception as exc:  # noqa: BLE001
            raise ImportError("google-generativeai package is required for Gemini") from exc

        genai.configure(api_key=config.api_key)
        self._genai = genai
        self._model_name = config.model
        self._model = genai.GenerativeModel(config.model)

    def chat_completion(self, messages: List[Message], *, model: Optional[str] = None) -> str:
        use_model = model or self._model_name
        if use_model != self._model_name:
            self._model_name = use_model
            self._model = self._genai.GenerativeModel(use_model)

        text_parts: List[str] = []
        for msg in messages:
            role = (msg.get("role") or "").strip().lower()
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                text_parts.append(f"[System]\n{content}")
            else:
                text_parts.append(content)

        prompt = "\n\n".join(text_parts) if text_parts else ""
        if not prompt:
            return "{}"
        result = self._model.generate_content(prompt)
        return (result.text or "{}").strip()


class AnthropicClient(BaseLLMClient):
    def __init__(self, config: LLMConfig) -> None:
        try:
            import anthropic
        except Exception as exc:  # noqa: BLE001
            raise ImportError("anthropic package is required for Claude") from exc

        kwargs = {"api_key": config.api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = anthropic.Anthropic(**kwargs)
        self._model = config.model

    def chat_completion(self, messages: List[Message], *, model: Optional[str] = None) -> str:
        system = ""
        prompt_chunks: List[str] = []
        for msg in messages:
            role = (msg.get("role") or "").strip().lower()
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                system = content
            elif role == "assistant":
                prompt_chunks.append(f"[Assistant]\n{content}")
            else:
                prompt_chunks.append(content)

        if not prompt_chunks:
            return "{}"

        response = self._client.messages.create(
            model=model or self._model,
            max_tokens=4096,
            system=system or None,
            messages=[{"role": "user", "content": "\n\n".join(prompt_chunks)}],
        )
        if response.content and len(response.content) > 0:
            return response.content[0].text
        return "{}"


class DummyLLMClient(BaseLLMClient):
    def chat_completion(self, messages: List[Message], *, model: Optional[str] = None) -> str:
        del messages, model
        raise RuntimeError(
            "LLM provider is not configured or unavailable. "
            "Configure a real provider before requesting analysis."
        )


_global_client: Optional[BaseLLMClient] = None
_global_client_config: Optional[LLMConfig] = None
_client_init_error: Optional[str] = None


def _normalize_provider(provider: Optional[str]) -> str:
    raw = (provider or "").strip().lower()
    if raw in OPENAI_PROVIDER_ALIASES:
        return "openai_compat"
    if raw in ANTHROPIC_PROVIDER_ALIASES:
        return "anthropic"
    return raw


def _normalize_base_url(base_url: Optional[str]) -> Optional[str]:
    raw = (base_url or "").strip()
    return raw.rstrip("/") if raw else None


def _base_url_hostname(base_url: Optional[str]) -> str:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return ""
    return (urlparse(normalized).hostname or "").strip().lower()


def _config_is_configured(config: LLMConfig) -> bool:
    return config.provider != "dummy" and bool((config.api_key or "").strip())


def _resolve_openai_compat_api_key(base_url: Optional[str]) -> str:
    hostname = _base_url_hostname(base_url)
    preferred_keys: List[str]

    if "dashscope.aliyuncs.com" in hostname:
        preferred_keys = [
            "DASHSCOPE_API_KEY",
            "CODING_PLAN_API_KEY",
            "OPENAI_API_KEY",
        ]
    elif "volces.com" in hostname or "ark.cn-beijing.volces.com" in hostname:
        preferred_keys = [
            "ARK_API_KEY",
            "VOLCENGINE_API_KEY",
            "VOLCENGINE_ARK_API_KEY",
            "OPENAI_API_KEY",
        ]
    else:
        preferred_keys = [
            "OPENAI_API_KEY",
            "DASHSCOPE_API_KEY",
            "ARK_API_KEY",
            "VOLCENGINE_API_KEY",
            "VOLCENGINE_ARK_API_KEY",
            "CODING_PLAN_API_KEY",
        ]

    for key in preferred_keys:
        value = (os.getenv(key) or "").strip()
        if value:
            return value

    return ""


def _resolve_anthropic_api_key() -> str:
    for key in ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"]:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def _build_gemini_config(api_key: Optional[str] = None) -> LLMConfig:
    return LLMConfig(
        provider="gemini",
        model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        api_key=(api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")).strip(),
    )


def _build_anthropic_config(api_key: Optional[str] = None) -> LLMConfig:
    base_url = os.getenv("ANTHROPIC_BASE_URL") or os.getenv("CLAUDE_BASE_URL")
    return LLMConfig(
        provider="anthropic",
        model=os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        api_key=(api_key if api_key is not None else _resolve_anthropic_api_key()).strip(),
        base_url=_normalize_base_url(base_url),
    )


def _build_openrouter_config(api_key: Optional[str] = None) -> LLMConfig:
    return LLMConfig(
        provider="openrouter",
        model=os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        api_key=(api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY", "")).strip(),
        base_url="https://openrouter.ai/api/v1",
    )


def _build_ollama_config() -> LLMConfig:
    base = (os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return LLMConfig(
        provider="ollama",
        model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        api_key="ollama" if (os.getenv("OLLAMA_BASE_URL") or "").strip() else "",
        base_url=base,
    )


def _build_openai_compat_config(api_key: str) -> LLMConfig:
    base_url = (
        os.getenv("OPENAI_BASE_URL")
        or os.getenv("DASHSCOPE_BASE_URL")
        or os.getenv("ARK_BASE_URL")
        or os.getenv("VOLCENGINE_BASE_URL")
    )
    if not base_url and (
        os.getenv("ARK_API_KEY")
        or os.getenv("VOLCENGINE_API_KEY")
        or os.getenv("VOLCENGINE_ARK_API_KEY")
    ):
        base_url = "https://ark.cn-beijing.volces.com/api/coding/v3"
    if not base_url:
        base_url = DEFAULT_OPENAI_COMPAT_BASE_URL

    model = (
        os.getenv("OPENAI_MODEL")
        or os.getenv("DASHSCOPE_MODEL")
        or os.getenv("ARK_MODEL")
        or os.getenv("VOLCENGINE_MODEL")
        or DEFAULT_OPENAI_MODEL
    )
    return LLMConfig(provider="openai_compat", model=model, api_key=api_key, base_url=base_url)


def _build_explicit_provider_config(provider: str) -> LLMConfig:
    normalized_provider = _normalize_provider(provider)

    if normalized_provider == "openai_compat":
        base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("DASHSCOPE_BASE_URL")
            or os.getenv("ARK_BASE_URL")
            or os.getenv("VOLCENGINE_BASE_URL")
            or DEFAULT_OPENAI_COMPAT_BASE_URL
        )
        return _build_openai_compat_config(_resolve_openai_compat_api_key(base_url))

    if normalized_provider == "gemini":
        return _build_gemini_config()

    if normalized_provider == "anthropic":
        return _build_anthropic_config()

    if normalized_provider == "openrouter":
        return _build_openrouter_config()

    if normalized_provider == "ollama":
        return _build_ollama_config()

    raw_provider = (provider or "").strip().lower() or "unknown"
    return LLMConfig(provider=raw_provider, model="", api_key="", base_url=None)


def get_selection_mode() -> str:
    return "explicit" if (os.getenv("LLM_PROVIDER") or "").strip() else "auto"


def _build_config_from_env() -> LLMConfig:
    """Build config from environment.

    Default: OpenAI-compatible Volcengine Ark (doubao-seed-1-6-thinking).
    Override provider with LLM_PROVIDER when needed.
    """
    explicit = (os.getenv("LLM_PROVIDER") or "").strip()
    if explicit:
        return _build_explicit_provider_config(explicit)

    api_key = _resolve_openai_compat_api_key(
        os.getenv("OPENAI_BASE_URL")
        or os.getenv("DASHSCOPE_BASE_URL")
        or os.getenv("ARK_BASE_URL")
        or os.getenv("VOLCENGINE_BASE_URL")
        or DEFAULT_OPENAI_COMPAT_BASE_URL
    )
    if api_key:
        return _build_openai_compat_config(api_key)

    if (os.getenv("GEMINI_API_KEY") or "").strip():
        return _build_gemini_config()

    if _resolve_anthropic_api_key():
        return _build_anthropic_config()

    if (os.getenv("OPENROUTER_API_KEY") or "").strip():
        return _build_openrouter_config()

    if (os.getenv("OLLAMA_BASE_URL") or "").strip():
        return _build_ollama_config()

    return LLMConfig(provider="dummy", model="dummy", api_key="", base_url=None)


def build_request_config(
    *,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[LLMConfig]:
    """Build a transient runtime config for per-request UI overrides."""
    normalized_provider = _normalize_provider(provider)
    normalized_base_url = _normalize_base_url(base_url)
    normalized_model = (model or "").strip()

    if not any([normalized_provider, normalized_base_url, normalized_model]):
        return None

    current = _build_config_from_env()
    hostname = _base_url_hostname(normalized_base_url)

    if not normalized_provider:
        if "anthropic" in hostname:
            normalized_provider = "anthropic"
        elif current.provider == "anthropic" and not normalized_base_url:
            normalized_provider = "anthropic"
        else:
            normalized_provider = "openai_compat"

    if normalized_provider == "anthropic":
        return LLMConfig(
            provider="anthropic",
            model=normalized_model or (current.model if current.provider == "anthropic" else os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)),
            api_key=_resolve_anthropic_api_key(),
            base_url=normalized_base_url or (current.base_url if current.provider == "anthropic" else None),
        )

    default_base_url = normalized_base_url
    if not default_base_url and current.provider in {"openai_compat", "openrouter", "ollama"}:
        default_base_url = current.base_url
    if not default_base_url:
        default_base_url = DEFAULT_OPENAI_COMPAT_BASE_URL

    return LLMConfig(
        provider="openai_compat",
        model=normalized_model or (current.model if current.provider in {"openai_compat", "openrouter", "ollama"} else DEFAULT_OPENAI_MODEL),
        api_key=_resolve_openai_compat_api_key(default_base_url),
        base_url=default_base_url,
    )


def get_config() -> LLMConfig:
    """Return the current LLM configuration resolved from environment variables."""
    return _build_config_from_env()


def is_configured(config_override: Optional[LLMConfig] = None) -> bool:
    """Whether a real LLM provider is configured instead of the dummy fallback."""
    return _config_is_configured(config_override or get_config())


def reset_client_cache() -> None:
    """Reset cached client state so environment changes can be re-evaluated."""
    global _global_client, _global_client_config, _client_init_error
    _global_client = None
    _global_client_config = None
    _client_init_error = None


def _create_client(config: LLMConfig) -> BaseLLMClient:
    if config.provider in {"openai_compat", "openrouter", "ollama"}:
        return OpenAICompatibleClient(config)
    if config.provider == "gemini":
        return GeminiClient(config)
    if config.provider == "anthropic":
        return AnthropicClient(config)
    return DummyLLMClient()


def _build_client_result(config: LLMConfig) -> tuple[BaseLLMClient, Optional[str]]:
    if not _config_is_configured(config):
        return DummyLLMClient(), None
    try:
        return _create_client(config), None
    except Exception as exc:  # noqa: BLE001
        return DummyLLMClient(), str(exc)


def get_client_error(config_override: Optional[LLMConfig] = None) -> Optional[str]:
    """Return client initialization error if a configured provider is unavailable."""
    if config_override is not None:
        if not is_configured(config_override):
            return None
        _client, error = _build_client_result(config_override)
        return error

    if not is_configured():
        return None

    _client, error = _build_client_result(get_config())
    return error


def is_available(config_override: Optional[LLMConfig] = None) -> bool:
    """Whether the configured provider is currently operational."""
    if config_override is not None:
        if not is_configured(config_override):
            return False
        client, error = _build_client_result(config_override)
        return not isinstance(client, DummyLLMClient) and error is None

    if not is_configured():
        return False

    client, error = _build_client_result(get_config())
    if error:
        return False
    return not isinstance(client, DummyLLMClient) and error is None


def get_status(config_override: Optional[LLMConfig] = None) -> Dict[str, Any]:
    """Return resolved provider status for frontend and release checks."""
    config = config_override or get_config()
    status: Dict[str, Any] = {
        "configured": _config_is_configured(config),
        "available": False,
        "provider": config.provider,
        "model": config.model if config.provider != "dummy" else None,
        "selection_mode": "request_override" if config_override is not None else get_selection_mode(),
    }
    if config.base_url:
        status["base_url"] = config.base_url

    if status["configured"]:
        if config_override is None:
            status["available"] = is_available()
            error = get_client_error()
            if error:
                status["error"] = error
        else:
            status["available"] = is_available(config_override)
            error = get_client_error(config_override)
            if error:
                status["error"] = error

    return status


def get_client(config_override: Optional[LLMConfig] = None) -> BaseLLMClient:
    global _global_client, _global_client_config, _client_init_error

    if config_override is not None:
        client, error = _build_client_result(config_override)
        if error:
            raise RuntimeError(f"LLM client initialization failed: {error}")
        return client

    config = _build_config_from_env()

    if _global_client is not None and _global_client_config == config:
        return _global_client

    _global_client = None
    _global_client_config = config
    _client_init_error = None

    _global_client, _client_init_error = _build_client_result(config)
    if _client_init_error:
        raise RuntimeError(f"LLM client initialization failed: {_client_init_error}")

    return _global_client


def chat_completion(
    messages: List[Message],
    *,
    model: Optional[str] = None,
    provider_type: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    request_config = build_request_config(
        provider=provider_type,
        base_url=base_url,
        model=model if provider_type or base_url else None,
    )
    return get_client(request_config).chat_completion(messages, model=model)

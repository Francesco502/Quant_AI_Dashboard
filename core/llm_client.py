"""Unified LLM client adapter."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

Message = Dict[str, str]

DEFAULT_OPENAI_COMPAT_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
DEFAULT_OPENAI_MODEL = "qwen3.5-plus"
DEFAULT_OPENAI_API_KEY = ""


@dataclass
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

        self._client = anthropic.Anthropic(api_key=config.api_key)
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
        return (
            '{"conclusion":"LLM is not configured. Returning placeholder result.",'
            '"action":"HOLD","score":50,'
            '"buy_price":null,"stop_loss":null,"target_price":null,'
            '"checklist":[],"highlights":[],"risks":["LLM not configured"]}'
        )


_global_client: Optional[BaseLLMClient] = None


def _build_config_from_env() -> LLMConfig:
    """Build config from environment.

    Default: OpenAI-compatible DashScope (qwen3.5-plus).
    Override provider with LLM_PROVIDER when needed.
    """
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()

    if explicit == "gemini" and os.getenv("GEMINI_API_KEY"):
        return LLMConfig(
            provider="gemini",
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
            api_key=os.getenv("GEMINI_API_KEY", ""),
        )

    if explicit == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        return LLMConfig(
            provider="anthropic",
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        )

    if explicit == "openrouter" and os.getenv("OPENROUTER_API_KEY"):
        return LLMConfig(
            provider="openrouter",
            model=os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo"),
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            base_url="https://openrouter.ai/api/v1",
        )

    if explicit == "ollama" and os.getenv("OLLAMA_BASE_URL"):
        base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return LLMConfig(
            provider="ollama",
            model=os.getenv("OLLAMA_MODEL", "llama2"),
            api_key="ollama",
            base_url=base,
        )

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or DEFAULT_OPENAI_API_KEY
    if not api_key:
        return LLMConfig(provider="dummy", model="dummy", api_key="", base_url=None)
    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("DASHSCOPE_BASE_URL") or DEFAULT_OPENAI_COMPAT_BASE_URL
    model = os.getenv("OPENAI_MODEL") or os.getenv("DASHSCOPE_MODEL") or DEFAULT_OPENAI_MODEL
    return LLMConfig(provider="openai_compat", model=model, api_key=api_key, base_url=base_url)


def get_client() -> BaseLLMClient:
    global _global_client
    if _global_client is not None:
        return _global_client

    config = _build_config_from_env()
    try:
        if config.provider in {"openai_compat", "openrouter", "ollama"}:
            _global_client = OpenAICompatibleClient(config)
        elif config.provider == "gemini":
            _global_client = GeminiClient(config)
        elif config.provider == "anthropic":
            _global_client = AnthropicClient(config)
        else:
            _global_client = DummyLLMClient()
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM client initialization failed, fallback to dummy: %s", exc)
        _global_client = DummyLLMClient()

    return _global_client


def chat_completion(messages: List[Message], *, model: Optional[str] = None) -> str:
    return get_client().chat_completion(messages, model=model)

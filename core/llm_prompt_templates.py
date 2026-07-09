"""Built-in LLM prompt templates for v3.0.0."""

from __future__ import annotations

import json
from typing import Any

from core.llm_client import Message


V300_SYSTEM_PREAMBLE = (
    "Quant-AI Dashboard v3.0.0 DeepSeek-backed analysis runtime. "
    "Use the provided context only, state data limitations explicitly, "
    "and prefer concise, auditable JSON outputs for product workflows."
)


def build_health_check_messages() -> list[Message]:
    return [
        {
            "role": "system",
            "content": (
                f"{V300_SYSTEM_PREAMBLE}\n"
                "You are checking a DeepSeek/OpenAI-compatible provider connection. "
                "Return valid JSON only."
            ),
        },
        {
            "role": "user",
            "content": 'Reply with JSON: {"status":"ok","runtime":"v3.0.0"}.',
        },
    ]


def build_daily_analysis_system_prefix() -> str:
    return (
        f"{V300_SYSTEM_PREAMBLE}\n"
        "Return valid JSON only. Do not wrap JSON in Markdown code fences."
    )


def build_agent_system_prefix() -> str:
    return (
        f"{V300_SYSTEM_PREAMBLE}\n"
        "DeepSeek-backed analysis runtime: plan tool calls conservatively, "
        "avoid fabricating unavailable market data, and keep final answers actionable."
    )


def compact_context(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

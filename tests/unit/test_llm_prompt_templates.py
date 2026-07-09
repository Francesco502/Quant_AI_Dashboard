"""LLM prompt template contracts for v3.0.0."""

from __future__ import annotations

import asyncio

from api.routers import llm_analysis
from core import llm_prompt_templates
from core.agent import prompts as agent_prompts
from core.agent.tools import BaseTool
from core.daily_analysis import prompts as daily_prompts


def test_health_check_prompt_template_contains_v300_contract():
    messages = llm_prompt_templates.build_health_check_messages()

    assert messages[0]["role"] == "system"
    assert "Quant-AI Dashboard v3.0.0" in messages[0]["content"]
    assert "DeepSeek" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "JSON" in messages[1]["content"]


def test_llm_health_check_uses_builtin_prompt_template(monkeypatch):
    seen: dict[str, object] = {}

    monkeypatch.setattr(llm_analysis, "_ensure_llm_configured", lambda config_override=None: None)
    monkeypatch.setattr(
        llm_analysis.llm_client,
        "get_status",
        lambda config_override=None: {
            "provider": "openai_compat",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
        },
    )

    def fake_chat_completion(messages, **kwargs):
        seen["messages"] = messages
        seen["kwargs"] = kwargs
        return '{"status":"ok"}'

    monkeypatch.setattr(llm_analysis.llm_client, "chat_completion", fake_chat_completion)

    asyncio.run(llm_analysis.llm_health_check())

    assert seen["messages"] == llm_prompt_templates.build_health_check_messages()


def test_daily_analysis_prompt_includes_builtin_v300_template():
    messages = daily_prompts.build_messages({"analysis_brief": {}, "text_context": "ctx"})

    assert "Quant-AI Dashboard v3.0.0" in messages[0]["content"]
    assert "Return valid JSON only" in messages[0]["content"]


def test_agent_system_prompt_includes_builtin_v300_template():
    class FakeTool(BaseTool):
        name = "price"
        description = "price context"

    system_prompt = agent_prompts.build_system_prompt({"price": FakeTool()})

    assert "Quant-AI Dashboard v3.0.0" in system_prompt
    assert "DeepSeek-backed analysis runtime" in system_prompt

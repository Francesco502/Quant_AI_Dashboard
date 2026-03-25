from __future__ import annotations

import pytest

from api.routers import llm_analysis


@pytest.mark.asyncio
async def test_natural_query_falls_back_to_heuristic_ticker_when_llm_parse_is_incomplete(monkeypatch) -> None:
    monkeypatch.setattr(llm_analysis.llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(llm_analysis.llm_client, "chat_completion", lambda messages: '{"intent":"decision"}')
    monkeypatch.setattr(llm_analysis, "_ensure_llm_configured", lambda config_override=None: None)
    monkeypatch.setattr(
        llm_analysis,
        "run_daily_analysis",
        lambda **kwargs: {"results": [{"ticker": kwargs["tickers"][0], "decision": {"action": "观望"}}]},
    )

    response = await llm_analysis.natural_query(llm_analysis.NaturalQueryRequest(query="请分析 159755 最近的趋势和操作建议"))

    assert response["parser"] == "llm"
    assert response["parsed"]["ticker"] == "159755"
    assert response["parsed"]["intent"] == "decision"
    assert response["analysis"]["results"][0]["ticker"] == "159755"

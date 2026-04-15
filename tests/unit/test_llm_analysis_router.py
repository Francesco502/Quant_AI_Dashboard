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


def test_parse_query_heuristically_maps_recent_valuation_question_to_decision():
    parsed = llm_analysis._parse_query_heuristically("请分析 600519 最近估值和资金流，值不值得继续持有？")

    assert parsed["ticker"] == "600519"
    assert parsed["intent"] == "decision"
    assert parsed["days"] == 20


def test_parse_query_heuristically_maps_quarter_language_to_60_days():
    parsed = llm_analysis._parse_query_heuristically("帮我看下 159755 近三个月走势")

    assert parsed["ticker"] == "159755"
    assert parsed["intent"] == "price_trend"
    assert parsed["days"] == 60

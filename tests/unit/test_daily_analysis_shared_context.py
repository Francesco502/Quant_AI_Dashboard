import pandas as pd

from core.daily_analysis import builder, run_daily_analysis


def _sample_price_df() -> pd.DataFrame:
    dates = pd.date_range(start="2025-01-01", periods=120, freq="D")
    return pd.DataFrame(
        {
            "600519.SH": [100 + i * 0.5 for i in range(len(dates))],
            "600519": [100 + i * 0.5 for i in range(len(dates))],
            "300750": [80 + i * 0.3 for i in range(len(dates))],
            "000001": [10 + i * 0.02 for i in range(len(dates))],
        },
        index=dates,
    )


def test_build_shared_analysis_context_summarizes_market_review_and_scanner(monkeypatch):
    monkeypatch.setattr(
        "core.market_review.daily_review",
        lambda market="cn": {
            "date": "2026-03-27",
            "market": market,
            "indices": [{"name": "上证指数", "value": 3300.0, "pct_change": 0.86}],
            "overview": {
                "up": 3200,
                "down": 1800,
                "limit_up": 82,
                "limit_down": 6,
                "amplitude": 2.31,
                "turn_rate": 1.88,
            },
            "sectors": {
                "gain": [{"name": "机器人", "pct_change": 3.6}],
                "loss": [{"name": "银行", "pct_change": -0.8}],
            },
            "northbound": {"description": "北向资金当日净流入 25.30 亿元"},
        },
    )
    monkeypatch.setattr(
        "core.daily_analysis.builder.tushare_provider.list_active_a_share_tickers",
        lambda limit=None: [
            {"ticker": "600519"},
            {"ticker": "300750"},
            {"ticker": "000001"},
        ],
    )
    monkeypatch.setattr(
        "core.daily_analysis.builder.load_price_data",
        lambda tickers, days: _sample_price_df(),
    )

    class FakeEngine:
        def scan(self, price_df, top_n=20, min_score=60):
            return pd.DataFrame(
                [
                    {"ticker": "600519", "score": 87.5, "action": "买入", "reasons": "趋势强+量价配合"},
                    {"ticker": "300750", "score": 79.2, "action": "观望", "reasons": "强势回调观察"},
                ]
            )

    monkeypatch.setattr("core.scanner.scanner_engine.get_scanner_engine", lambda: FakeEngine())

    context = builder.build_shared_analysis_context(["600519.SH"], market="cn")

    assert context["market_review_summary"]["breadth"]["up"] == 3200
    assert context["market_review_summary"]["leading_sectors"][0]["name"] == "机器人"
    assert context["scanner_summary"]["leaders"][0]["ticker"] == "600519"
    assert context["scanner_summary"]["matches"]["600519.SH"]["rank"] == 1


def test_build_analysis_input_includes_shared_market_and_scanner_sections(monkeypatch):
    monkeypatch.setattr(
        "core.daily_analysis.builder.load_price_data",
        lambda tickers, days: _sample_price_df(),
    )
    monkeypatch.setattr(
        "core.daily_analysis.builder.tushare_provider.get_cn_security_name",
        lambda ticker: "贵州茅台",
    )
    monkeypatch.setattr(
        "core.daily_analysis.builder.tushare_provider.get_tushare_token",
        lambda: "token-123",
    )
    monkeypatch.setattr(
        "core.daily_analysis.builder.tushare_provider.get_cn_market_context",
        lambda: {"calendar": {"is_trading_day": True}, "indices": [], "northbound": {}},
    )
    monkeypatch.setattr(
        "core.daily_analysis.builder.tushare_provider.get_cn_security_profile",
        lambda ticker: {"ticker": ticker, "asset_type": "stock", "industry": "白酒", "valuation": {"trade_date": "20260327"}},
    )
    monkeypatch.setattr(
        "core.daily_analysis.builder.tushare_provider.get_cn_security_moneyflow",
        lambda ticker: {"description": "最新主力资金净流入 4.20 亿元"},
    )

    result = builder.build_analysis_input(
        "600519.SH",
        market="cn",
        shared_context={
            "market_review_summary": {
                "breadth": {"up": 3200, "down": 1800, "advance_decline_ratio": 1.78},
                "leading_sectors": [{"name": "机器人", "pct_change": 3.6}],
                "lagging_sectors": [{"name": "银行", "pct_change": -0.8}],
            },
            "scanner_summary": {
                "sample_size": 180,
                "result_count": 12,
                "leaders": [{"ticker": "600519", "rank": 1, "score": 87.5, "action": "买入"}],
                "matches": {"600519.SH": {"ticker": "600519", "rank": 1, "score": 87.5, "action": "买入", "reasons": "趋势强+量价配合"}},
            },
            "limitations": [],
        },
    )

    assert "市场复盘摘要" in result["text_context"]
    assert "领涨板块" in result["text_context"]
    assert "市场扫描摘要" in result["text_context"]
    assert "当前标的在本轮扫描中入选" in result["text_context"]
    assert result["meta"]["analysis_scope"]["uses_market_review_summary"] is True
    assert result["meta"]["analysis_scope"]["uses_scanner_summary"] is True


def test_run_daily_analysis_attaches_shared_context_to_response_and_builder(monkeypatch):
    shared_context = {
        "market_review_summary": {"breadth": {"up": 10, "down": 5}},
        "scanner_summary": {"leaders": [{"ticker": "600519", "rank": 1, "score": 88.0, "action": "买入"}]},
        "limitations": [],
    }
    seen_shared_contexts = []

    monkeypatch.setattr("core.daily_analysis.builder.build_shared_analysis_context", lambda tickers, market="cn": shared_context)

    def _fake_build_analysis_input(ticker, market="cn", shared_context=None):
        seen_shared_contexts.append(shared_context)
        return {
            "ticker": ticker,
            "name": ticker,
            "market": market,
            "meta": {"last_close": 100.0, "limitations": []},
            "analysis_brief": {},
            "text_context": "ctx",
        }

    monkeypatch.setattr("core.daily_analysis.builder.build_analysis_input", _fake_build_analysis_input)
    monkeypatch.setattr("core.daily_analysis.prompts.build_messages", lambda ctx: [{"role": "user", "content": "hi"}])
    monkeypatch.setattr(
        "core.daily_analysis.llm_client.chat_completion",
        lambda *args, **kwargs: (
            '{"conclusion":"ok","action":"观望","score":50,"checklist":[],"highlights":[],"risks":[],"thesis":[],'
            '"data_scope":"","limitations":[],"valuation_view":"","liquidity_view":""}'
        ),
    )
    monkeypatch.setattr("core.scratchpad.is_scratchpad_enabled", lambda: False)

    result = run_daily_analysis(["600519"], market="cn")

    assert result["shared_context"]["market_review_summary"]["breadth"]["up"] == 10
    assert seen_shared_contexts[0] is shared_context

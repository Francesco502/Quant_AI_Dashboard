import datetime as dt
from types import SimpleNamespace

import pandas as pd

from core.agent.tools import TradingContextTool
from core.daily_analysis.builder import build_analysis_input
from core.data_service import load_price_data, load_price_data_tushare
from core.market_review import _cn_indices, _cn_northbound
from core.trading_calendar import Market, TradingCalendar


def _sample_price_df() -> pd.DataFrame:
    dates = pd.date_range(start="2025-01-01", periods=90, freq="D")
    return pd.DataFrame({"600519.SH": [100 + i for i in range(len(dates))]}, index=dates)


def test_trading_calendar_uses_tushare_for_a_share(monkeypatch):
    calendar = TradingCalendar()
    target_date = dt.date(2026, 10, 2)

    monkeypatch.setattr(
        "core.trading_calendar.tushare_provider.is_a_share_trading_day",
        lambda date=None: True,
    )

    assert calendar.is_trading_day(target_date, Market.A_SHARE) is True


def test_market_review_prefers_tushare_indices(monkeypatch):
    monkeypatch.setattr(
        "core.market_review.tushare_provider.get_cn_index_snapshots",
        lambda: [
            {
                "name": "上证指数",
                "value": 3200.11,
                "pct_change": 1.23,
                "volume": 123456789,
                "amount": 4567.89,
                "amplitude": None,
                "turn_rate": None,
            }
        ],
    )

    indices = _cn_indices()

    assert len(indices) == 1
    assert indices[0].name == "上证指数"
    assert indices[0].amount == 4567.89


def test_market_review_prefers_tushare_northbound(monkeypatch):
    monkeypatch.setattr(
        "core.market_review.tushare_provider.get_cn_northbound_flow",
        lambda: {
            "net_inflow": 32.5,
            "unit": "亿元",
            "description": "北向资金当日净流入 32.50 亿元",
        },
    )

    northbound = _cn_northbound()

    assert northbound["net_inflow"] == 32.5
    assert "北向资金" in northbound["description"]


def test_build_analysis_input_enriches_name_and_market_context(monkeypatch):
    monkeypatch.setattr(
        "core.daily_analysis.builder.load_price_data",
        lambda tickers, days: _sample_price_df(),
    )
    monkeypatch.setattr(
        "core.daily_analysis.builder.tushare_provider.get_cn_security_name",
        lambda ticker: "贵州茅台",
    )
    monkeypatch.setattr(
        "core.daily_analysis.builder.tushare_provider.get_cn_market_context",
        lambda: {
            "calendar": {
                "today": "2026-03-13",
                "is_trading_day": True,
                "next_trading_day": "2026-03-16",
            },
            "indices": [{"name": "上证指数", "pct_change": 0.82, "value": 3200.11}],
            "northbound": {"net_inflow": 12.3, "unit": "亿元", "description": "北向资金净流入 12.3 亿元"},
        },
    )

    result = build_analysis_input("600519.SH", market="cn")

    assert result["name"] == "贵州茅台"
    assert result["meta"]["market_context"]["calendar"]["is_trading_day"] is True
    assert "上证指数" in result["text_context"]
    assert "北向资金" in result["text_context"]


def test_trading_context_tool_returns_structured_context(monkeypatch):
    monkeypatch.setattr(
        "core.agent.tools.tushare_provider.get_cn_security_name",
        lambda ticker: "贵州茅台",
    )
    monkeypatch.setattr(
        "core.agent.tools.tushare_provider.get_cn_market_context",
        lambda: {
            "calendar": {
                "today": "2026-03-13",
                "is_trading_day": True,
                "next_trading_day": "2026-03-16",
            },
            "indices": [{"name": "上证指数", "pct_change": 0.82, "value": 3200.11}],
            "northbound": {"net_inflow": 12.3, "unit": "亿元", "description": "北向资金净流入 12.3 亿元"},
        },
    )

    tool = TradingContextTool()
    result = tool.run(ticker="600519.SH")

    assert result.name == "trading_context"
    assert result.data["ticker"] == "600519.SH"
    assert result.data["name"] == "贵州茅台"
    assert result.data["market_context"]["calendar"]["next_trading_day"] == "2026-03-16"


def test_load_price_data_reads_uppercase_tushare_key(monkeypatch):
    captured = {}

    monkeypatch.setattr("core.data_store.load_local_price_history", lambda ticker: None)
    monkeypatch.setattr(
        "core.data_service.get_api_keys",
        lambda: {"TUSHARE_TOKEN": "token-123"},
    )

    def _fake_remote(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame({"600519.SH": [101.0]}, index=pd.date_range("2025-01-01", periods=1))

    monkeypatch.setattr("core.data_service._load_price_data_remote", _fake_remote)
    monkeypatch.setattr("core.data_store.save_local_price_history", lambda ticker, series: None)

    load_price_data(["600519.SH"], days=1)

    assert captured["tushare_token"] == "token-123"


def test_load_price_data_tushare_supports_digit_only_ticker(monkeypatch):
    class FakePro:
        def __init__(self):
            self.received = []

        def daily(self, ts_code, start_date, end_date):
            self.received.append(ts_code)
            if ts_code == "600519.SH":
                return pd.DataFrame(
                    {
                        "trade_date": ["20250311", "20250312"],
                        "close": [100.0, 101.0],
                    }
                )
            return pd.DataFrame()

        def fund_daily(self, ts_code, start_date, end_date):
            return pd.DataFrame()

    fake_pro = FakePro()
    fake_ts = SimpleNamespace(set_token=lambda token: None, pro_api=lambda: fake_pro)

    monkeypatch.setattr("core.data_service.TUSHARE_AVAILABLE", True)
    monkeypatch.setattr("core.data_service.ts", fake_ts)

    result = load_price_data_tushare(["600519"], days=2, tushare_token="token-123")

    assert "600519" in result.columns
    assert fake_pro.received == ["600519.SH"]

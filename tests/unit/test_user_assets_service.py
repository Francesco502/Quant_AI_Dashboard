from __future__ import annotations

import datetime as dt
import os
import tempfile
from unittest.mock import patch

import pandas as pd
import pytest

from core.database import Database
from core.user_assets import UserAssetService


pytestmark = pytest.mark.unit


@pytest.fixture
def asset_service():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(os.path.join(tmpdir, "user_assets.db"))
        with patch("core.user_assets.get_database", return_value=db):
            service = UserAssetService()
            yield service
            if service.db.conn:
                service.db.conn.close()


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data_akshare")
@patch("core.user_assets.load_price_data")
def test_user_asset_overview_calculates_pnl(mock_load_price, mock_load_price_akshare, _mock_realtime, asset_service):
    dates = pd.to_datetime(["2026-02-17", "2026-03-12", "2026-03-18", "2026-03-19"])
    mock_load_price.return_value = pd.DataFrame({"002611": [2.00, 2.20, 2.50, 2.60]}, index=dates)
    mock_load_price_akshare.return_value = pd.DataFrame({"002611": [2.00, 2.20, 2.50, 2.60]}, index=dates)

    overview = asset_service.upsert_asset(
        1,
        {
            "ticker": "002611",
            "asset_name": "博时黄金ETF联接C",
            "asset_category": "商品/避险",
            "asset_style": "抗通胀",
            "units": 10,
            "avg_cost": 2.50,
        },
    )

    assert overview["summary"]["asset_count"] == 1
    asset = overview["assets"][0]
    assert asset["ticker"] == "002611"
    assert asset["market_value"] == pytest.approx(26.0)
    assert asset["invested_amount"] == pytest.approx(25.0)
    assert asset["total_return"] == pytest.approx(1.0)
    assert asset["current_price"] == pytest.approx(2.60)
    assert asset["day_change"] == pytest.approx(1.0)
    assert asset["day_change_pct"] == pytest.approx(4.0)
    assert asset["week_change"] == pytest.approx(4.0)
    assert asset["week_change_pct"] == pytest.approx(round(((26.0 - 22.0) / 22.0) * 100.0, 4))
    assert asset["month_change"] == pytest.approx(6.0)
    assert asset["month_change_pct"] == pytest.approx(round(((26.0 - 20.0) / 20.0) * 100.0, 4))
    assert mock_load_price.call_args.kwargs["refresh_stale"] is False
    assert asset["asset_type"] == "fund"


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data_akshare")
@patch("core.user_assets.load_price_data")
def test_user_asset_overview_uses_cached_payload_between_reads(
    mock_load_price,
    mock_load_price_akshare,
    _mock_realtime,
    asset_service,
):
    dates = pd.to_datetime(["2026-03-18", "2026-03-19"])
    mock_load_price.return_value = pd.DataFrame({"002611": [2.50, 2.60]}, index=dates)
    mock_load_price_akshare.return_value = pd.DataFrame({"002611": [2.50, 2.60]}, index=dates)

    asset_service.upsert_asset(
        1,
        {
            "ticker": "002611",
            "asset_name": "鍗氭椂榛勯噾ETF鑱旀帴C",
            "units": 10,
            "avg_cost": 2.50,
        },
    )

    overview = asset_service.get_overview(1, sync_dca=False)

    assert overview["assets"][0]["current_price"] == pytest.approx(2.60)
    assert mock_load_price.call_count == 1
    assert mock_load_price_akshare.call_count == 1


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data")
def test_reconcile_due_dca_shifts_to_next_trading_day(mock_load_price, _mock_realtime, asset_service):
    dates = pd.to_datetime(["2026-03-13", "2026-03-16"])
    mock_load_price.return_value = pd.DataFrame({"159755": [1.95, 2.00]}, index=dates)

    asset_service.upsert_asset(
        1,
        {
            "ticker": "159755",
            "asset_name": "泰康港股通中证香港银行投资指数C",
            "units": 0,
            "avg_cost": 0,
            "trade_date": "2026-03-13",
            "dca_rule": {
                "enabled": True,
                "frequency": "weekly",
                "weekday": 5,
                "amount": 100,
                "start_date": "2026-03-14",
                "shift_to_next_trading_day": True,
            },
        },
    )

    result = asset_service.reconcile_due_dca(1, as_of=dt.date(2026, 3, 16))

    assert result["created"] == 1
    txns = asset_service.list_transactions(1, "159755")
    dca_trades = [item for item in txns if item["source"] == "dca"]
    assert len(dca_trades) == 1
    assert dca_trades[0]["trade_date"] == "2026-03-16"

    overview = asset_service.get_overview(1, sync_dca=False)
    asset = overview["assets"][0]
    assert asset["units"] == pytest.approx(50.0)
    assert asset["invested_amount"] == pytest.approx(100.0)


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data")
def test_update_asset_can_rename_ticker(mock_load_price, _mock_realtime, asset_service):
    dates = pd.to_datetime(["2026-03-18", "2026-03-19"])
    mock_load_price.return_value = pd.DataFrame({"159755A": [1.02, 1.05]}, index=dates)

    asset_service.upsert_asset(
        1,
        {
            "ticker": "159755",
            "asset_name": "电池ETF",
            "units": 10,
            "avg_cost": 0.80,
        },
    )

    overview = asset_service.update_asset(
        1,
        "159755",
        {
            "ticker": "159755A",
            "asset_name": "电池ETF增强版",
            "units": 12,
            "avg_cost": 0.82,
        },
    )

    assets = overview["assets"]
    assert len(assets) == 1
    assert assets[0]["ticker"] == "159755A"
    assert assets[0]["asset_name"] == "电池ETF增强版"

    transactions = asset_service.list_transactions(1, "159755A")
    assert len(transactions) == 2
    assert {item["ticker"] for item in transactions} == {"159755A"}


@patch(
    "core.user_assets.load_cn_realtime_quotes_sina",
    return_value={
        "159755": {
            "ticker": "159755",
            "price": 1.082,
            "trade_date": "2026-03-20",
            "trade_time": "15:00:03",
            "timestamp": pd.Timestamp("2026-03-20 15:00:03"),
        }
    },
)
@patch("core.user_assets.load_price_data")
def test_user_asset_overview_prefers_realtime_quote_for_exchange_etf(
    mock_load_price,
    _mock_realtime,
    asset_service,
):
    dates = pd.to_datetime(["2026-03-18", "2026-03-19"])
    mock_load_price.return_value = pd.DataFrame({"159755": [1.0903, 1.0615]}, index=dates)

    overview = asset_service.upsert_asset(
        1,
        {
            "ticker": "159755",
            "asset_name": "电池ETF",
            "asset_type": "fund",
            "units": 100,
            "avg_cost": 0.653,
        },
    )

    asset = overview["assets"][0]
    assert asset["asset_type"] == "etf"
    assert asset["current_price"] == pytest.approx(1.082)
    assert asset["last_price_date"] == "2026-03-20"


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data_akshare")
@patch("core.user_assets.load_price_data")
def test_user_asset_overview_prefers_fund_nav_for_linked_fund(
    mock_load_price,
    mock_load_price_akshare,
    _mock_realtime,
    asset_service,
):
    load_dates = pd.to_datetime(["2026-03-19", "2026-03-20"])
    nav_dates = pd.to_datetime(["2026-03-18", "2026-03-19"])
    mock_load_price.return_value = pd.DataFrame({"160615": [1.3770, 1.3640]}, index=load_dates)
    mock_load_price_akshare.return_value = pd.DataFrame({"160615": [1.3981, 1.3770]}, index=nav_dates)

    overview = asset_service.upsert_asset(
        1,
        {
            "ticker": "160615",
            "asset_name": "鹏华沪深300ETF联接(LOF)A",
            "asset_type": "fund",
            "units": 100,
            "avg_cost": 1.2088,
        },
    )

    asset = overview["assets"][0]
    assert asset["asset_type"] == "fund"
    assert asset["current_price"] == pytest.approx(1.3770)
    assert asset["last_price_date"] == "2026-03-19"


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data_akshare")
@patch("core.user_assets.load_price_data")
def test_otc_fund_dca_pending_confirmation_is_exposed_in_overview(
    mock_load_price,
    mock_load_price_akshare,
    _mock_realtime,
    asset_service,
):
    execution_dates = pd.to_datetime(["2026-03-19", "2026-03-20"])
    mock_load_price.return_value = pd.DataFrame({"002611": [2.00, 2.05]}, index=execution_dates)
    mock_load_price_akshare.return_value = pd.DataFrame({"002611": [2.00]}, index=pd.to_datetime(["2026-03-19"]))

    asset_service.upsert_asset(
        1,
        {
            "ticker": "002611",
            "asset_name": "Fund DCA Test",
            "asset_type": "fund",
            "units": 0,
            "avg_cost": 0,
            "trade_date": "2026-03-18",
            "dca_rule": {
                "enabled": True,
                "frequency": "weekly",
                "weekday": 3,
                "amount": 100,
                "start_date": "2026-03-19",
                "shift_to_next_trading_day": True,
            },
        },
    )

    thursday_result = asset_service.reconcile_due_dca(1, as_of=dt.date(2026, 3, 19))
    assert thursday_result["created"] == 0
    assert [item for item in asset_service.list_transactions(1, "002611") if item["source"] == "dca"] == []

    class ThursdayDate(dt.date):
        @classmethod
        def today(cls) -> "ThursdayDate":
            return cls(2026, 3, 19)

    with patch("core.user_assets.dt.date", ThursdayDate):
        overview = asset_service.get_overview(1, sync_dca=False, force_refresh=True)

    asset = overview["assets"][0]
    assert asset["units"] == pytest.approx(0.0)
    assert asset["invested_amount"] == pytest.approx(0.0)
    assert asset["total_return"] == pytest.approx(0.0)
    assert asset["pending_dca"] == {
        "status": "pending_confirmation",
        "amount": 100.0,
        "execution_date": "2026-03-19",
        "confirmation_date": "2026-03-20",
        "price_basis_date": "2026-03-19",
        "estimated_price": 2.0,
        "estimated_units": 50.0,
    }


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data_akshare")
@patch("core.user_assets.load_price_data")
def test_otc_fund_dca_confirms_next_trading_day_and_starts_earning_on_confirmation_day(
    mock_load_price,
    mock_load_price_akshare,
    _mock_realtime,
    asset_service,
):
    execution_dates = pd.to_datetime(["2026-03-19", "2026-03-20"])
    mock_load_price.return_value = pd.DataFrame({"002611": [2.00, 2.05]}, index=execution_dates)
    mock_load_price_akshare.return_value = pd.DataFrame({"002611": [2.00, 2.05]}, index=execution_dates)

    asset_service.upsert_asset(
        1,
        {
            "ticker": "002611",
            "asset_name": "Fund DCA Test",
            "asset_type": "fund",
            "units": 0,
            "avg_cost": 0,
            "trade_date": "2026-03-18",
            "dca_rule": {
                "enabled": True,
                "frequency": "weekly",
                "weekday": 3,
                "amount": 100,
                "start_date": "2026-03-19",
                "shift_to_next_trading_day": True,
            },
        },
    )

    friday_result = asset_service.reconcile_due_dca(1, as_of=dt.date(2026, 3, 20))
    assert friday_result["created"] == 1

    txns = asset_service.list_transactions(1, "002611")
    dca_trades = [item for item in txns if item["source"] == "dca"]
    assert len(dca_trades) == 1
    assert dca_trades[0]["trade_date"] == "2026-03-20"
    assert dca_trades[0]["price"] == pytest.approx(2.00)

    class FridayDate(dt.date):
        @classmethod
        def today(cls) -> "FridayDate":
            return cls(2026, 3, 20)

    with patch("core.user_assets.dt.date", FridayDate):
        overview = asset_service.get_overview(1, sync_dca=False, force_refresh=True)

    asset = overview["assets"][0]
    assert asset["units"] == pytest.approx(50.0)
    assert asset["invested_amount"] == pytest.approx(100.0)
    assert asset["pending_dca"] is None
    assert asset["current_price"] == pytest.approx(2.05)
    assert asset["total_return"] == pytest.approx(2.5)
    assert asset["day_change"] == pytest.approx(2.5)
    assert asset["week_change"] == pytest.approx(2.5)

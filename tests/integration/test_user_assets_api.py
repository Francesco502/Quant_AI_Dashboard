from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pandas as pd
import pytest

from core.database import Database
from core.user_assets import UserAssetService


pytestmark = pytest.mark.integration


@pytest.fixture
def api_user_asset_service():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(os.path.join(tmpdir, "api_user_assets.db"))
        with patch("core.user_assets.get_database", return_value=db):
            service = UserAssetService()
            yield service
            if service.db.conn:
                service.db.conn.close()


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data")
def test_user_asset_api_crud(mock_load_price, _mock_realtime, auth_client, api_user_asset_service):
    dates = pd.to_datetime(["2026-03-18", "2026-03-19"])
    mock_load_price.return_value = pd.DataFrame({"159755": [0.65, 0.70]}, index=dates)

    with patch("api.routers.user_assets.get_user_asset_service", return_value=api_user_asset_service):
        create_resp = auth_client.post(
            "/api/user/assets",
            json={
                "ticker": "159755",
                "asset_name": "电池ETF",
                "asset_category": "主题权益",
                "asset_style": "成长",
                "units": 100,
                "avg_cost": 0.65,
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

        assert create_resp.status_code == 200
        payload = create_resp.json()
        assert payload["summary"]["asset_count"] == 1
        assert payload["assets"][0]["ticker"] == "159755"
        assert payload["assets"][0]["asset_type"] == "etf"

        overview_resp = auth_client.get("/api/user/assets?sync_dca=false")
        assert overview_resp.status_code == 200
        overview = overview_resp.json()
        assert overview["assets"][0]["market_value"] == pytest.approx(70.0)

        tx_resp = auth_client.get("/api/user/assets/transactions?ticker=159755")
        assert tx_resp.status_code == 200
        assert tx_resp.json()["count"] >= 1


@patch("core.user_assets.load_cn_realtime_quotes_sina")
@patch("core.user_assets.load_price_data_akshare")
@patch("core.user_assets.load_price_data")
def test_user_asset_overview_fast_mode_skips_external_quote_refresh(
    mock_load_price,
    mock_fund_nav,
    mock_realtime,
    api_user_asset_service,
):
    dates = pd.to_datetime(["2026-03-18", "2026-03-19"])
    mock_load_price.return_value = pd.DataFrame({"159755": [0.65, 0.70]}, index=dates)
    mock_fund_nav.return_value = pd.DataFrame({"159755": [0.66, 0.71]}, index=dates)
    mock_realtime.return_value = {"159755": {"price": 0.72, "trade_date": "2026-03-19"}}

    api_user_asset_service.upsert_asset(
        1,
        {
            "ticker": "159755",
            "asset_name": "电池ETF",
            "asset_type": "etf",
            "units": 100,
            "avg_cost": 0.65,
        },
    )

    mock_fund_nav.reset_mock()
    mock_realtime.reset_mock()
    overview = api_user_asset_service.get_overview(1, sync_dca=False, force_refresh=True, refresh_market=False)

    assert overview["assets"][0]["current_price"] == pytest.approx(0.70)
    mock_fund_nav.assert_not_called()
    mock_realtime.assert_not_called()


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data")
def test_user_asset_api_reconcile(mock_load_price, _mock_realtime, auth_client, api_user_asset_service):
    dates = pd.to_datetime(["2026-03-13", "2026-03-16"])
    mock_load_price.return_value = pd.DataFrame({"006195": [3.30, 3.40]}, index=dates)

    with patch("api.routers.user_assets.get_user_asset_service", return_value=api_user_asset_service):
        auth_client.post(
            "/api/user/assets",
            json={
                "ticker": "006195",
                "asset_name": "国金量化多因子股票A",
                "units": 0,
                "avg_cost": 0,
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

        reconcile_resp = auth_client.post("/api/user/assets/reconcile")
        assert reconcile_resp.status_code == 200
        body = reconcile_resp.json()
        assert body["reconcile"]["rules_checked"] == 1
        assert body["summary"]["asset_count"] == 1


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data")
def test_user_asset_api_imports_csv(mock_load_price, _mock_realtime, auth_client, api_user_asset_service):
    dates = pd.to_datetime(["2026-03-18", "2026-03-19"])
    mock_load_price.return_value = pd.DataFrame(
        {
            "159755": [0.65, 0.70],
            "510300": [4.10, 4.20],
        },
        index=dates,
    )
    csv_payload = (
        "ticker,asset_name,asset_type,units,avg_cost,trade_date,notes\n"
        "159755,电池ETF,etf,100,0.65,2026-03-18,first import\n"
        "510300,沪深300ETF,etf,50,4.10,2026-03-18,second import\n"
    )

    with patch("api.routers.user_assets.get_user_asset_service", return_value=api_user_asset_service):
        response = auth_client.post(
            "/api/user/assets/import-csv",
            files={"file": ("assets.csv", csv_payload.encode("utf-8"), "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 2
    assert body["summary"]["asset_count"] == 2
    assert {asset["ticker"] for asset in body["assets"]} == {"159755", "510300"}


@patch("core.user_assets.load_cn_realtime_quotes_sina", return_value={})
@patch("core.user_assets.load_price_data")
def test_user_asset_api_update_supports_ticker_change(mock_load_price, _mock_realtime, auth_client, api_user_asset_service):
    dates = pd.to_datetime(["2026-03-18", "2026-03-19"])
    mock_load_price.return_value = pd.DataFrame({"013281X": [1.13, 1.14]}, index=dates)

    with patch("api.routers.user_assets.get_user_asset_service", return_value=api_user_asset_service):
        create_resp = auth_client.post(
            "/api/user/assets",
            json={
                "ticker": "013281",
                "asset_name": "国泰海通30天滚动持有中短债债券A",
                "units": 10,
                "avg_cost": 1.13,
            },
        )
        assert create_resp.status_code == 200

        update_resp = auth_client.put(
            "/api/user/assets/013281",
            json={
                "ticker": "013281X",
                "asset_name": "国泰海通30天滚动持有中短债债券A-测试",
                "units": 12,
                "avg_cost": 1.12,
            },
        )

        assert update_resp.status_code == 200
        body = update_resp.json()
        assert body["assets"][0]["ticker"] == "013281X"
        assert body["assets"][0]["asset_name"] == "国泰海通30天滚动持有中短债债券A-测试"

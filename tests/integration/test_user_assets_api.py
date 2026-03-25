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

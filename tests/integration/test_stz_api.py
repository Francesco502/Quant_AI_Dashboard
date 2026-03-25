"""Integration tests for StockTradebyZ endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest


pytestmark = pytest.mark.integration


class TestStockTradebyZAPI:
    def test_update_data_sources_is_forbidden_for_clients(
        self,
        auth_client,
    ):
        response = auth_client.post(
            "/api/stz/data-sources",
            json={"sources": ["Tushare", "AkShare"], "api_keys": {"TUSHARE_TOKEN": "demo"}},
        )

        assert response.status_code == 403
        payload = response.json()
        assert "服务器环境变量统一管理" in payload["detail"]

    @patch("api.routers.stocktradebyz.save_selector_results", return_value=True)
    @patch("api.routers.stocktradebyz.run_selectors_for_universe")
    @patch("api.routers.stocktradebyz._load_asset_pool")
    def test_run_strategy_normalizes_object_asset_pool(
        self,
        mock_load_asset_pool,
        mock_run_selectors_for_universe,
        _mock_save_selector_results,
        auth_client,
    ):
        mock_load_asset_pool.return_value = [
            {"ticker": "002611", "name": "博时黄金ETF联接C", "alias": "黄金"},
            {"ticker": "160615", "name": "鹏华沪深300ETF联接A", "alias": ""},
        ]
        mock_run_selectors_for_universe.return_value = pd.DataFrame(
            [
                {
                    "ticker": "002611",
                    "name": "博时黄金ETF联接C",
                    "selector_class": "TestSelector",
                    "selector_alias": "黄金策略",
                    "trade_date": "2026-03-19",
                    "last_close": 2.53,
                    "score": 88.0,
                }
            ]
        )

        response = auth_client.post(
            "/api/stz/run",
            json={"trade_date": "2026-03-19", "mode": "universe"},
        )

        assert response.status_code == 200
        assert mock_run_selectors_for_universe.call_args.kwargs["tickers"] == ["002611", "160615"]
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["count"] == 1

    @patch("api.routers.stocktradebyz.load_cn_realtime_quotes_sina", return_value={})
    @patch("api.routers.stocktradebyz.load_price_data")
    @patch("api.routers.stocktradebyz._load_asset_pool_as_dicts")
    def test_asset_pool_prefers_fund_nav_for_fund_assets(
        self,
        mock_load_asset_pool_as_dicts,
        mock_load_price_data,
        _mock_realtime_quotes,
        auth_client,
    ):
        index = pd.to_datetime(["2026-03-18", "2026-03-19"])
        mock_load_asset_pool_as_dicts.return_value = [
            {
                "ticker": "002611",
                "name": "博时黄金ETF联接C",
                "alias": "黄金",
                "asset_type": "fund",
            }
        ]
        mock_load_price_data.return_value = pd.DataFrame({"002611": [3.2510, 3.3376]}, index=index)

        response = auth_client.get("/api/stz/asset-pool")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["ticker"] == "002611"
        assert payload[0]["asset_type"] == "fund"
        assert payload[0]["last_price"] == pytest.approx(3.3376)
        assert payload[0]["last_price_date"] == "2026-03-19"
        assert payload[0]["price_source"] == "fund_nav"

    @patch("api.routers.stocktradebyz.search_assets")
    def test_asset_search_returns_candidates(self, mock_search_assets, auth_client):
        mock_search_assets.return_value = [
            {
                "ticker": "002611",
                "name": "博时黄金ETF联接C",
                "asset_type": "fund",
                "market": "CN",
                "source": "fund_name_em",
                "category": "联接基金",
                "score": 140,
            }
        ]

        response = auth_client.get("/api/stz/asset-search?q=002611&limit=8")

        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["ticker"] == "002611"
        assert payload[0]["name"] == "博时黄金ETF联接C"
        assert payload[0]["asset_type"] == "fund"

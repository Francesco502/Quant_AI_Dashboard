"""Integration tests for external data API routes."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest


pytestmark = pytest.mark.integration


@patch("api.routers.external.merge_price_with_external")
@patch("api.routers.external.load_external_data")
@patch("api.routers.external.load_price_data")
def test_external_merge_contract(
    mock_load_price_data,
    mock_load_external_data,
    mock_merge_price_with_external,
    auth_client,
):
    dates = pd.date_range(start="2025-01-01", periods=3, freq="B")
    price_df = pd.DataFrame(
        {
            "600519": [100.0, 101.0, 102.0],
        },
        index=dates,
    )
    merged_df = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d").tolist(),
            "600519": [100.0, 101.0, 102.0],
            "macro_score": [1.1, 1.2, 1.3],
        }
    )

    mock_load_price_data.return_value = price_df
    mock_load_external_data.return_value = {"economic": {"macro_score": [1.1, 1.2, 1.3]}}
    mock_merge_price_with_external.return_value = merged_df

    response = auth_client.post(
        "/api/external/merge?tickers=600519&days=30",
        json={
            "economic": True,
            "industry": False,
            "sentiment": False,
            "flow": False,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["columns"] == ["date", "600519", "macro_score"]
    assert len(body["data"]["data"]) == 3

    mock_load_price_data.assert_called_once_with(tickers=["600519"], days=30)
    mock_load_external_data.assert_called_once()
    mock_merge_price_with_external.assert_called_once()

"""Integration tests for portfolio API contract."""

from unittest.mock import patch

import pandas as pd
import pytest


pytestmark = pytest.mark.integration


@patch("core.portfolio_analyzer.generate_multi_asset_signals")
@patch("core.portfolio_analyzer.load_price_data")
def test_portfolio_analyze_contract(mock_load_price_data, mock_generate_signals, auth_client):
    dates = pd.date_range(start="2025-01-01", periods=120, freq="B")
    mock_load_price_data.return_value = pd.DataFrame(
        {
            "600519": pd.Series(range(100, 220), index=dates, dtype=float),
            "000001": pd.Series(range(50, 170), index=dates, dtype=float),
        },
        index=dates,
    )
    mock_generate_signals.return_value = pd.DataFrame()

    payload = {
        "holdings": [
            {"ticker": "600519", "shares": 100},
            {"ticker": "000001", "shares": 200},
        ]
    }

    response = auth_client.post("/api/portfolio/analyze", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "correlations" in body
    assert "contributions" in body
    assert isinstance(body["correlations"], list)
    assert isinstance(body["contributions"], list)
    assert len(body["correlations"]) == 2
    assert len(body["contributions"]) == 2

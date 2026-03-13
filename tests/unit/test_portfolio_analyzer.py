"""Unit tests for portfolio analyzer and risk analysis helpers."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from core.portfolio_analyzer import PortfolioAnalyzer
from core.risk_analysis import (
    calculate_correlation_matrix,
    calculate_cvar,
    calculate_max_drawdown,
    calculate_portfolio_risk_metrics,
    calculate_var,
)


class TestRiskAnalysisFunctions:
    def test_calculate_var_and_cvar(self):
        returns = pd.Series([0.01, 0.02, -0.01, -0.02, 0.01, 0.015, -0.015, 0.005])
        var = calculate_var(returns, 0.05)
        cvar = calculate_cvar(returns, 0.05)
        assert isinstance(var, float)
        assert isinstance(cvar, float)
        assert var <= 0

    def test_calculate_max_drawdown(self):
        prices = pd.Series([100, 110, 120, 115, 100, 90])
        max_dd, dd_series = calculate_max_drawdown(prices)
        assert isinstance(max_dd, float)
        assert max_dd <= 0
        assert len(dd_series) == len(prices)

    def test_correlation_matrix_shape(self):
        returns = pd.DataFrame(
            {
                "AAPL": [0.01, 0.02, -0.01, 0.015, 0.01],
                "MSFT": [0.012, 0.018, -0.008, 0.016, 0.009],
                "GOOGL": [0.008, 0.022, -0.012, 0.014, 0.011],
            }
        )
        corr = calculate_correlation_matrix(returns)
        assert corr.shape == (3, 3)
        assert np.allclose(np.diag(corr.values), np.ones(3))

    def test_portfolio_risk_metrics_keys(self):
        returns = pd.DataFrame(
            {
                "AAPL": [0.01, 0.02, -0.01, 0.015, 0.01],
                "MSFT": [0.012, 0.018, -0.008, 0.016, 0.009],
            }
        )
        weights = np.array([0.6, 0.4])
        metrics = calculate_portfolio_risk_metrics(returns, weights)
        assert "annual_return" in metrics
        assert "annual_volatility" in metrics
        assert "sharpe_ratio" in metrics


class TestPortfolioAnalyzer:
    @pytest.fixture
    def tickers(self):
        return ["600519", "000001", "AAPL"]

    @pytest.fixture
    def mock_price_df(self):
        dates = pd.date_range(start="2025-01-01", periods=100, freq="B")
        return pd.DataFrame(
            {
                "600519": np.linspace(100, 120, 100),
                "000001": np.linspace(50, 60, 100),
                "AAPL": np.linspace(150, 180, 100),
            },
            index=dates,
        )

    @patch("core.portfolio_analyzer.load_price_data")
    def test_analyze_basic(self, mock_load_price, tickers, mock_price_df):
        mock_load_price.return_value = mock_price_df
        result = PortfolioAnalyzer(tickers=tickers).analyze(days=100)
        assert "summary" in result
        assert "asset_metrics" in result
        assert "correlations" in result
        assert "contributions" in result

    @patch("core.portfolio_analyzer.load_price_data")
    def test_analyze_with_custom_weights(self, mock_load_price, tickers, mock_price_df):
        mock_load_price.return_value = mock_price_df
        result = PortfolioAnalyzer(tickers=tickers, weights=[0.5, 0.3, 0.2]).analyze(days=100)
        weights = result["weights"]
        assert weights["600519"] == 0.5
        assert weights["000001"] == 0.3
        assert weights["AAPL"] == 0.2

    @patch("core.portfolio_analyzer.load_price_data")
    def test_analyze_weights_from_position_market_value(self, mock_load_price):
        dates = pd.date_range(start="2025-01-01", periods=5, freq="B")
        mock_load_price.return_value = pd.DataFrame(
            {
                "AAA": [10, 10, 10, 10, 10],
                "BBB": [20, 20, 20, 20, 20],
            },
            index=dates,
        )
        result = PortfolioAnalyzer(
            tickers=["AAA", "BBB"],
            position_shares={"AAA": 100, "BBB": 100},
        ).analyze(days=5)
        weights = result["weights"]
        assert pytest.approx(weights["AAA"], rel=1e-5) == 1 / 3
        assert pytest.approx(weights["BBB"], rel=1e-5) == 2 / 3

    @patch("core.portfolio_analyzer.load_price_data")
    def test_analyze_empty_data(self, mock_load_price, tickers):
        mock_load_price.return_value = pd.DataFrame()
        result = PortfolioAnalyzer(tickers=tickers).analyze(days=100)
        assert result["error"] == "无法获取价格数据"

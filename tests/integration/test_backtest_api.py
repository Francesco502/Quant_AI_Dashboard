"""Integration tests for backtest API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


pytestmark = pytest.mark.integration


class TestBacktestAPI:
    @patch("api.routers.backtest.load_price_data")
    def test_run_multi_strategy_backtest(self, mock_load_price, auth_client):
        dates = pd.date_range(start="2025-01-01", periods=100, freq="B")
        bench_dates = pd.date_range(start="2024-12-01", periods=130, freq="B")

        def mock_side_effect(tickers, days=None):
            if tickers[0] == "000300.SH":
                return pd.DataFrame({"000300.SH": np.linspace(3000, 4000, 130)}, index=bench_dates)
            return pd.DataFrame({"600519": np.linspace(100, 150, 100)}, index=dates)

        mock_load_price.side_effect = mock_side_effect

        payload = {
            "strategies": {
                "sma_crossover": {"weight": 0.5, "params": {"short_window": 5, "long_window": 15}},
                "mean_reversion": {"weight": 0.5, "params": {"window": 10, "std_dev": 1.5}},
            },
            "tickers": ["600519"],
            "start_date": "2025-01-01",
            "end_date": "2025-04-10",
            "initial_capital": 100000.0,
            "benchmark_ticker": "000300.SH",
        }

        response = auth_client.post("/api/backtest/run-multi", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "portfolio" in data
        assert "individual" in data
        assert "metrics" in data["portfolio"]
        assert "equity_curve" in data["portfolio"]
        assert "weights" in data["portfolio"]

    @patch("api.routers.backtest.load_price_data")
    def test_run_multi_strategy_empty_strategies(self, mock_load_price, auth_client):
        dates = pd.date_range(start="2025-01-01", periods=100, freq="B")
        mock_load_price.return_value = pd.DataFrame({"600519": np.linspace(100, 150, 100)}, index=dates)

        payload = {
            "strategies": {},
            "tickers": ["600519"],
            "start_date": "2025-01-01",
            "initial_capital": 100000.0,
        }

        response = auth_client.post("/api/backtest/run-multi", json=payload)
        assert response.status_code == 500

    @patch("api.routers.backtest.load_price_data")
    def test_optimize_parameters(self, mock_load_price, auth_client):
        dates = pd.date_range(start="2025-01-01", periods=100, freq="B")
        mock_load_price.return_value = pd.DataFrame({"600519": np.linspace(100, 150, 100)}, index=dates)

        payload = {
            "strategy_id": "sma_crossover",
            "tickers": ["600519"],
            "param_grid": {"short_window": [5, 10, 15], "long_window": [15, 20, 25]},
            "start_date": "2025-01-01",
            "end_date": "2025-04-10",
            "initial_capital": 100000.0,
            "objective": "sharpe_ratio",
            "cv_days": 60,
        }

        response = auth_client.post("/api/backtest/optimize", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "best_params" in data
        assert "best_score" in data
        assert "all_results" in data
        assert "best_result" in data

    @patch("api.routers.backtest.load_price_data")
    def test_optimize_invalid_strategy(self, mock_load_price, auth_client):
        dates = pd.date_range(start="2025-01-01", periods=100, freq="B")
        mock_load_price.return_value = pd.DataFrame({"600519": np.linspace(100, 150, 100)}, index=dates)

        payload = {
            "strategy_id": "invalid_strategy",
            "tickers": ["600519"],
            "param_grid": {"param1": [1, 2, 3]},
            "start_date": "2025-01-01",
            "initial_capital": 100000.0,
        }

        response = auth_client.post("/api/backtest/optimize", json=payload)
        assert response.status_code == 404

    @patch("api.routers.backtest.load_price_data")
    def test_extended_analysis(self, mock_load_price, auth_client):
        benchmark_dates = pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"])
        mock_load_price.return_value = pd.DataFrame(
            {"000300.SH": [3000.0, 3060.0, 3120.0]},
            index=benchmark_dates,
        )

        payload = {
            "equity_curve": [
                {"date": "2025-01-01", "equity": 100000, "cash": 100000},
                {"date": "2025-02-01", "equity": 105000, "cash": 5000},
                {"date": "2025-03-01", "equity": 110000, "cash": 10000},
            ],
            "trades": [
                {"date": "2025-01-05", "ticker": "600519", "action": "buy", "shares": 100, "price": 100.0, "cost": 10018.0},
                {"date": "2025-02-05", "ticker": "600519", "action": "sell", "shares": 100, "price": 105.0, "cost": 10521.0},
            ],
            "initial_capital": 100000.0,
            "benchmark_ticker": "000300.SH",
        }

        response = auth_client.post("/api/backtest/extended-analysis", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["benchmark"]["ticker"] == "000300.SH"
        assert data["benchmark"]["loaded"] is True
        assert "information_ratio" in data["metrics"]

    def test_export_backtest_html(self, auth_client):
        payload = {
            "equity_curve": [
                {"date": "2025-01-01", "equity": 100000, "cash": 100000},
                {"date": "2025-12-31", "equity": 120000, "cash": 20000},
            ],
            "trades": [],
            "metrics": {},
            "format": "html",
        }

        response = auth_client.post("/api/backtest/export", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "html"

    def test_list_benchmarks(self, auth_client):
        response = auth_client.get("/api/backtest/benchmarks")
        assert response.status_code == 200
        data = response.json()
        assert "benchmarks" in data
        assert isinstance(data["benchmarks"], list)
        assert len(data["benchmarks"]) > 0

    def test_compare_strategies(self, auth_client):
        payload = {
            "equity_curves": {
                "strategy1": [
                    {"date": "2025-01-01", "equity": 100000},
                    {"date": "2025-12-31", "equity": 120000},
                ],
                "strategy2": [
                    {"date": "2025-01-01", "equity": 100000},
                    {"date": "2025-12-31", "equity": 115000},
                ],
            },
            "trades": {"strategy1": [], "strategy2": []},
            "initial_capital": 100000.0,
        }

        response = auth_client.post("/api/backtest/compare-strategies", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "comparison_table" in data
        assert "summary" in data

    def test_run_single_strategy(self, auth_client):
        payload = {
            "strategy_id": "sma_crossover",
            "tickers": ["600519"],
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "initial_capital": 100000.0,
            "params": {"short_window": 10, "long_window": 30},
        }

        response = auth_client.post("/api/backtest/run", json=payload)
        assert response.status_code in [200, 500]

    def test_list_strategies(self, auth_client):
        response = auth_client.get("/api/backtest/strategies")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        strategy_ids = {item["id"] for item in data}
        assert "ema_crossover" in strategy_ids
        assert "macd_trend" in strategy_ids
        assert "donchian_breakout" in strategy_ids
        assert "momentum_rotation" in strategy_ids

    @patch("api.routers.backtest.load_price_data")
    def test_run_new_builtin_strategy(self, mock_load_price, auth_client):
        dates = pd.date_range(start="2025-01-01", periods=160, freq="B")
        mock_load_price.return_value = pd.DataFrame({"600519": np.linspace(100, 180, len(dates))}, index=dates)

        payload = {
            "strategy_id": "macd_trend",
            "tickers": ["600519"],
            "start_date": "2025-01-01",
            "end_date": "2025-08-15",
            "initial_capital": 100000.0,
            "params": {"fast": 12, "slow": 26, "signal": 9},
        }

        response = auth_client.post("/api/backtest/run", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "equity_curve" in data

    @patch("api.routers.backtest.load_price_data")
    def test_run_donchian_breakout_strategy(self, mock_load_price, auth_client):
        dates = pd.date_range(start="2025-01-01", periods=180, freq="B")
        prices = np.concatenate([np.linspace(100, 120, 120), np.linspace(121, 150, 60)])
        mock_load_price.return_value = pd.DataFrame({"600519": prices}, index=dates)

        payload = {
            "strategy_id": "donchian_breakout",
            "tickers": ["600519"],
            "start_date": "2025-01-01",
            "end_date": "2025-09-30",
            "initial_capital": 100000.0,
            "params": {"breakout_window": 55, "exit_window": 20},
        }

        response = auth_client.post("/api/backtest/run", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "equity_curve" in data

    def test_health_check(self, auth_client):
        response = auth_client.get("/api/health")
        assert response.status_code == 200


class TestBacktestAPIErrorHandling:
    def test_invalid_date_format(self, auth_client):
        payload = {
            "strategy_id": "sma_crossover",
            "tickers": ["600519"],
            "start_date": "invalid-date",
            "initial_capital": 100000.0,
        }

        response = auth_client.post("/api/backtest/run", json=payload)
        assert response.status_code == 422

    def test_missing_required_fields(self, auth_client):
        payload = {"strategy_id": "sma_crossover"}
        response = auth_client.post("/api/backtest/run", json=payload)
        assert response.status_code == 422

    def test_invalid_strategy(self, auth_client):
        payload = {
            "strategy_id": "nonexistent_strategy",
            "tickers": ["600519"],
            "start_date": "2025-01-01",
            "initial_capital": 100000.0,
        }

        response = auth_client.post("/api/backtest/run", json=payload)
        assert response.status_code == 404

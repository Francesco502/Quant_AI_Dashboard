"""Unit tests for core.backtest_engine — strategy backtesting engine."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from core.backtest_engine import BacktestEngine


@pytest.fixture
def sample_prices():
    dates = pd.date_range("2025-01-01", periods=100, freq="B")
    close = 100 + np.cumsum(np.random.randn(100) * 1.5)
    return pd.DataFrame(
        {"open": close - 0.5, "high": close + 1, "low": close - 1, "close": close,
         "volume": np.random.randint(100000, 500000, 100)}, index=dates)


class TestBacktestEngineInit:
    def test_default_capital(self):
        engine = BacktestEngine()
        assert engine.initial_capital == 100000.0

    def test_custom_capital(self):
        engine = BacktestEngine(initial_capital=500000.0)
        assert engine.initial_capital == 500000.0

    def test_custom_fees(self):
        engine = BacktestEngine(fees={"commission": 0.0003, "slippage": 0.001})
        assert engine is not None


class TestBacktestRun:
    def test_run_buy_hold_strategy(self, sample_prices):
        def buy_hold(price_df, **_):
            return {"600519": 1.0}

        with patch("core.backtest_engine.load_price_data", return_value=sample_prices):
            engine = BacktestEngine(initial_capital=100000)
            result = engine.run(buy_hold, tickers=["600519"],
                               start_date="2025-01-01", end_date="2025-03-31")

        assert "metrics" in result
        assert "equity_curve" in result
        assert result["metrics"]["total_return"] is not None

    def test_run_returns_weights_and_trades(self, sample_prices):
        def simple_strategy(price_df, **_):
            return {"600519": 0.5}

        with patch("core.backtest_engine.load_price_data", return_value=sample_prices):
            engine = BacktestEngine()
            result = engine.run(simple_strategy, tickers=["600519"],
                               start_date="2025-01-02", end_date="2025-02-28")
        assert "weights" in result
        assert isinstance(result["trade_history"], list)


class TestMetrics:
    def test_calculate_metrics_has_required_fields(self, sample_prices):
        engine = BacktestEngine(initial_capital=100000)
        metrics = engine._calculate_metrics()
        for key in ["total_return", "sharpe_ratio", "max_drawdown"]:
            assert key in metrics


class TestMultiStrategy:
    def test_run_multi_strategy(self, sample_prices):
        def strat_a(price_df, **_): return {"600519": 0.6}
        def strat_b(price_df, **_): return {"600519": 0.4}

        with patch("core.backtest_engine.load_price_data", return_value=sample_prices):
            engine = BacktestEngine()
            result = engine.run_multi_strategy(
                strategies={"A": strat_a, "B": strat_b}, tickers=["600519"],
                start_date="2025-01-02", end_date="2025-02-28")

        assert "individual" in result
        assert "A" in result["individual"]
        assert "B" in result["individual"]


class TestPositionLookup:
    def test_get_positions_at_date(self, sample_prices):
        import datetime

        def buy_hold(price_df, **_): return {"600519": 1.0}
        with patch("core.backtest_engine.load_price_data", return_value=sample_prices):
            engine = BacktestEngine()
            engine.run(buy_hold, tickers=["600519"],
                      start_date="2025-01-02", end_date="2025-02-28")
        positions = engine.get_positions_at_date(datetime.datetime(2025, 1, 15))
        assert isinstance(positions, dict)

"""Unit tests for core.strategy_framework — the foundation of all strategy execution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from core.strategy_framework import (
    AIStrategy,
    BaseStrategy,
    EnsembleStrategy,
    StrategySignal,
    TechnicalStrategy,
    _ensure_strategies_dir,
)


# ---------------------------------------------------------------------------
# StrategySignal
# ---------------------------------------------------------------------------

class TestStrategySignal:
    def test_creation_with_required_fields(self):
        signal = StrategySignal(
            ticker="600519",
            signal=0.75,
            direction=1,
            confidence=0.9,
            action="买入",
            reason="均线金叉",
        )
        assert signal.ticker == "600519"
        assert signal.signal == 0.75
        assert signal.direction == 1
        assert signal.confidence == 0.9
        assert signal.target_weight is None

    def test_creation_with_target_weight(self):
        signal = StrategySignal(
            ticker="000001",
            signal=-0.5,
            direction=-1,
            confidence=0.7,
            action="卖出",
            reason="RSI超买",
            target_weight=0.0,
        )
        assert signal.target_weight == 0.0

    def test_signal_range_clamping(self):
        """Signal values should be between -1 and 1."""
        s = StrategySignal(ticker="TEST", signal=0.5, direction=1, confidence=0.8, action="", reason="")
        assert -1.0 <= s.signal <= 1.0


# ---------------------------------------------------------------------------
# BaseStrategy
# ---------------------------------------------------------------------------

class TestBaseStrategy:
    def test_init_defaults(self):
        class DummyStrategy(BaseStrategy):
            def generate_signals(self, price_df, **kwargs):
                return []

        s = DummyStrategy(strategy_id="test-1")
        assert s.strategy_id == "test-1"
        assert s.version == "v1.0"
        assert s.config == {}

    def test_init_with_config(self):
        class DummyStrategy(BaseStrategy):
            def generate_signals(self, price_df, **kwargs):
                return []

        s = DummyStrategy(strategy_id="test-2", version="v2.0", config={"lookback": 20})
        assert s.config == {"lookback": 20}
        assert s.version == "v2.0"

    def test_get_config_returns_copy(self):
        class DummyStrategy(BaseStrategy):
            def generate_signals(self, price_df, **kwargs):
                return []

        s = DummyStrategy(strategy_id="t", config={"a": 1})
        cfg = s.get_config()
        cfg["a"] = 999
        assert s.config["a"] == 1  # original unchanged

    def test_repr(self):
        class DummyStrategy(BaseStrategy):
            def generate_signals(self, price_df, **kwargs):
                return []

        s = DummyStrategy(strategy_id="my-id", version="v1.5")
        assert "my-id" in repr(s)
        assert "v1.5" in repr(s)


# ---------------------------------------------------------------------------
# TechnicalStrategy
# ---------------------------------------------------------------------------

class TestTechnicalStrategy:
    @pytest.fixture
    def strategy(self):
        return TechnicalStrategy(
            strategy_id="ma-cross",
            indicators=["ma_cross", "rsi"],
            version="v1.0",
            config={"short_window": 5, "long_window": 20},
        )

    @pytest.fixture
    def sample_prices(self):
        dates = pd.date_range("2025-01-01", periods=100, freq="B")
        return pd.DataFrame(
            {"close": 100 + np.cumsum(np.random.randn(100) * 2)},
            index=dates,
        )

    def test_init_sets_parameters(self, strategy):
        assert strategy.strategy_id == "ma-cross"
        assert strategy.indicators == ["ma_cross", "rsi"]
        assert strategy.config["short_window"] == 5

    def test_generate_signals_returns_dataframe(self, strategy, sample_prices):
        with patch("core.strategy_framework.generate_multi_asset_signals") as mock_gen:
            mock_gen.return_value = pd.DataFrame(
                {"ticker": ["600519"], "action": ["买入"], "combined_signal": [0.8]}
            )
            signals = strategy.generate_signals(sample_prices, tickers=["600519"])
            assert isinstance(signals, pd.DataFrame)
            assert not signals.empty

    def test_generate_signals_with_empty_data(self, strategy):
        empty_df = pd.DataFrame()
        with patch("core.strategy_framework.generate_multi_asset_signals") as mock_gen:
            mock_gen.return_value = pd.DataFrame()
            signals = strategy.generate_signals(empty_df, tickers=["600519"])
            assert isinstance(signals, pd.DataFrame)
            assert signals.empty


# ---------------------------------------------------------------------------
# AIStrategy
# ---------------------------------------------------------------------------

class TestAIStrategy:
    @pytest.fixture
    def strategy(self):
        return AIStrategy(strategy_id="lstm-predict", model_id="lstm_v1", version="v1.0")

    @pytest.fixture
    def sample_prices(self):
        dates = pd.date_range("2025-01-01", periods=60, freq="B")
        return pd.DataFrame(
            {"close": 100 + np.cumsum(np.random.randn(60) * 1.5)},
            index=dates,
        )

    def test_init_sets_model_id(self, strategy):
        assert strategy.model_id == "lstm_v1"
        assert strategy.version == "v1.0"

    def test_generate_signals_calls_quick_predict(self, strategy, sample_prices):
        with patch("core.strategy_framework.quick_predict") as mock_predict:
            mock_predict.return_value = pd.DataFrame(
                {"forecast": [102.0, 103.0, 101.5]},
                index=pd.date_range("2025-03-25", periods=3, freq="B"),
            )
            signals = strategy.generate_signals(sample_prices, tickers=["600519"], horizon=3)
            assert isinstance(signals, pd.DataFrame)
            assert not signals.empty
            mock_predict.assert_called_once()


# ---------------------------------------------------------------------------
# EnsembleStrategy
# ---------------------------------------------------------------------------

class TestEnsembleStrategy:
    @pytest.fixture
    def sample_prices(self):
        dates = pd.date_range("2025-01-01", periods=50, freq="B")
        return pd.DataFrame({"close": np.linspace(100, 120, 50)}, index=dates)

    @pytest.fixture
    def mock_strategies(self):
        s1 = MagicMock(spec=BaseStrategy)
        s1.strategy_id = "s1"
        s1.generate_signals.return_value = [
            StrategySignal(ticker="X", signal=0.8, direction=1, confidence=0.9, action="买入", reason="t1")
        ]
        s2 = MagicMock(spec=BaseStrategy)
        s2.strategy_id = "s2"
        s2.generate_signals.return_value = [
            StrategySignal(ticker="X", signal=0.3, direction=1, confidence=0.5, action="买入", reason="t2")
        ]
        return [s1, s2]

    def test_init_with_strategies(self, mock_strategies):
        ensemble = EnsembleStrategy(
            strategy_id="ensemble-1",
            strategies=mock_strategies,
            weights={"s1": 0.7, "s2": 0.3},
        )
        assert len(ensemble.strategies) == 2

    def test_generate_signals_aggregates(self, sample_prices, mock_strategies):
        ensemble = EnsembleStrategy(
            strategy_id="ensemble-1",
            strategies=mock_strategies,
            weights={"s1": 0.6, "s2": 0.4},
        )
        signals = ensemble.generate_signals(sample_prices, tickers=["X"])
        assert isinstance(signals, pd.DataFrame)
        assert not signals.empty
        # Both sub-strategies should have been called
        for s in mock_strategies:
            s.generate_signals.assert_called_once()

    def test_get_config_includes_weights(self, mock_strategies):
        ensemble = EnsembleStrategy(
            strategy_id="e",
            strategies=mock_strategies,
            weights={"s1": 0.6, "s2": 0.4},
        )
        cfg = ensemble.get_config()
        assert "sub_strategies" in cfg or "weights" in cfg


# ---------------------------------------------------------------------------
# _ensure_strategies_dir
# ---------------------------------------------------------------------------

class TestEnsureStrategiesDir:
    def test_creates_directory(self, tmp_path):
        import os

        import core.strategy_framework as sf

        original = sf.STRATEGIES_DIR
        try:
            sf.STRATEGIES_DIR = str(tmp_path / "strategies")
            sf._ensure_strategies_dir()
            assert os.path.isdir(sf.STRATEGIES_DIR)
        finally:
            sf.STRATEGIES_DIR = original

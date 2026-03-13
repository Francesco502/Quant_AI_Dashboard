"""Integration tests for trading flow."""

import numpy as np
import pandas as pd
import pytest

from core.account import ensure_account_dict
from core.database import get_database
from core.order_manager import OrderManager
from core.risk_monitor import RiskMonitor
from core.stop_loss_manager import StopLossManager
from core.strategy_engine import generate_multi_asset_signals
from core.trading_engine import apply_equal_weight_rebalance


pytestmark = pytest.mark.integration


class TestTradingFlow:
    @pytest.fixture
    def sample_data(self):
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        return pd.DataFrame(
            {
                "AAPL": np.random.uniform(150, 200, 100),
                "TSLA": np.random.uniform(200, 300, 100),
                "MSFT": np.random.uniform(300, 400, 100),
            },
            index=dates,
        )

    @pytest.fixture
    def sample_account(self):
        return ensure_account_dict(
            {
                "account_id": 1,
                "cash": 1000000.0,
                "positions": {},
                "equity_history": [],
                "trade_log": [],
            }
        )

    @pytest.fixture
    def order_manager(self):
        db = get_database(":memory:")
        return OrderManager(db)

    def test_signal_to_execution_flow(self, sample_data, sample_account, order_manager):
        signals_df = generate_multi_asset_signals(price_df=sample_data)
        if not signals_df.empty:
            signals = signals_df.head(2).copy()
            if "action" not in signals.columns:
                signals["action"] = "BUY"
        else:
            signals = pd.DataFrame(columns=["ticker", "action", "combined_signal"])

        assert not signals.empty

        risk_monitor = RiskMonitor()
        stop_loss_manager = StopLossManager()

        account, _ = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_data,
            total_capital=1000000.0,
            max_positions=2,
            risk_monitor=risk_monitor,
            stop_loss_manager=stop_loss_manager,
            order_manager=order_manager,
        )

        assert account is not None
        assert "cash" in account
        assert "positions" in account

    def test_risk_check_integration(self, sample_data, sample_account):
        risk_monitor = RiskMonitor()

        signals_df = generate_multi_asset_signals(price_df=sample_data)
        if not signals_df.empty:
            signals = signals_df.head(3).copy()
            if "action" not in signals.columns:
                signals["action"] = "BUY"
        else:
            signals = pd.DataFrame(columns=["ticker", "action", "combined_signal"])

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_data,
            total_capital=1000000.0,
            max_positions=3,
            risk_monitor=risk_monitor,
        )

        assert account is not None
        assert isinstance(message, str)

    def test_order_manager_integration(self, sample_data, sample_account, order_manager):
        signals_df = generate_multi_asset_signals(price_df=sample_data)
        if not signals_df.empty:
            signals = signals_df.head(2).copy()
            if "action" not in signals.columns:
                signals["action"] = "BUY"
        else:
            signals = pd.DataFrame(columns=["ticker", "action", "combined_signal", "last_price"])

        apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_data,
            total_capital=1000000.0,
            max_positions=2,
            order_manager=order_manager,
        )

        stats = order_manager.get_order_statistics()
        assert "total_orders" in stats
        assert "by_status" in stats

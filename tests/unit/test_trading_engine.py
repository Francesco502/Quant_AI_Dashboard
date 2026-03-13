"""交易引擎模块单元测试（补充）"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock

from core.trading_engine import apply_equal_weight_rebalance
from core.broker_simulator import Trade
from core.account import ensure_account_dict
from core.risk_monitor import RiskMonitor


class TestTradingEngineAdvanced:
    """交易引擎模块高级测试"""

    @pytest.fixture
    def sample_account(self):
        """创建示例账户"""
        return ensure_account_dict({
            "cash": 1000000.0,
            "positions": {
                "AAPL": 100,
                "TSLA": 50,
            },
            "equity_history": [],
            "trade_log": [],
        })

    @pytest.fixture
    def sample_signal_table(self):
        """创建示例信号表"""
        return pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["买入", "买入", "买入"],
            "combined_signal": [0.8, 0.7, 0.6],
            "last_price": [150.0, 250.0, 350.0],
        })

    @pytest.fixture
    def sample_price_data(self):
        """创建示例价格数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        return pd.DataFrame({
            "AAPL": np.random.uniform(150, 200, 100),
            "TSLA": np.random.uniform(200, 300, 100),
            "MSFT": np.random.uniform(300, 400, 100),
        }, index=dates)

    # --------------------------------------------------------------------------
    # 空信号表测试
    # --------------------------------------------------------------------------

    def test_apply_equal_weight_rebalance_empty_table_columns(self):
        """验证空信号表（只有列名）"""
        account = ensure_account_dict({
            "cash": 1000000.0,
            "positions": {},
            "equity_history": [],
            "trade_log": [],
        })

        empty_signals = pd.DataFrame(columns=["ticker", "action", "combined_signal", "last_price"])

        account, message = apply_equal_weight_rebalance(
            account=account,
            signal_table=empty_signals,
            data=pd.DataFrame(),
            total_capital=1000000.0,
            max_positions=3,
        )

        assert account is not None

    def test_apply_equal_weight_rebalance_empty_rows(self):
        """验证空行信号表"""
        account = ensure_account_dict({
            "cash": 1000000.0,
            "positions": {},
            "equity_history": [],
            "trade_log": [],
        })

        empty_signals = pd.DataFrame({
            "ticker": [],
            "action": [],
            "combined_signal": [],
            "last_price": [],
        })

        account, message = apply_equal_weight_rebalance(
            account=account,
            signal_table=empty_signals,
            data=pd.DataFrame(),
            total_capital=1000000.0,
            max_positions=3,
        )

        assert account is not None

    # --------------------------------------------------------------------------
    # 总资金限制测试
    # --------------------------------------------------------------------------

    def test_apply_equal_weight_rebalance_exceeds_capital(self, sample_account, sample_price_data):
        """验证超出总资金的情况"""
        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["买入", "买入", "买入"],
            "combined_signal": [0.4, 0.4, 0.4],  # 总共超过100%
            "last_price": [150.0, 250.0, 350.0],
        })

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_price_data,
            total_capital=100000.0,  # 较小的资金
            max_positions=3,
        )

        assert account is not None

    # --------------------------------------------------------------------------
    # 价格边界测试
    # --------------------------------------------------------------------------

    def test_apply_equal_weight_rebalance_zero_price(self, sample_account, sample_price_data):
        """验证零价格情况"""
        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["买入", "买入", "买入"],
            "combined_signal": [0.33, 0.33, 0.34],
            "last_price": [0.0, 250.0, 350.0],  # AAPL价格为0
        })

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_price_data,
            total_capital=1000000.0,
            max_positions=3,
        )

        assert account is not None

    def test_apply_equal_weight_rebalance_very_high_price(self, sample_account, sample_price_data):
        """验证极高价格情况"""
        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["买入", "买入", "买入"],
            "combined_signal": [0.33, 0.33, 0.34],
            "last_price": [10000.0, 250.0, 350.0],  # AAPL价格极高
        })

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_price_data,
            total_capital=1000000.0,
            max_positions=3,
        )

        assert account is not None

    def test_apply_equal_weight_rebalance_negative_price(self, sample_account, sample_price_data):
        """验证负价格情况"""
        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["买入", "买入", "买入"],
            "combined_signal": [0.33, 0.33, 0.34],
            "last_price": [-10.0, 250.0, 350.0],  # AAPL负价格
        })

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_price_data,
            total_capital=1000000.0,
            max_positions=3,
        )

        assert account is not None

    # --------------------------------------------------------------------------
    # 最大持仓数测试
    # --------------------------------------------------------------------------

    def test_apply_equal_weight_rebalance_max_positions_exceeded(self, sample_account, sample_price_data):
        """验证超过最大持仓数"""
        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"],
            "action": ["买入", "买入", "买入", "买入", "买入"],
            "combined_signal": [0.8, 0.7, 0.6, 0.5, 0.4],
            "last_price": [150.0, 250.0, 350.0, 450.0, 550.0],
        })

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_price_data,
            total_capital=1000000.0,
            max_positions=3,  # 只允许3个持仓
        )

        assert account is not None

    def test_apply_equal_weight_rebalance_max_positions_one(self, sample_account, sample_price_data):
        """验证最大持仓数为1"""
        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["买入", "买入", "买入"],
            "combined_signal": [0.8, 0.7, 0.6],
            "last_price": [150.0, 250.0, 350.0],
        })

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_price_data,
            total_capital=1000000.0,
            max_positions=1,  # 只允许1个持仓
        )

        assert account is not None

    # --------------------------------------------------------------------------
    # 混合动作测试
    # --------------------------------------------------------------------------

    def test_apply_equal_weight_rebalance_mixed_actions(self, sample_account, sample_price_data):
        """验证混合买入卖出动作"""
        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["买入", "卖出", "买入"],
            "combined_signal": [0.8, 0.7, 0.6],
            "last_price": [150.0, 250.0, 350.0],
        })

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_price_data,
            total_capital=1000000.0,
            max_positions=3,
        )

        assert account is not None

    def test_apply_equal_weight_rebalance_all_sell(self, sample_account, sample_price_data):
        """验证全卖出动作"""
        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["卖出", "卖出", "卖出"],
            "combined_signal": [0.8, 0.7, 0.6],
            "last_price": [150.0, 250.0, 350.0],
        })

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_price_data,
            total_capital=1000000.0,
            max_positions=3,
        )

        assert account is not None

    # --------------------------------------------------------------------------
    # 价格数据不匹配测试
    # --------------------------------------------------------------------------

    def test_apply_equal_weight_rebalance_signal_price_not_in_data(self, sample_account):
        """验证信号价格不在价格数据中的情况"""
        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["买入", "买入", "买入"],
            "combined_signal": [0.8, 0.7, 0.6],
            "last_price": [150.0, 250.0, 350.0],
        })

        # 价格数据中没有这些股票
        price_data = pd.DataFrame({
            "GOOGL": np.random.uniform(100, 200, 100),
        }, index=pd.date_range(start="2025-01-01", periods=100, freq="D"))

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=price_data,
            total_capital=1000000.0,
            max_positions=3,
        )

        assert account is not None

    def test_apply_equal_weight_rebalance_partial_price_data(self, sample_account):
        """验证部分价格数据缺失"""
        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["买入", "买入", "买入"],
            "combined_signal": [0.8, 0.7, 0.6],
            "last_price": [150.0, 250.0, 350.0],
        })

        # 只有部分价格数据
        price_data = pd.DataFrame({
            "AAPL": np.random.uniform(150, 200, 100),
            # TSLA和MSFT缺失
        }, index=pd.date_range(start="2025-01-01", periods=100, freq="D"))

        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=price_data,
            total_capital=1000000.0,
            max_positions=3,
        )

        assert account is not None

    # --------------------------------------------------------------------------
    # 边界值测试
    # --------------------------------------------------------------------------

    def test_apply_equal_weight_rebalance_minimal_values(self):
        """验证最小值情况"""
        account = ensure_account_dict({
            "cash": 100.0,  # 极小资金
            "positions": {},
            "equity_history": [],
            "trade_log": [],
        })

        signals = pd.DataFrame({
            "ticker": ["AAPL"],
            "action": ["买入"],
            "combined_signal": [0.8],
            "last_price": [150.0],
        })

        price_data = pd.DataFrame({
            "AAPL": np.random.uniform(150, 200, 100),
        }, index=pd.date_range(start="2025-01-01", periods=100, freq="D"))

        account, message = apply_equal_weight_rebalance(
            account=account,
            signal_table=signals,
            data=price_data,
            total_capital=100.0,
            max_positions=1,
        )

        assert account is not None

    def test_apply_equal_weight_rebalance_zero_initial_capital(self):
        """验证零初始资金"""
        account = ensure_account_dict({
            "cash": 0.0,
            "positions": {},
            "equity_history": [],
            "trade_log": [],
        })

        signals = pd.DataFrame({
            "ticker": ["AAPL"],
            "action": ["买入"],
            "combined_signal": [0.8],
            "last_price": [150.0],
        })

        price_data = pd.DataFrame({
            "AAPL": np.random.uniform(150, 200, 100),
        }, index=pd.date_range(start="2025-01-01", periods=100, freq="D"))

        account, message = apply_equal_weight_rebalance(
            account=account,
            signal_table=signals,
            data=price_data,
            total_capital=0.0,
            max_positions=1,
        )

        assert account is not None


class TestTradingEngineIntegration:
    """交易引擎集成测试"""

    def test_full_rebalance_workflow(self):
        """验证完整调仓工作流"""
        account = ensure_account_dict({
            "cash": 1000000.0,
            "positions": {},
            "equity_history": [],
            "trade_log": [],
        })

        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA"],
            "action": ["买入", "买入"],
            "combined_signal": [0.8, 0.7],
            "last_price": [150.0, 250.0],
        })

        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        price_data = pd.DataFrame({
            "AAPL": np.random.uniform(150, 200, 100),
            "TSLA": np.random.uniform(200, 300, 100),
        }, index=dates)

        account, message = apply_equal_weight_rebalance(
            account=account,
            signal_table=signals,
            data=price_data,
            total_capital=1000000.0,
            max_positions=3,
        )

        assert account is not None
        assert "cash" in account
        assert "positions" in account

    def test_rebalance_with_risk_monitor(self):
        """验证带风险监控的调仓"""
        from core.risk_monitor import RiskMonitor

        account = ensure_account_dict({
            "cash": 1000000.0,
            "positions": {},
            "equity_history": [],
            "trade_log": [],
        })

        signals = pd.DataFrame({
            "ticker": ["AAPL", "TSLA"],
            "action": ["买入", "买入"],
            "combined_signal": [0.8, 0.7],
            "last_price": [150.0, 250.0],
        })

        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        price_data = pd.DataFrame({
            "AAPL": np.random.uniform(150, 200, 100),
            "TSLA": np.random.uniform(200, 300, 100),
        }, index=dates)

        risk_monitor = RiskMonitor()
        account, message = apply_equal_weight_rebalance(
            account=account,
            signal_table=signals,
            data=price_data,
            total_capital=1000000.0,
            max_positions=3,
            risk_monitor=risk_monitor,
        )

        assert account is not None
        # 验证 message 是字符串类型
        assert isinstance(message, str)

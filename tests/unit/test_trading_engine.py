"""交易引擎模块单元测试"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock

from core.trading_engine import apply_equal_weight_rebalance
from core.broker_simulator import Trade
from core.account import ensure_account_dict


class TestTradingEngine:
    """测试交易引擎模块"""
    
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
        """创建示例信号表（需要action、combined_signal和last_price列）"""
        return pd.DataFrame({
            "ticker": ["AAPL", "TSLA", "MSFT"],
            "action": ["买入", "买入", "买入"],
            "combined_signal": [0.8, 0.7, 0.6],
            "last_price": [150.0, 250.0, 350.0],  # generate_equal_weight_plan需要last_price列
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
    
    def test_apply_equal_weight_rebalance_basic(
        self,
        sample_account,
        sample_signal_table,
        sample_price_data
    ):
        """测试基本调仓功能"""
        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=sample_signal_table,
            data=sample_price_data,
            total_capital=1000000.0,
            max_positions=3,
        )
        
        assert account is not None
        assert "cash" in account
        assert "positions" in account
        assert isinstance(message, str)
    
    def test_apply_equal_weight_rebalance_with_risk_check(
        self,
        sample_account,
        sample_signal_table,
        sample_price_data
    ):
        """测试带风险检查的调仓"""
        from core.risk_monitor import RiskMonitor
        
        risk_monitor = RiskMonitor()
        
        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=sample_signal_table,
            data=sample_price_data,
            total_capital=1000000.0,
            max_positions=3,
            risk_monitor=risk_monitor,
        )
        
        assert account is not None
        assert isinstance(message, str)
    
    def test_apply_equal_weight_rebalance_no_signals(
        self,
        sample_account,
        sample_price_data
    ):
        """测试无信号时的调仓"""
        # 创建空的信号表（列名应该匹配实际代码期望的格式）
        empty_signals = pd.DataFrame(columns=["ticker", "action", "combined_signal", "last_price"])
        
        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=empty_signals,
            data=sample_price_data,
            total_capital=1000000.0,
            max_positions=3,
        )
        
        assert account is not None
        # 实际代码返回的消息是"当前无有效信号，未执行调仓。"
        assert "无有效信号" in message or "未执行调仓" in message or "信号表为空" in message


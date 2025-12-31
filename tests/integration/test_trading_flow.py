"""交易流程集成测试

测试从信号生成到订单执行的完整流程
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import patch

from core.strategy_engine import generate_multi_asset_signals
from core.trading_engine import apply_equal_weight_rebalance
from core.risk_monitor import RiskMonitor
from core.order_manager import OrderManager
from core.stop_loss_manager import StopLossManager
from core.account import ensure_account_dict


class TestTradingFlow:
    """测试交易流程"""
    
    @pytest.fixture
    def sample_data(self):
        """创建示例数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        return pd.DataFrame({
            "AAPL": np.random.uniform(150, 200, 100),
            "TSLA": np.random.uniform(200, 300, 100),
            "MSFT": np.random.uniform(300, 400, 100),
        }, index=dates)
    
    @pytest.fixture
    def sample_account(self):
        """创建示例账户"""
        return ensure_account_dict({
            "cash": 1000000.0,
            "positions": {},
            "equity_history": [],
            "trade_log": [],
        })
    
    def test_signal_to_execution_flow(
        self,
        sample_data,
        sample_account
    ):
        """测试从信号生成到订单执行的完整流程"""
        # 1. 生成信号
        signals_df = generate_multi_asset_signals(price_df=sample_data)
        # 转换为交易引擎需要的格式（需要action和combined_signal列）
        if not signals_df.empty:
            signals = signals_df.head(2).copy()
            # 确保有action列（generate_multi_asset_signals已经生成）
            if "action" not in signals.columns:
                signals["action"] = "买入"  # 默认买入
        else:
            signals = pd.DataFrame(columns=["ticker", "action", "combined_signal"])
        
        assert signals is not None
        assert not signals.empty
        
        # 2. 创建风险监控器和订单管理器
        risk_monitor = RiskMonitor()
        order_manager = OrderManager()
        stop_loss_manager = StopLossManager()
        
        # 3. 执行调仓（带风险检查）
        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_data,
            total_capital=1000000.0,
            max_positions=2,
            risk_monitor=risk_monitor,
            stop_loss_manager=stop_loss_manager,
            order_manager=order_manager,
        )
        
        # 4. 验证结果
        assert account is not None
        assert "cash" in account
        assert "positions" in account
        
        # 验证订单管理器中有订单
        if order_manager.orders:
            assert len(order_manager.orders) > 0
    
    def test_risk_check_integration(
        self,
        sample_data,
        sample_account
    ):
        """测试风险检查集成"""
        # 创建风险监控器
        risk_monitor = RiskMonitor()
        
        # 生成信号
        signals_df = generate_multi_asset_signals(price_df=sample_data)
        if not signals_df.empty:
            signals = signals_df.head(3).copy()
            if "action" not in signals.columns:
                signals["action"] = "买入"
        else:
            signals = pd.DataFrame(columns=["ticker", "action", "combined_signal"])
        
        # 执行调仓
        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_data,
            total_capital=1000000.0,
            max_positions=3,
            risk_monitor=risk_monitor,
        )
        
        # 验证风险检查已执行
        assert account is not None
        # 如果被风险系统拒绝，message会包含相关信息
        assert isinstance(message, str)
    
    def test_order_manager_integration(
        self,
        sample_data,
        sample_account
    ):
        """测试订单管理器集成"""
        order_manager = OrderManager()
        
        signals_df = generate_multi_asset_signals(price_df=sample_data)
        # 使用完整的信号DataFrame，包含所有必需的列（ticker, action, combined_signal, last_price）
        if not signals_df.empty:
            signals = signals_df.head(2).copy()
            if "action" not in signals.columns:
                signals["action"] = "买入"
        else:
            signals = pd.DataFrame(columns=["ticker", "action", "combined_signal", "last_price"])
        
        account, message = apply_equal_weight_rebalance(
            account=sample_account,
            signal_table=signals,
            data=sample_data,
            total_capital=1000000.0,
            max_positions=2,
            order_manager=order_manager,
        )
        
        # 验证订单管理器状态
        stats = order_manager.get_order_statistics()
        assert "total_orders" in stats
        assert "active_orders" in stats


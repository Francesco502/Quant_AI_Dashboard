"""止损止盈管理器测试"""

import pytest
from core.stop_loss_manager import StopLossManager
from core.broker_simulator import Trade


class TestStopLossManager:
    """测试止损止盈管理器"""
    
    @pytest.fixture
    def stop_loss_manager(self):
        """创建止损止盈管理器实例"""
        return StopLossManager()
    
    @pytest.fixture
    def portfolio(self):
        """创建测试账户"""
        return {
            "initial_capital": 1_000_000.0,
            "cash": 850_000.0,
            "positions": {
                "AAPL": 100
            }
        }
    
    def test_set_stop_loss_percentage(self, stop_loss_manager):
        """测试设置百分比止损"""
        stop_loss_manager.set_stop_loss(
            symbol="AAPL",
            entry_price=150.0,
            stop_type="percentage",
            stop_percentage=0.05
        )
        
        assert "AAPL" in stop_loss_manager.stop_loss_rules
        rule = stop_loss_manager.stop_loss_rules["AAPL"]
        assert rule.stop_type == "percentage"
        assert rule.stop_percentage == 0.05
        assert rule.stop_price == 150.0 * 0.95  # 5%止损
    
    def test_set_stop_loss_fixed(self, stop_loss_manager):
        """测试设置固定止损"""
        stop_loss_manager.set_stop_loss(
            symbol="AAPL",
            entry_price=150.0,
            stop_type="fixed",
            stop_price=140.0
        )
        
        assert "AAPL" in stop_loss_manager.stop_loss_rules
        rule = stop_loss_manager.stop_loss_rules["AAPL"]
        assert rule.stop_type == "fixed"
        assert rule.stop_price == 140.0
    
    def test_set_take_profit(self, stop_loss_manager):
        """测试设置止盈"""
        stop_loss_manager.set_take_profit(
            symbol="AAPL",
            entry_price=150.0,
            take_profit_type="percentage",
            take_profit_percentage=0.1
        )
        
        assert "AAPL" in stop_loss_manager.take_profit_rules
        rule = stop_loss_manager.take_profit_rules["AAPL"]
        assert rule.take_profit_type == "percentage"
        assert rule.take_profit_percentage == 0.1
        assert rule.take_profit_price == 150.0 * 1.1  # 10%止盈
    
    def test_check_and_execute_stop_loss(self, stop_loss_manager, portfolio):
        """测试触发止损"""
        # 设置止损
        stop_loss_manager.set_stop_loss(
            symbol="AAPL",
            entry_price=150.0,
            stop_type="percentage",
            stop_percentage=0.05
        )
        
        # 价格跌破止损价
        current_prices = {"AAPL": 140.0}  # 低于止损价142.5
        
        trades = stop_loss_manager.check_and_execute(
            current_prices=current_prices,
            portfolio=portfolio
        )
        
        # 应该触发止损
        assert len(trades) > 0
        assert trades[0].ticker == "AAPL"
        assert trades[0].side == "SELL"
        assert trades[0].shares == 100
    
    def test_check_and_execute_take_profit(self, stop_loss_manager, portfolio):
        """测试触发止盈"""
        # 设置止盈
        stop_loss_manager.set_take_profit(
            symbol="AAPL",
            entry_price=150.0,
            take_profit_type="percentage",
            take_profit_percentage=0.1
        )
        
        # 价格涨破止盈价
        current_prices = {"AAPL": 165.0}  # 高于止盈价165.0
        
        trades = stop_loss_manager.check_and_execute(
            current_prices=current_prices,
            portfolio=portfolio
        )
        
        # 应该触发止盈
        assert len(trades) > 0
        assert trades[0].ticker == "AAPL"
        assert trades[0].side == "SELL"
        assert trades[0].shares == 100
    
    def test_remove_stop_loss(self, stop_loss_manager):
        """测试移除止损规则"""
        stop_loss_manager.set_stop_loss(
            symbol="AAPL",
            entry_price=150.0,
            stop_type="percentage",
            stop_percentage=0.05
        )
        
        assert "AAPL" in stop_loss_manager.stop_loss_rules
        
        stop_loss_manager.remove_stop_loss("AAPL")
        
        assert "AAPL" not in stop_loss_manager.stop_loss_rules
    
    def test_get_active_rules(self, stop_loss_manager):
        """测试获取活跃规则"""
        stop_loss_manager.set_stop_loss(
            symbol="AAPL",
            entry_price=150.0,
            stop_type="percentage",
            stop_percentage=0.05
        )
        stop_loss_manager.set_take_profit(
            symbol="AAPL",
            entry_price=150.0,
            take_profit_type="percentage",
            take_profit_percentage=0.1
        )
        
        rules = stop_loss_manager.get_active_rules()
        
        assert "stop_loss" in rules
        assert "take_profit" in rules
        assert "AAPL" in rules["stop_loss"]
        assert "AAPL" in rules["take_profit"]


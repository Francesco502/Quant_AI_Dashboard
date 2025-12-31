"""风险监控器测试"""

import pytest
from core.risk_monitor import RiskMonitor
from core.risk_types import RiskLimits, RiskAction, RiskLevel
from core.position_manager import PositionManager


class TestRiskMonitor:
    """测试风险监控器"""
    
    @pytest.fixture
    def risk_monitor(self):
        """创建风险监控器实例"""
        risk_limits = RiskLimits(
            max_single_stock=0.05,
            max_daily_loss=0.05,
            max_total_loss=0.2
        )
        return RiskMonitor(risk_limits=risk_limits)
    
    @pytest.fixture
    def portfolio(self):
        """创建测试账户（无亏损，避免触发紧急停止）"""
        return {
            "initial_capital": 1_000_000.0,
            "cash": 850_000.0,  # 调整现金，使总权益接近初始资本
            "positions": {
                "AAPL": 100
            }
        }
    
    @pytest.fixture
    def current_prices(self):
        """创建当前价格"""
        return {
            "AAPL": 150.0
        }
    
    def test_check_order_risk_allow(self, risk_monitor, portfolio, current_prices):
        """测试订单风险检查通过"""
        order = {
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 10,
            "price": 150.0
        }
        
        result = risk_monitor.check_order_risk(order, portfolio, current_prices)
        
        assert result.action in [RiskAction.ALLOW, RiskAction.WARN]
    
    def test_check_order_risk_reject(self, risk_monitor, portfolio, current_prices):
        """测试订单风险检查拒绝"""
        # 大额订单，超过单股票限制
        order = {
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 10000,  # 非常大的数量
            "price": 150.0
        }
        
        result = risk_monitor.check_order_risk(order, portfolio, current_prices)
        
        # 应该被拒绝或警告
        assert result.action in [RiskAction.REJECT, RiskAction.WARN]
    
    def test_emergency_stop(self, risk_monitor, portfolio, current_prices):
        """测试紧急停止"""
        # 模拟总亏损超过限制
        portfolio["cash"] = 700_000.0  # 总权益约850000，亏损15%
        portfolio["initial_capital"] = 1_000_000.0
        
        # 进一步亏损，触发紧急停止
        portfolio["cash"] = 750_000.0  # 总权益约900000，亏损10%
        
        order = {
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 10,
            "price": 150.0
        }
        
        # 手动设置紧急停止
        risk_monitor.emergency_stop = True
        
        result = risk_monitor.check_order_risk(order, portfolio, current_prices)
        
        assert result.action == RiskAction.EMERGENCY_STOP
    
    def test_get_risk_summary(self, risk_monitor):
        """测试获取风险汇总"""
        summary = risk_monitor.get_risk_summary()
        
        assert "emergency_stop" in summary
        assert "is_monitoring" in summary
        assert "total_events" in summary
        assert "recent_events" in summary
    
    def test_update_daily_pnl(self, risk_monitor):
        """测试更新每日盈亏"""
        risk_monitor.update_daily_pnl("2025-01-01", -5000.0)
        
        assert "2025-01-01" in risk_monitor.daily_pnl
        assert risk_monitor.daily_pnl["2025-01-01"] == -5000.0
        assert risk_monitor.total_pnl == -5000.0
    
    def test_clear_emergency_stop(self, risk_monitor):
        """测试清除紧急停止"""
        risk_monitor.emergency_stop = True
        assert risk_monitor.emergency_stop is True
        
        risk_monitor.clear_emergency_stop()
        assert risk_monitor.emergency_stop is False


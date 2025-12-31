"""风险类型定义测试"""

import pytest
from datetime import datetime

from core.risk_types import (
    RiskLevel,
    RiskAction,
    AlertSeverity,
    RiskLimits,
    RiskCheckResult,
    RiskEvent,
    PositionLimit,
    StopLossRule,
    TakeProfitRule,
)


class TestRiskLevel:
    """测试风险等级枚举"""
    
    def test_risk_level_values(self):
        """测试风险等级值"""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestRiskAction:
    """测试风险动作枚举"""
    
    def test_risk_action_values(self):
        """测试风险动作值"""
        assert RiskAction.ALLOW.value == "allow"
        assert RiskAction.WARN.value == "warn"
        assert RiskAction.REJECT.value == "reject"
        assert RiskAction.EMERGENCY_STOP.value == "emergency_stop"


class TestRiskLimits:
    """测试风险限制"""
    
    def test_default_risk_limits(self):
        """测试默认风险限制"""
        limits = RiskLimits()
        assert limits.max_position_size == 0.1
        assert limits.max_single_stock == 0.05
        assert limits.max_daily_loss == 0.05
        assert limits.max_total_loss == 0.2
    
    def test_custom_risk_limits(self):
        """测试自定义风险限制"""
        limits = RiskLimits(
            max_position_size=0.15,
            max_single_stock=0.08,
            max_daily_loss=0.03,
            max_total_loss=0.15
        )
        assert limits.max_position_size == 0.15
        assert limits.max_single_stock == 0.08
        assert limits.max_daily_loss == 0.03
        assert limits.max_total_loss == 0.15


class TestRiskCheckResult:
    """测试风险检查结果"""
    
    def test_risk_check_result_creation(self):
        """测试风险检查结果创建"""
        result = RiskCheckResult(
            action=RiskAction.ALLOW,
            risk_level=RiskLevel.LOW,
            message="通过"
        )
        assert result.action == RiskAction.ALLOW
        assert result.risk_level == RiskLevel.LOW
        assert result.message == "通过"
        assert result.violations == []
        assert result.metadata == {}
    
    def test_risk_check_result_with_violations(self):
        """测试带违规项的风险检查结果"""
        result = RiskCheckResult(
            action=RiskAction.REJECT,
            risk_level=RiskLevel.HIGH,
            message="拒绝",
            violations=["仓位超限", "集中度超限"]
        )
        assert len(result.violations) == 2
        assert "仓位超限" in result.violations


class TestRiskEvent:
    """测试风险事件"""
    
    def test_risk_event_creation(self):
        """测试风险事件创建"""
        event = RiskEvent(
            event_id="test_001",
            timestamp=datetime.now(),
            event_type="order_risk_check",
            severity=AlertSeverity.WARNING,
            message="测试事件",
            symbol="AAPL"
        )
        assert event.event_id == "test_001"
        assert event.event_type == "order_risk_check"
        assert event.severity == AlertSeverity.WARNING
        assert event.symbol == "AAPL"


class TestPositionLimit:
    """测试仓位限制"""
    
    def test_position_limit_creation(self):
        """测试仓位限制创建"""
        limit = PositionLimit(
            symbol="AAPL",
            max_position=10000,
            max_weight=0.05
        )
        assert limit.symbol == "AAPL"
        assert limit.max_position == 10000
        assert limit.max_weight == 0.05


class TestStopLossRule:
    """测试止损规则"""
    
    def test_stop_loss_rule_creation(self):
        """测试止损规则创建"""
        rule = StopLossRule(
            symbol="AAPL",
            stop_type="percentage",
            stop_percentage=0.05,
            entry_price=150.0
        )
        assert rule.symbol == "AAPL"
        assert rule.stop_type == "percentage"
        assert rule.stop_percentage == 0.05
        assert rule.entry_price == 150.0


class TestTakeProfitRule:
    """测试止盈规则"""
    
    def test_take_profit_rule_creation(self):
        """测试止盈规则创建"""
        rule = TakeProfitRule(
            symbol="AAPL",
            take_profit_type="percentage",
            take_profit_percentage=0.1,
            entry_price=150.0
        )
        assert rule.symbol == "AAPL"
        assert rule.take_profit_type == "percentage"
        assert rule.take_profit_percentage == 0.1
        assert rule.entry_price == 150.0


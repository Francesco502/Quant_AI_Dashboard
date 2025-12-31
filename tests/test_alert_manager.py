"""告警管理器测试"""

import pytest
from datetime import datetime, timedelta
from core.monitoring import (
    AlertManager,
    AlertRule,
    AlertSeverity,
    ComparisonOperator,
    MetricsCollector,
    DashboardChannel,
)


class TestAlertManager:
    """测试告警管理器"""
    
    @pytest.fixture
    def alert_manager(self):
        """创建告警管理器实例"""
        metrics_collector = MetricsCollector()
        return AlertManager(metrics_collector=metrics_collector)
    
    def test_add_alert_rule(self, alert_manager):
        """测试添加告警规则"""
        rule_id = alert_manager.add_alert_rule(
            name="CPU告警",
            metric_name="cpu_usage",
            threshold=80.0,
            comparison=ComparisonOperator.GT,
            severity=AlertSeverity.WARNING,
        )
        
        assert rule_id in alert_manager.alert_rules
        rule = alert_manager.alert_rules[rule_id]
        assert rule.name == "CPU告警"
        assert rule.metric_name == "cpu_usage"
        assert rule.threshold == 80.0
    
    def test_alert_rule_should_trigger(self, alert_manager):
        """测试告警规则触发判断"""
        rule_id = alert_manager.add_alert_rule(
            name="CPU告警",
            metric_name="cpu_usage",
            threshold=80.0,
            comparison=ComparisonOperator.GT,
            severity=AlertSeverity.WARNING,
        )
        
        rule = alert_manager.alert_rules[rule_id]
        
        # 应该触发（85 > 80）
        assert rule.should_trigger(85.0) is True
        
        # 不应该触发（75 < 80）
        assert rule.should_trigger(75.0) is False
    
    def test_check_and_trigger(self, alert_manager):
        """测试检查并触发告警"""
        # 添加告警规则
        rule_id = alert_manager.add_alert_rule(
            name="CPU告警",
            metric_name="cpu_usage",
            threshold=80.0,
            comparison=ComparisonOperator.GT,
            severity=AlertSeverity.WARNING,
        )
        
        # 检查指标（CPU使用率85%，应该触发）
        metrics = {"cpu_usage": 85.0}
        alert_manager.check_and_trigger(metrics)
        
        # 应该生成告警
        assert len(alert_manager.alert_history) > 0
    
    def test_alert_cooldown(self, alert_manager):
        """测试告警冷却期"""
        rule_id = alert_manager.add_alert_rule(
            name="CPU告警",
            metric_name="cpu_usage",
            threshold=80.0,
            comparison=ComparisonOperator.GT,
            severity=AlertSeverity.WARNING,
            cooldown_minutes=10,
        )
        
        rule = alert_manager.alert_rules[rule_id]
        
        # 第一次触发
        assert rule.should_trigger(85.0) is True
        rule.last_triggered = datetime.now()
        
        # 立即再次检查（应该在冷却期内）
        assert rule.should_trigger(85.0) is False
        
        # 等待冷却期后（模拟）
        rule.last_triggered = datetime.now() - timedelta(minutes=11)
        assert rule.should_trigger(85.0) is True
    
    def test_get_alert_history(self, alert_manager):
        """测试获取告警历史"""
        # 添加规则并触发告警
        alert_manager.add_alert_rule(
            name="CPU告警",
            metric_name="cpu_usage",
            threshold=80.0,
            comparison=ComparisonOperator.GT,
            severity=AlertSeverity.WARNING,
        )
        
        alert_manager.check_and_trigger({"cpu_usage": 85.0})
        
        history = alert_manager.get_alert_history(limit=10)
        
        assert len(history) > 0
        assert history[0]["rule_name"] == "CPU告警"
    
    def test_get_alert_statistics(self, alert_manager):
        """测试获取告警统计"""
        # 添加多个规则并触发告警
        alert_manager.add_alert_rule(
            name="CPU告警",
            metric_name="cpu_usage",
            threshold=80.0,
            comparison=ComparisonOperator.GT,
            severity=AlertSeverity.WARNING,
        )
        
        alert_manager.check_and_trigger({"cpu_usage": 85.0})
        
        stats = alert_manager.get_alert_statistics()
        
        assert "total_alerts" in stats
        assert "by_severity" in stats
        assert "active_rules" in stats


class TestAlertChannels:
    """测试告警渠道"""
    
    def test_dashboard_channel(self):
        """测试Dashboard渠道"""
        from core.monitoring import DashboardChannel, Alert, AlertSeverity
        
        channel = DashboardChannel()
        
        alert = Alert(
            alert_id="TEST",
            rule_id="RULE_001",
            rule_name="测试规则",
            severity=AlertSeverity.WARNING,
            message="测试消息",
            metric_name="cpu_usage",
            metric_value=85.0,
            threshold=80.0,
            timestamp=datetime.now(),
        )
        
        # 应该成功发送（记录到日志）
        result = channel.send(alert)
        assert result is True


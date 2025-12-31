"""系统监控器测试"""

import pytest
from datetime import datetime, timedelta
from core.monitoring import (
    SystemMonitor,
    MetricsCollector,
    HealthChecker,
    HealthStatus,
)


class TestMetricsCollector:
    """测试指标收集器"""
    
    @pytest.fixture
    def collector(self):
        """创建指标收集器实例"""
        return MetricsCollector()
    
    def test_record_metrics(self, collector):
        """测试记录指标"""
        metrics = {
            "cpu_usage": 50.0,
            "memory_usage": 60.0,
        }
        collector.record(metrics)
        
        assert "cpu_usage" in collector.metrics
        assert "memory_usage" in collector.metrics
    
    def test_get_latest_metric(self, collector):
        """测试获取最新指标"""
        collector.record({"cpu_usage": 50.0})
        collector.record({"cpu_usage": 60.0})
        
        latest = collector.get_latest_metric("cpu_usage")
        assert latest == 60.0
    
    def test_get_metric_statistics(self, collector):
        """测试获取指标统计"""
        # 记录多个数据点
        for i in range(10):
            collector.record({"cpu_usage": 50.0 + i})
        
        stats = collector.get_metric_statistics("cpu_usage", window_minutes=60)
        
        assert "mean" in stats
        assert "min" in stats
        assert "max" in stats
        assert stats["count"] == 10


class TestHealthChecker:
    """测试健康检查器"""
    
    @pytest.fixture
    def health_checker(self):
        """创建健康检查器实例"""
        return HealthChecker()
    
    def test_check_database(self, health_checker):
        """测试数据库检查"""
        check = health_checker.check_database()
        
        assert check.name == "database"
        assert isinstance(check.status, HealthStatus)
    
    def test_check_data_source(self, health_checker):
        """测试数据源检查"""
        check = health_checker.check_data_source(["AkShare", "yfinance"])
        
        assert check.name == "data_source"
        assert isinstance(check.status, HealthStatus)
    
    def test_check_all(self, health_checker):
        """测试所有健康检查"""
        checks = health_checker.check_all()
        
        assert "database" in checks
        assert "data_source" in checks
        assert "disk_space" in checks
        assert "memory" in checks
    
    def test_get_overall_status(self, health_checker):
        """测试获取整体状态"""
        checks = health_checker.check_all()
        overall = health_checker.get_overall_status(checks)
        
        assert isinstance(overall, HealthStatus)


class TestSystemMonitor:
    """测试系统监控器"""
    
    @pytest.fixture
    def system_monitor(self):
        """创建系统监控器实例"""
        return SystemMonitor(collection_interval=1.0)
    
    def test_collect_metrics(self, system_monitor):
        """测试收集指标"""
        metrics = system_monitor.collect_metrics()
        
        # 应该包含业务指标
        assert "data_update_latency" in metrics
        assert "order_execution_latency" in metrics
        assert "api_response_time" in metrics
    
    def test_check_health(self, system_monitor):
        """测试健康检查"""
        health_status = system_monitor.check_health()
        
        assert "status" in health_status
        assert "checks" in health_status
    
    def test_record_data_update(self, system_monitor):
        """测试记录数据更新"""
        system_monitor.record_data_update()
        
        latency = system_monitor._get_data_update_latency()
        assert latency >= 0
    
    def test_record_order_execution(self, system_monitor):
        """测试记录订单执行"""
        system_monitor.record_order_execution(0.5)
        
        latency = system_monitor._get_order_execution_latency()
        assert latency == 0.5
    
    def test_get_system_summary(self, system_monitor):
        """测试获取系统汇总"""
        summary = system_monitor.get_system_summary()
        
        assert "monitoring" in summary
        assert "metrics" in summary
        assert "health" in summary
        assert "business_metrics" in summary


"""系统监控器

职责：
- 收集系统指标（CPU、内存、磁盘、网络等）
- 执行健康检查
- 监控业务指标（数据更新延迟、订单执行延迟等）
"""

from __future__ import annotations

import time
import threading
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta

from .metrics import MetricsCollector
from .health_checker import HealthChecker, HealthStatus

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


logger = logging.getLogger(__name__)


class SystemMonitor:
    """系统监控器"""

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        health_checker: Optional[HealthChecker] = None,
        collection_interval: float = 60.0,
    ):
        """
        初始化系统监控器

        Args:
            metrics_collector: 指标收集器（可选）
            health_checker: 健康检查器（可选）
            collection_interval: 指标收集间隔（秒）
        """
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.health_checker = health_checker or HealthChecker()
        self.collection_interval = collection_interval
        
        # 监控状态
        self.is_monitoring = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # 业务指标追踪
        self.data_update_times: List[datetime] = []
        self.order_execution_times: List[float] = []
        self.api_response_times: List[float] = []
        
        # 回调函数
        self.on_metrics_updated: Optional[Callable[[Dict], None]] = None
        self.on_health_check: Optional[Callable[[Dict], None]] = None
        
        logger.info("系统监控器初始化完成")

    def collect_metrics(self) -> Dict[str, float]:
        """
        收集系统指标

        Returns:
            指标字典
        """
        metrics = {}
        
        if PSUTIL_AVAILABLE:
            try:
                # CPU使用率
                metrics["cpu_usage"] = psutil.cpu_percent(interval=0.1)
                
                # 内存使用
                memory = psutil.virtual_memory()
                metrics["memory_usage"] = memory.percent
                metrics["memory_available_mb"] = memory.available / (1024 * 1024)
                
                # 磁盘使用
                disk = psutil.disk_usage("/")
                metrics["disk_usage"] = disk.used / disk.total * 100
                metrics["disk_free_gb"] = disk.free / (1024 * 1024 * 1024)
                
                # 网络IO
                net_io = psutil.net_io_counters()
                metrics["network_bytes_sent"] = net_io.bytes_sent
                metrics["network_bytes_recv"] = net_io.bytes_recv
            except Exception as e:
                logger.error(f"收集系统指标失败: {e}")
        
        # 业务指标
        metrics["data_update_latency"] = self._get_data_update_latency()
        metrics["order_execution_latency"] = self._get_order_execution_latency()
        metrics["api_response_time"] = self._get_api_response_time()
        
        # 记录指标
        self.metrics_collector.record(metrics)
        
        # 触发回调
        if self.on_metrics_updated:
            try:
                self.on_metrics_updated(metrics)
            except Exception as e:
                logger.error(f"指标更新回调异常: {e}")
        
        return metrics

    def check_health(self, data_sources: Optional[List[str]] = None) -> Dict:
        """
        健康检查

        Args:
            data_sources: 数据源列表（可选）

        Returns:
            健康状态字典
        """
        checks = self.health_checker.check_all(data_sources)
        overall_status = self.health_checker.get_overall_status(checks)
        
        health_status = {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "details": check.details,
                }
                for name, check in checks.items()
            }
        }
        
        # 触发回调
        if self.on_health_check:
            try:
                self.on_health_check(health_status)
            except Exception as e:
                logger.error(f"健康检查回调异常: {e}")
        
        return health_status

    def start_monitoring(self, data_sources: Optional[List[str]] = None):
        """
        启动监控

        Args:
            data_sources: 数据源列表（可选）
        """
        if self.is_monitoring:
            logger.warning("监控已在运行中")
            return
        
        self.is_monitoring = True
        self.stop_event.clear()
        
        def monitoring_loop():
            logger.info("系统监控线程启动")
            while not self.stop_event.is_set():
                try:
                    # 收集指标
                    self.collect_metrics()
                    
                    # 健康检查（每5次指标收集执行一次）
                    if len(self.metrics_collector.metrics.get("cpu_usage", [])) % 5 == 0:
                        self.check_health(data_sources)
                    
                    # 等待下次收集
                    self.stop_event.wait(self.collection_interval)
                except Exception as e:
                    logger.error(f"监控循环异常: {e}", exc_info=True)
                    time.sleep(self.collection_interval)
            
            logger.info("系统监控线程停止")
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info(f"系统监控已启动，收集间隔={self.collection_interval}秒")

    def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self.stop_event.set()
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5.0)
        
        logger.info("系统监控已停止")

    def record_data_update(self):
        """记录数据更新时间"""
        self.data_update_times.append(datetime.now())
        # 只保留最近100次
        if len(self.data_update_times) > 100:
            self.data_update_times = self.data_update_times[-100:]

    def record_order_execution(self, latency: float):
        """记录订单执行延迟"""
        self.order_execution_times.append(latency)
        # 只保留最近1000次
        if len(self.order_execution_times) > 1000:
            self.order_execution_times = self.order_execution_times[-1000:]

    def record_api_response(self, response_time: float):
        """记录API响应时间"""
        self.api_response_times.append(response_time)
        # 只保留最近1000次
        if len(self.api_response_times) > 1000:
            self.api_response_times = self.api_response_times[-1000:]

    def _get_data_update_latency(self) -> float:
        """获取数据更新延迟（秒）"""
        if not self.data_update_times:
            return 0.0
        
        last_update = self.data_update_times[-1]
        latency = (datetime.now() - last_update).total_seconds()
        return latency

    def _get_order_execution_latency(self) -> float:
        """获取订单执行平均延迟（秒）"""
        if not self.order_execution_times:
            return 0.0
        
        return sum(self.order_execution_times) / len(self.order_execution_times)

    def _get_api_response_time(self) -> float:
        """获取API平均响应时间（秒）"""
        if not self.api_response_times:
            return 0.0
        
        return sum(self.api_response_times) / len(self.api_response_times)

    def get_system_summary(self) -> Dict:
        """获取系统汇总信息"""
        latest_metrics = {}
        for metric_name in ["cpu_usage", "memory_usage", "disk_usage"]:
            value = self.metrics_collector.get_latest_metric(metric_name)
            if value is not None:
                latest_metrics[metric_name] = value
        
        health_status = self.check_health()
        
        return {
            "monitoring": {
                "is_monitoring": self.is_monitoring,
                "collection_interval": self.collection_interval,
            },
            "metrics": latest_metrics,
            "health": health_status,
            "business_metrics": {
                "data_update_latency": self._get_data_update_latency(),
                "order_execution_latency": self._get_order_execution_latency(),
                "api_response_time": self._get_api_response_time(),
            },
        }


"""系统监控器

职责：
- 收集系统指标（CPU、内存、磁盘、网络等）
- 执行健康检查
- 监控业务指标（数据更新延迟、订单执行延迟等）
- 支持2GB低配服务器优化
"""

from __future__ import annotations

import time
import threading
import logging
import os
from copy import deepcopy
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import deque

from .metrics import MetricsCollector
from .health_checker import HealthChecker, HealthStatus
from .config import SystemMonitorConfig, get_monitoring_config

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """系统指标数据类"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    process_cpu_usage: float
    process_memory_mb: float


@dataclass
class MonitoringStatus:
    """监控状态"""
    is_monitoring: bool
    uptime_seconds: float
    metrics_collected: int
    health_checks_performed: int
    last_metric_time: Optional[datetime]
    last_health_check_time: Optional[datetime]


class SystemMonitor:
    """系统监控器（支持2GB低配服务器）"""

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        health_checker: Optional[HealthChecker] = None,
        config: Optional[SystemMonitorConfig] = None,
    ):
        """
        初始化系统监控器

        Args:
            metrics_collector: 指标收集器（可选）
            health_checker: 健康检查器（可选）
            config: 监控配置（可选）
        """
        self.metrics_collector = metrics_collector or MetricsCollector(max_history=500)
        self.health_checker = health_checker or HealthChecker()
        self.config = config or get_monitoring_config().system

        # 监控状态
        self.is_monitoring = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # 性能计时器
        self.start_time = datetime.now()
        self.metrics_collected_count = 0
        self.health_checks_count = 0
        self.last_health_check_time: Optional[datetime] = None
        self.last_health_status: Optional[Dict[str, Any]] = None

        # 业务指标追踪（使用 deque 限制内存）
        self.data_update_times: deque = deque(maxlen=100)
        self.order_execution_times: deque = deque(maxlen=1000)
        self.api_response_times: deque = deque(maxlen=1000)

        # 回调函数
        self.on_metrics_updated: Optional[Callable[[Dict], None]] = None
        self.on_health_check: Optional[Callable[[Dict], None]] = None
        self.on_memory_pressure: Optional[Callable[[float], None]] = None

        logger.info("系统监控器初始化完成（适配2GB低配服务器）")

    def collect_metrics(self) -> Dict[str, Any]:
        """
        收集系统指标（轻量级版本）

        Returns:
            指标字典
        """
        metrics = {}

        if PSUTIL_AVAILABLE:
            try:
                # CPU使用率（0.1秒间隔）
                metrics["cpu_usage"] = psutil.cpu_percent(interval=0.1)

                # 内存使用
                memory = psutil.virtual_memory()
                metrics["memory_usage"] = memory.percent
                metrics["memory_available_mb"] = round(memory.available / (1024 * 1024), 2)
                metrics["memory_used_mb"] = round(memory.used / (1024 * 1024), 2)

                # 磁盘使用
                disk = psutil.disk_usage("/")
                metrics["disk_usage"] = round(disk.used / disk.total * 100, 2)
                metrics["disk_free_gb"] = round(disk.free / (1024 * 1024 * 1024), 2)

                # 网络IO
                net_io = psutil.net_io_counters()
                metrics["network_bytes_sent"] = net_io.bytes_sent
                metrics["network_bytes_recv"] = net_io.bytes_recv

                # 进程资源使用
                process = psutil.Process(os.getpid())
                with process.oneshot():
                    metrics["process_cpu_usage"] = process.cpu_percent(interval=0.01)
                    metrics["process_memory_mb"] = round(process.memory_info().rss / (1024 * 1024), 2)

                # 磁盘IO（可选，增加少量开销）
                try:
                    disk_io = psutil.disk_io_counters()
                    metrics["disk_read_bytes"] = disk_io.read_bytes
                    metrics["disk_write_bytes"] = disk_io.write_bytes
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"收集系统指标失败: {e}")
        else:
            # 降级方案：使用 os.times()
            try:
                times = os.times()
                metrics["cpu_usage"] = times.user + times.system
                metrics["memory_usage"] = 0.0
                metrics["memory_available_mb"] = 0.0
                metrics["memory_used_mb"] = 0.0
                metrics["disk_usage"] = 0.0
                metrics["disk_free_gb"] = 0.0
                metrics["process_cpu_usage"] = 0.0
                metrics["process_memory_mb"] = 0.0
            except Exception:
                metrics = {
                    "cpu_usage": 0.0,
                    "memory_usage": 0.0,
                    "memory_available_mb": 0.0,
                    "memory_used_mb": 0.0,
                    "disk_usage": 0.0,
                    "disk_free_gb": 0.0,
                    "process_cpu_usage": 0.0,
                    "process_memory_mb": 0.0,
                }

        # 业务指标
        metrics["data_update_latency"] = self._get_data_update_latency()
        metrics["order_execution_latency"] = self._get_order_execution_latency()
        metrics["api_response_time"] = self._get_api_response_time()

        # 记录指标
        self.metrics_collector.record(metrics)
        self.metrics_collected_count += 1

        # 检查内存压力（2GB服务器优化）
        memory_percent = metrics.get("memory_usage", 0)
        if self.config.is_under_memory_pressure(memory_percent):
            if self.on_memory_pressure:
                try:
                    self.on_memory_pressure(memory_percent)
                except Exception as e:
                    logger.error(f"内存压力回调异常: {e}")

        # 触发回调
        if self.on_metrics_updated:
            try:
                self.on_metrics_updated(metrics)
            except Exception as e:
                logger.error(f"指标更新回调异常: {e}")

        return metrics

    def collect_detailed_metrics(self) -> Dict[str, Any]:
        """
        收集详细系统指标（用于监控页面）

        Returns:
            详细指标字典
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "system": {},
            "process": {},
            "storage": {},
            "network": {},
            "business": {},
        }

        if PSUTIL_AVAILABLE:
            # 系统CPU信息
            try:
                cpu_times = psutil.cpu_times_percent(interval=0.1)
                result["system"]["cpu_times"] = {
                    "user": cpu_times.user,
                    "system": cpu_times.system,
                    "idle": cpu_times.idle,
                    "iowait": getattr(cpu_times, 'iowait', None),
                }
            except Exception:
                pass

            # 内存详细信息
            memory = psutil.virtual_memory()
            result["system"]["memory"] = {
                "total_mb": round(memory.total / (1024 * 1024), 2),
                "available_mb": round(memory.available / (1024 * 1024), 2),
                "used_mb": round(memory.used / (1024 * 1024), 2),
                "percent": memory.percent,
                "active_mb": round(getattr(memory, 'active', 0) / (1024 * 1024), 2) if hasattr(memory, 'active') else None,
                "inactive_mb": round(getattr(memory, 'inactive', 0) / (1024 * 1024), 2) if hasattr(memory, 'inactive') else None,
            }

            # 磁盘详细信息
            disk = psutil.disk_usage("/")
            result["storage"]["disk"] = {
                "total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
                "used_gb": round(disk.used / (1024 * 1024 * 1024), 2),
                "free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                "percent": round(disk.used / disk.total * 100, 2),
            }

            # 分区信息
            try:
                partitions = psutil.disk_partitions()
                result["storage"]["partitions"] = [
                    {
                        "device": p.device,
                        "mountpoint": p.mountpoint,
                        "fstype": p.fstype,
                    }
                    for p in partitions
                ]
            except Exception:
                pass

            # 网络详细信息
            net_io = psutil.net_io_counters()
            result["network"]["io"] = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
            }

            # 网络接口
            try:
                net_if_addrs = psutil.net_if_addrs()
                result["network"]["interfaces"] = list(net_if_addrs.keys())
            except Exception:
                pass

            # 进程详细信息
            process = psutil.Process(os.getpid())
            with process.oneshot():
                mem_info = process.memory_info()
                result["process"]["memory"] = {
                    "rss_mb": round(mem_info.rss / (1024 * 1024), 2),
                    "vms_mb": round(mem_info.vms / (1024 * 1024), 2),
                }
                result["process"]["cpu"] = {
                    "percent": process.cpu_percent(interval=0.05),
                    "num_threads": process.num_threads(),
                }
                try:
                    result["process"]["open_files"] = len(process.open_files())
                except Exception:
                    result["process"]["open_files"] = 0
                try:
                    result["process"]["connections"] = len(process.connections())
                except Exception:
                    result["process"]["connections"] = 0

        # 业务指标
        result["business"] = {
            "data_update_latency": round(self._get_data_update_latency(), 2),
            "data_update_latency_minutes": round(self._get_data_update_latency() / 60, 2),
            "order_execution_latency": round(self._get_order_execution_latency(), 3),
            "api_response_time": round(self._get_api_response_time(), 3),
            "api_response_time_seconds": round(self._get_api_response_time(), 3),
        }

        return result

    def check_health(
        self,
        data_sources: Optional[List[str]] = None,
        *,
        force: bool = False,
        max_age_seconds: Optional[float] = None,
    ) -> Dict:
        """
        健康检查（带缓存避免频繁检查）

        Args:
            data_sources: 数据源列表（可选）

        Returns:
            健康状态字典
        """
        effective_max_age = (
            float(max_age_seconds)
            if max_age_seconds is not None
            else max(float(self.config.collection_interval) * 2.0, 30.0)
        )
        if (
            not force
            and self.last_health_status is not None
            and self.last_health_check_time is not None
            and (datetime.now() - self.last_health_check_time).total_seconds() <= effective_max_age
        ):
            return deepcopy(self.last_health_status)

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

        self.health_checks_count += 1
        self.last_health_check_time = datetime.now()
        self.last_health_status = deepcopy(health_status)

        # 触发回调
        if self.on_health_check:
            try:
                self.on_health_check(health_status)
            except Exception as e:
                logger.error(f"健康检查回调异常: {e}")

        return health_status

    def get_monitoring_status(self) -> MonitoringStatus:
        """获取监控状态"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        last_metric_time = None
        last_health_time = self.last_health_check_time

        if self.metrics_collector.last_collection_time:
            last_metric_time = self.metrics_collector.last_collection_time

        return MonitoringStatus(
            is_monitoring=self.is_monitoring,
            uptime_seconds=round(uptime, 2),
            metrics_collected=self.metrics_collected_count,
            health_checks_performed=self.health_checks_count,
            last_metric_time=last_metric_time,
            last_health_check_time=last_health_time,
        )

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
        self.start_time = datetime.now()
        self.stop_event.clear()

        def monitoring_loop():
            logger.info("系统监控线程启动（2GB服务器优化模式）")
            last_health_check = time.time()

            while not self.stop_event.is_set():
                try:
                    # 收集指标（高频）
                    self.collect_metrics()

                    # 健康检查（低频，每5次收集执行一次）
                    current_time = time.time()
                    if current_time - last_health_check >= self.config.collection_interval * 5:
                        self.check_health(data_sources, force=True)
                        last_health_check = current_time

                    # 等待下次收集
                    self.stop_event.wait(self.config.collection_interval)
                except Exception as e:
                    logger.error(f"监控循环异常: {e}", exc_info=True)
                    time.sleep(self.config.collection_interval)

            logger.info("系统监控线程停止")

        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info(f"系统监控已启动，收集间隔={self.config.collection_interval}秒")

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

    def record_order_execution(self, latency: float):
        """记录订单执行延迟"""
        self.order_execution_times.append(latency)

    def record_api_response(self, response_time: float):
        """记录API响应时间"""
        self.api_response_times.append(response_time)

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

        health_status = self.check_health(max_age_seconds=max(float(self.config.collection_interval) * 4.0, 60.0))

        return {
            "monitoring": {
                "is_monitoring": self.is_monitoring,
                "collection_interval": self.config.collection_interval,
                "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
                "metrics_collected": self.metrics_collected_count,
                "health_checks": self.health_checks_count,
            },
            "metrics": latest_metrics,
            "health": health_status,
            "business_metrics": {
                "data_update_latency": round(self._get_data_update_latency(), 2),
                "data_update_latency_minutes": round(self._get_data_update_latency() / 60, 2),
                "order_execution_latency": round(self._get_order_execution_latency(), 3),
                "api_response_time": round(self._get_api_response_time(), 3),
            },
        }

    def get_metrics_history(self, metric_name: str, minutes: int = 60) -> List[Dict]:
        """
        获取指标历史数据

        Args:
            metric_name: 指标名称
            minutes: 时间范围（分钟）

        Returns:
            指标历史数据列表
        """
        points = self.metrics_collector.get_metric(metric_name)

        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        filtered = [p for p in points if p.timestamp >= cutoff_time]

        return [
            {
                "timestamp": p.timestamp.isoformat(),
                "value": p.value,
            }
            for p in filtered
        ]

    def get_metric_statistics(self, metric_name: str, window_minutes: int = 60) -> Dict:
        """
        获取指标统计信息

        Args:
            metric_name: 指标名称
            window_minutes: 时间窗口（分钟）

        Returns:
            统计信息字典
        """
        return self.metrics_collector.get_metric_statistics(metric_name, window_minutes)

    def get_all_metric_statistics(self, window_minutes: int = 60) -> Dict:
        """
        获取所有指标的统计信息

        Args:
            window_minutes: 时间窗口（分钟）

        Returns:
            所有指标的统计信息
        """
        metrics = {}
        for metric_name in ["cpu_usage", "memory_usage", "disk_usage", "process_memory_mb"]:
            stats = self.get_metric_statistics(metric_name, window_minutes)
            if stats:
                metrics[metric_name] = stats
        return metrics


# 全局监控器实例
_global_monitor: Optional[SystemMonitor] = None


def get_system_monitor() -> SystemMonitor:
    """获取全局系统监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = SystemMonitor()
    return _global_monitor


def restart_system_monitor() -> SystemMonitor:
    """重启全局系统监控器"""
    global _global_monitor
    if _global_monitor is not None:
        _global_monitor.stop_monitoring()
    _global_monitor = SystemMonitor()
    _global_monitor.start_monitoring()
    return _global_monitor

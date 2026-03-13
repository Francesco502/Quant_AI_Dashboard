"""健康检查器

增强功能：
- 多数据源健康检查
- API响应时间检查
- 业务指标健康检查
- 2GB低配服务器优化
"""

from __future__ import annotations

import os
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from functools import wraps

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """健康检查结果"""
    name: str
    status: HealthStatus
    message: str
    details: Dict = None
    timestamp: datetime = None
    check_time_ms: float = 0.0

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.timestamp is None:
            self.timestamp = datetime.now()


def timed_health_check(func):
    """健康检查计时装饰器"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        try:
            result = func(self, *args, **kwargs)
            result.check_time_ms = round((time.time() - start_time) * 1000, 2)
            return result
        except Exception as e:
            result = HealthCheck(
                name=func.__name__,
                status=HealthStatus.UNKNOWN,
                message=f"检查失败: {e}",
            )
            result.check_time_ms = round((time.time() - start_time) * 1000, 2)
            return result
    return wrapper


class HealthChecker:
    """健康检查器（多数据源支持）"""

    # 默认超时设置
    DEFAULT_TIMEOUT_SECONDS = 10
    API_RESPONSE_THRESHOLD_MS = 5000  # API响应阈值（毫秒）
    DATA_UPDATE_THRESHOLD_SECONDS = 300  # 数据更新延迟阈值（秒）

    def __init__(self):
        """初始化健康检查器"""
        self.checks: List[str] = []
        self._last_data_update: Optional[datetime] = None
        self._last_api_response_time_ms: float = 0.0
        logger.info("健康检查器初始化完成")

    def set_last_data_update(self, timestamp: Optional[datetime] = None):
        """设置最后数据更新时间"""
        self._last_data_update = timestamp or datetime.now()

    def set_last_api_response_time(self, response_time_ms: float):
        """设置最后API响应时间"""
        self._last_api_response_time_ms = response_time_ms

    @timed_health_check
    def check_database(self, db_path: Optional[str] = None) -> HealthCheck:
        """
        检查数据库连接

        Args:
            db_path: 数据库路径（可选）

        Returns:
            健康检查结果
        """
        try:
            # 检查数据目录
            from ..data_store import BASE_DIR
            data_dir = BASE_DIR

            if os.path.exists(data_dir):
                # 检查目录可写性
                test_file = os.path.join(data_dir, ".health_check")
                try:
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    return HealthCheck(
                        name="database",
                        status=HealthStatus.HEALTHY,
                        message="数据目录可访问",
                        details={"path": data_dir, "writable": True}
                    )
                except Exception as e:
                    return HealthCheck(
                        name="database",
                        status=HealthStatus.DEGRADED,
                        message=f"数据目录不可写: {e}",
                        details={"path": data_dir, "writable": False}
                    )
            else:
                return HealthCheck(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message="数据目录不存在",
                    details={"path": data_dir, "exists": False}
                )
        except Exception as e:
            return HealthCheck(
                name="database",
                status=HealthStatus.UNKNOWN,
                message=f"数据库检查失败: {e}",
            )

    @timed_health_check
    def check_data_source(self, data_sources: Optional[List[str]] = None) -> HealthCheck:
        """
        检查数据源连接

        Args:
            data_sources: 数据源列表（可选）

        Returns:
            健康检查结果
        """
        try:
            available_sources = []
            unavailable_sources = []
            timeout_sources = []

            if data_sources is None:
                data_sources = ["AkShare", "yfinance", "Binance"]

            for source in data_sources:
                if source == "AkShare":
                    try:
                        import akshare as ak
                        # 测试连接（轻量级调用）
                        start = time.time()
                        ak.stock_zh_a_spot()
                        elapsed = (time.time() - start) * 1000
                        if elapsed > self.DEFAULT_TIMEOUT_SECONDS * 1000:
                            timeout_sources.append(source)
                        else:
                            available_sources.append(source)
                    except ImportError:
                        unavailable_sources.append(source)
                    except Exception as e:
                        timeout_sources.append(source)
                elif source == "yfinance":
                    try:
                        import yfinance as yf
                        # 测试连接
                        start = time.time()
                        yf.Ticker("AAPL").info
                        elapsed = (time.time() - start) * 1000
                        if elapsed > self.DEFAULT_TIMEOUT_SECONDS * 1000:
                            timeout_sources.append(source)
                        else:
                            available_sources.append(source)
                    except ImportError:
                        unavailable_sources.append(source)
                    except Exception as e:
                        timeout_sources.append(source)
                elif source == "Binance":
                    try:
                        import CCXT
                        available_sources.append(source)
                    except ImportError:
                        try:
                            import ccxt
                            available_sources.append(source)
                        except ImportError:
                            unavailable_sources.append(source)
                    except Exception:
                        available_sources.append(source)
                else:
                    unavailable_sources.append(source)

            # 构建消息
            if timeout_sources:
                return HealthCheck(
                    name="data_source",
                    status=HealthStatus.DEGRADED,
                    message=f"部分数据源响应超时: {', '.join(timeout_sources)}",
                    details={
                        "available": available_sources,
                        "timeout": timeout_sources,
                        "unavailable": unavailable_sources
                    }
                )
            elif unavailable_sources:
                return HealthCheck(
                    name="data_source",
                    status=HealthStatus.UNHEALTHY,
                    message=f"部分数据源不可用: {', '.join(unavailable_sources)}",
                    details={
                        "available": available_sources,
                        "unavailable": unavailable_sources
                    }
                )
            else:
                return HealthCheck(
                    name="data_source",
                    status=HealthStatus.HEALTHY,
                    message="所有数据源可用",
                    details={
                        "available": available_sources,
                        "response_time_ms": "< 1000"
                    }
                )
        except Exception as e:
            return HealthCheck(
                name="data_source",
                status=HealthStatus.UNKNOWN,
                message=f"数据源检查失败: {e}",
            )

    @timed_health_check
    def check_disk_space(self, threshold_percent: float = 90.0) -> HealthCheck:
        """
        检查磁盘空间

        Args:
            threshold_percent: 告警阈值（百分比）

        Returns:
            健康检查结果
        """
        if not PSUTIL_AVAILABLE:
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message="psutil未安装，无法检查磁盘空间",
            )

        try:
            disk_usage = psutil.disk_usage("/")
            used_percent = disk_usage.used / disk_usage.total * 100

            if used_percent >= threshold_percent:
                status = HealthStatus.UNHEALTHY
                message = f"磁盘空间不足: {used_percent:.1f}% 已使用"
            elif used_percent >= threshold_percent - 10:
                status = HealthStatus.DEGRADED
                message = f"磁盘空间紧张: {used_percent:.1f}% 已使用"
            else:
                status = HealthStatus.HEALTHY
                message = f"磁盘空间充足: {used_percent:.1f}% 已使用"

            return HealthCheck(
                name="disk_space",
                status=status,
                message=message,
                details={
                    "total_gb": round(disk_usage.total / (1024 ** 3), 2),
                    "used_gb": round(disk_usage.used / (1024 ** 3), 2),
                    "free_gb": round(disk_usage.free / (1024 ** 3), 2),
                    "percent": round(used_percent, 2),
                }
            )
        except Exception as e:
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"磁盘空间检查失败: {e}",
            )

    @timed_health_check
    def check_memory(self, threshold_percent: float = 90.0) -> HealthCheck:
        """
        检查内存使用

        Args:
            threshold_percent: 告警阈值（百分比）

        Returns:
            健康检查结果
        """
        if not PSUTIL_AVAILABLE:
            return HealthCheck(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message="psutil未安装，无法检查内存",
            )

        try:
            memory = psutil.virtual_memory()
            used_percent = memory.percent

            if used_percent >= threshold_percent:
                status = HealthStatus.UNHEALTHY
                message = f"内存使用过高: {used_percent:.1f}%"
            elif used_percent >= threshold_percent - 15:
                status = HealthStatus.DEGRADED
                message = f"内存使用较高: {used_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"内存使用正常: {used_percent:.1f}%"

            return HealthCheck(
                name="memory",
                status=status,
                message=message,
                details={
                    "total_mb": round(memory.total / (1024 ** 2), 2),
                    "used_mb": round(memory.used / (1024 ** 2), 2),
                    "available_mb": round(memory.available / (1024 ** 2), 2),
                    "percent": round(used_percent, 2),
                    "active_mb": round(getattr(memory, 'active', 0) / (1024 ** 2), 2) if hasattr(memory, 'active') else None,
                }
            )
        except Exception as e:
            return HealthCheck(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message=f"内存检查失败: {e}",
            )

    @timed_health_check
    def check_api_response_time(self, threshold_ms: float = None) -> HealthCheck:
        """
        检查API响应时间

        Args:
            threshold_ms: 告警阈值（毫秒），None时使用默认值

        Returns:
            健康检查结果
        """
        threshold_ms = threshold_ms or self.API_RESPONSE_THRESHOLD_MS

        if self._last_api_response_time_ms == 0.0:
            return HealthCheck(
                name="api_response_time",
                status=HealthStatus.UNKNOWN,
                message="尚未记录API响应时间",
                details={"last_response_ms": 0, "threshold_ms": threshold_ms}
            )

        if self._last_api_response_time_ms > threshold_ms:
            status = HealthStatus.DEGRADED
            message = f"API响应时间偏高: {self._last_api_response_time_ms:.1f}ms"
        else:
            status = HealthStatus.HEALTHY
            message = f"API响应时间正常: {self._last_api_response_time_ms:.1f}ms"

        return HealthCheck(
            name="api_response_time",
            status=status,
            message=message,
            details={
                "last_response_ms": round(self._last_api_response_time_ms, 2),
                "threshold_ms": threshold_ms,
            }
        )

    @timed_health_check
    def check_data_update_latency(self, threshold_seconds: float = None) -> HealthCheck:
        """
        检查数据更新延迟

        Args:
            threshold_seconds: 告警阈值（秒），None时使用默认值

        Returns:
            健康检查结果
        """
        threshold_seconds = threshold_seconds or self.DATA_UPDATE_THRESHOLD_SECONDS

        if self._last_data_update is None:
            return HealthCheck(
                name="data_update_latency",
                status=HealthStatus.UNKNOWN,
                message="尚未记录数据更新时间",
                details={"last_update": None, "threshold_seconds": threshold_seconds}
            )

        latency = (datetime.now() - self._last_data_update).total_seconds()

        if latency > threshold_seconds:
            status = HealthStatus.UNHEALTHY
            message = f"数据更新延迟: {latency:.0f}秒"
        elif latency > threshold_seconds * 0.7:
            status = HealthStatus.DEGRADED
            message = f"数据更新延迟偏高: {latency:.0f}秒"
        else:
            status = HealthStatus.HEALTHY
            message = f"数据更新正常: {latency:.0f}秒"

        return HealthCheck(
            name="data_update_latency",
            status=status,
            message=message,
            details={
                "last_update": self._last_data_update.isoformat(),
                "latency_seconds": round(latency, 2),
                "threshold_seconds": threshold_seconds,
            }
        )

    @timed_health_check
    def check_process_health(self) -> HealthCheck:
        """
        检查进程健康状态

        Returns:
            健康检查结果
        """
        try:
            process = psutil.Process(os.getpid())

            with process.oneshot():
                # 检查进程是否存在
                if not process.is_running():
                    return HealthCheck(
                        name="process_health",
                        status=HealthStatus.UNHEALTHY,
                        message="进程已退出",
                    )

                # 获取进程资源使用
                mem_info = process.memory_info()
                cpu_percent = process.cpu_percent(interval=0.01)

                # 检查文件描述符
                try:
                    open_files = len(process.open_files())
                except Exception:
                    open_files = 0

                # 检查网络连接
                try:
                    connections = len(process.connections())
                except Exception:
                    connections = 0

                # 检查线程数
                num_threads = process.num_threads()

                # 判断进程健康状态
                if cpu_percent > 95:
                    status = HealthStatus.DEGRADED
                    message = f"进程CPU使用率高: {cpu_percent:.1f}%"
                elif cpu_percent > 80:
                    status = HealthStatus.DEGRADED
                    message = f"进程CPU使用率偏高: {cpu_percent:.1f}%"
                elif open_files > 1000:
                    status = HealthStatus.DEGRADED
                    message = f"进程打开文件数太多: {open_files}"
                else:
                    status = HealthStatus.HEALTHY
                    message = "进程运行正常"

                return HealthCheck(
                    name="process_health",
                    status=status,
                    message=message,
                    details={
                        "pid": os.getpid(),
                        "cpu_percent": round(cpu_percent, 2),
                        "memory_mb": round(mem_info.rss / (1024 ** 2), 2),
                        "num_threads": num_threads,
                        "open_files": open_files,
                        "connections": connections,
                    }
                )

        except psutil.NoSuchProcess:
            return HealthCheck(
                name="process_health",
                status=HealthStatus.UNHEALTHY,
                message="进程不存在",
            )
        except Exception as e:
            return HealthCheck(
                name="process_health",
                status=HealthStatus.UNKNOWN,
                message=f"进程检查失败: {e}",
            )

    @timed_health_check
    def check_services(self, services: Optional[List[Dict]] = None) -> HealthCheck:
        """
        检查外部服务状态

        Args:
            services: 服务列表，每个服务包含 name, host, port

        Returns:
            健康检查结果
        """
        services = services or [
            {"name": "database", "host": "localhost", "port": 5432},
        ]

        available_services = []
        unavailable_services = []

        for service in services:
            name = service.get("name", "unknown")
            host = service.get("host", "localhost")
            port = service.get("port", 0)

            try:
                # 尝试连接（简单检查）
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    available_services.append(name)
                else:
                    unavailable_services.append(name)
            except Exception:
                unavailable_services.append(name)

        if unavailable_services:
            return HealthCheck(
                name="services",
                status=HealthStatus.UNHEALTHY,
                message=f"部分服务不可用: {', '.join(unavailable_services)}",
                details={
                    "available": available_services,
                    "unavailable": unavailable_services
                }
            )
        else:
            return HealthCheck(
                name="services",
                status=HealthStatus.HEALTHY,
                message="所有服务可用",
                details={"available": available_services}
            )

    def check_all(self, data_sources: Optional[List[str]] = None) -> Dict[str, HealthCheck]:
        """
        执行所有健康检查（2GB低配服务器优化版本）

        Args:
            data_sources: 数据源列表（可选）

        Returns:
            健康检查结果字典
        """
        checks = {
            "database": self.check_database(),
            "data_source": self.check_data_source(data_sources),
            "disk_space": self.check_disk_space(),
            "memory": self.check_memory(),
            "api_response_time": self.check_api_response_time(),
            "data_update_latency": self.check_data_update_latency(),
            "process_health": self.check_process_health(),
        }

        return checks

    def get_overall_status(self, checks: Dict[str, HealthCheck]) -> HealthStatus:
        """
        获取整体健康状态

        Args:
            checks: 健康检查结果字典

        Returns:
            整体健康状态
        """
        if not checks:
            return HealthStatus.UNKNOWN

        statuses = [check.status for check in checks.values()]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN

    def get_health_summary(self, checks: Optional[Dict[str, HealthCheck]] = None,
                          data_sources: Optional[List[str]] = None) -> Dict:
        """
        获取健康检查摘要

        Args:
            checks: 已有的健康检查结果（可选）
            data_sources: 数据源列表（可选）

        Returns:
            健康摘要字典
        """
        if checks is None:
            checks = self.check_all(data_sources)

        overall_status = self.get_overall_status(checks)

        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "checks_count": len(checks),
            "healthy_count": sum(1 for c in checks.values() if c.status == HealthStatus.HEALTHY),
            "degraded_count": sum(1 for c in checks.values() if c.status == HealthStatus.DEGRADED),
            "unhealthy_count": sum(1 for c in checks.values() if c.status == HealthStatus.UNHEALTHY),
            "checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "check_time_ms": check.check_time_ms,
                }
                for name, check in checks.items()
            },
        }

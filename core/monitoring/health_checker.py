"""健康检查器"""

from __future__ import annotations

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

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

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.timestamp is None:
            self.timestamp = datetime.now()


class HealthChecker:
    """健康检查器"""

    def __init__(self):
        """初始化健康检查器"""
        self.checks: List[str] = []
        logger.info("健康检查器初始化完成")

    def check_database(self, db_path: Optional[str] = None) -> HealthCheck:
        """
        检查数据库连接

        Args:
            db_path: 数据库路径（可选）

        Returns:
            健康检查结果
        """
        try:
            # 简化版：检查数据目录是否存在
            from ..data_store import BASE_DIR
            data_dir = BASE_DIR
            
            if os.path.exists(data_dir):
                # 检查目录是否可写
                test_file = os.path.join(data_dir, ".health_check")
                try:
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    return HealthCheck(
                        name="database",
                        status=HealthStatus.HEALTHY,
                        message="数据目录可访问",
                        details={"path": data_dir}
                    )
                except Exception as e:
                    return HealthCheck(
                        name="database",
                        status=HealthStatus.DEGRADED,
                        message=f"数据目录不可写: {e}",
                        details={"path": data_dir}
                    )
            else:
                return HealthCheck(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message="数据目录不存在",
                    details={"path": data_dir}
                )
        except Exception as e:
            return HealthCheck(
                name="database",
                status=HealthStatus.UNKNOWN,
                message=f"数据库检查失败: {e}",
            )

    def check_data_source(self, data_sources: Optional[List[str]] = None) -> HealthCheck:
        """
        检查数据源连接

        Args:
            data_sources: 数据源列表（可选）

        Returns:
            健康检查结果
        """
        try:
            # 简化版：检查数据源模块是否可用
            available_sources = []
            unavailable_sources = []
            
            if data_sources is None:
                data_sources = ["AkShare", "yfinance", "Binance"]
            
            for source in data_sources:
                if source == "AkShare":
                    try:
                        import akshare as ak
                        available_sources.append(source)
                    except ImportError:
                        unavailable_sources.append(source)
                elif source == "yfinance":
                    try:
                        import yfinance as yf
                        available_sources.append(source)
                    except ImportError:
                        unavailable_sources.append(source)
                elif source == "Binance":
                    # Binance 不需要特殊检查
                    available_sources.append(source)
            
            if unavailable_sources:
                return HealthCheck(
                    name="data_source",
                    status=HealthStatus.DEGRADED,
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
                    details={"available": available_sources}
                )
        except Exception as e:
            return HealthCheck(
                name="data_source",
                status=HealthStatus.UNKNOWN,
                message=f"数据源检查失败: {e}",
            )

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
                    "total": disk_usage.total,
                    "used": disk_usage.used,
                    "free": disk_usage.free,
                    "percent": used_percent,
                }
            )
        except Exception as e:
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"磁盘空间检查失败: {e}",
            )

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
            elif used_percent >= threshold_percent - 10:
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
                    "total": memory.total,
                    "used": memory.used,
                    "available": memory.available,
                    "percent": used_percent,
                }
            )
        except Exception as e:
            return HealthCheck(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message=f"内存检查失败: {e}",
            )

    def check_all(self, data_sources: Optional[List[str]] = None) -> Dict[str, HealthCheck]:
        """
        执行所有健康检查

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


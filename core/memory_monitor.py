"""内存监控模块

职责:
- 监控系统内存使用情况
- 内存使用率超过阈值时发出告警
- 定期清理缓存释放内存

优化说明:
- 2026-03-03: 新增内存监控，适配 2GB 内存服务器环境
"""

from __future__ import annotations

import os
import gc
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MemoryStatus:
    """内存状态数据类"""
    used_mb: float        # 已使用内存 (MB)
    available_mb: float   # 可用内存 (MB)
    total_mb: float       # 总内存 (MB)
    percent: float        # 使用率百分比
    is_warning: bool      # 是否达到警告阈值
    is_critical: bool     # 是否达到严重阈值


class MemoryMonitor:
    """内存监控器"""

    # 警告阈值 (百分比)
    WARNING_THRESHOLD = 0.70    # 70% 警告
    CRITICAL_THRESHOLD = 0.85   # 85% 严重警告

    # 2GB 内存环境的默认限制
    DEFAULT_MEMORY_LIMIT_MB = 1800  # 预留 200MB 给系统

    def __init__(self, memory_limit_mb: Optional[float] = None):
        """
        初始化内存监控器

        Args:
            memory_limit_mb: 内存限制 (MB)，None 时自动检测
        """
        self.memory_limit_mb = memory_limit_mb or self.DEFAULT_MEMORY_LIMIT_MB
        self._last_gc_run = 0
        logger.info(f"内存监控器初始化完成，限制：{self.memory_limit_mb}MB")

    def get_memory_status(self) -> MemoryStatus:
        """获取当前内存状态"""
        try:
            import resource
            # Unix/Linux/MacOS
            usage = resource.getrusage(resource.RUSAGE_SELF)
            used_mb = usage.ru_maxrss / 1024  # KB to MB (MacOS returns bytes)
            if os.name == 'nt':
                # Windows returns bytes, convert to MB
                used_mb = usage.ru_maxrss / (1024 * 1024)
        except ImportError:
            # 降级方案：使用 psutil
            try:
                import psutil
                process = psutil.Process(os.getpid())
                used_mb = process.memory_info().rss / (1024 * 1024)
            except ImportError:
                # 最简降级：返回估算值
                logger.warning("无法获取精确内存使用，使用估算值")
                used_mb = 0

        available_mb = self.memory_limit_mb - used_mb
        percent = used_mb / self.memory_limit_mb if self.memory_limit_mb > 0 else 0

        return MemoryStatus(
            used_mb=round(used_mb, 2),
            available_mb=round(available_mb, 2),
            total_mb=self.memory_limit_mb,
            percent=round(percent * 100, 2),
            is_warning=percent >= self.WARNING_THRESHOLD,
            is_critical=percent >= self.CRITICAL_THRESHOLD,
        )

    def check_memory(self) -> Tuple[bool, str]:
        """
        检查内存状态

        Returns:
            (是否健康，消息)
        """
        status = self.get_memory_status()

        if status.is_critical:
            msg = f"内存严重不足：{status.used_mb}MB/{status.total_mb}MB ({status.percent}%)"
            logger.warning(msg)
            return False, msg
        elif status.is_warning:
            msg = f"内存使用率偏高：{status.used_mb}MB/{status.total_mb}MB ({status.percent}%)"
            logger.info(msg)
            return True, msg
        else:
            msg = f"内存使用正常：{status.used_mb}MB/{status.total_mb}MB ({status.percent}%)"
            logger.debug(msg)
            return True, msg

    def force_gc(self) -> int:
        """
        强制垃圾回收

        Returns:
            回收的对象数量
        """
        before = gc.get_count()
        collected = gc.collect()
        after = gc.get_count()

        freed = (before[0] + before[1] + before[2]) - (after[0] + after[1] + after[2])
        logger.info(f"垃圾回收：释放 {freed} 个对象")

        return collected

    def cleanup_caches(self) -> Dict[str, int]:
        """
        清理各种缓存

        Returns:
            清理统计
        """
        stats = {
            'gc_collected': 0,
            'dict_caches_cleared': 0,
        }

        # 1. 垃圾回收
        stats['gc_collected'] = self.force_gc()

        # 2. 清理字典缓存（如果有全局缓存实例）
        try:
            from core.multi_level_cache import get_cache
            cache = get_cache()
            if hasattr(cache, 'clear'):
                cache.clear()
                stats['dict_caches_cleared'] += 1
                logger.info("已清理多级缓存")
        except Exception as e:
            logger.debug(f"清理缓存时出错：{e}")

        return stats

    def get_memory_report(self) -> Dict:
        """生成内存报告"""
        status = self.get_memory_status()
        return {
            'used_mb': status.used_mb,
            'available_mb': status.available_mb,
            'total_mb': status.total_mb,
            'percent': status.percent,
            'status': 'critical' if status.is_critical else ('warning' if status.is_warning else 'ok'),
            'timestamp': __import__('datetime').datetime.now().isoformat(),
        }


# 全局内存监控器实例
_memory_monitor: Optional[MemoryMonitor] = None


def get_memory_monitor(limit_mb: Optional[float] = None) -> MemoryMonitor:
    """获取内存监控器实例（单例模式）"""
    global _memory_monitor
    if _memory_monitor is None:
        _memory_monitor = MemoryMonitor(memory_limit_mb=limit_mb)
    return _memory_monitor


def check_and_cleanup() -> Dict:
    """检查内存并在需要时清理"""
    monitor = get_memory_monitor()
    is_healthy, msg = monitor.check_memory()

    result = {
        'message': msg,
        'is_healthy': is_healthy,
        'cleanup_performed': False,
    }

    if not is_healthy:
        stats = monitor.cleanup_caches()
        result['cleanup_performed'] = True
        result['cleanup_stats'] = stats

        # 再次检查
        is_healthy, msg = monitor.check_memory()
        result['message_after_cleanup'] = msg
        result['is_healthy_after_cleanup'] = is_healthy

    return result

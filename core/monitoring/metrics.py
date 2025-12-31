"""指标收集器"""

from __future__ import annotations

import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """指标收集器"""

    def __init__(self, max_history: int = 1000):
        """
        初始化指标收集器

        Args:
            max_history: 最大历史记录数
        """
        self.max_history = max_history
        self.metrics: Dict[str, deque] = {}
        self.last_collection_time: Optional[datetime] = None
        
        logger.info("指标收集器初始化完成")

    def record(self, metrics: Dict[str, float], tags: Optional[Dict[str, str]] = None):
        """
        记录指标

        Args:
            metrics: 指标字典 {metric_name: value}
            tags: 标签字典（可选）
        """
        timestamp = datetime.now()
        tags = tags or {}
        
        for metric_name, value in metrics.items():
            if metric_name not in self.metrics:
                self.metrics[metric_name] = deque(maxlen=self.max_history)
            
            point = MetricPoint(timestamp=timestamp, value=value, tags=tags)
            self.metrics[metric_name].append(point)
        
        self.last_collection_time = timestamp

    def get_metric(self, metric_name: str, start_time: Optional[datetime] = None) -> List[MetricPoint]:
        """
        获取指标数据

        Args:
            metric_name: 指标名称
            start_time: 起始时间（可选）

        Returns:
            指标数据点列表
        """
        if metric_name not in self.metrics:
            return []
        
        points = list(self.metrics[metric_name])
        
        if start_time:
            points = [p for p in points if p.timestamp >= start_time]
        
        return points

    def get_latest_metric(self, metric_name: str) -> Optional[float]:
        """获取最新指标值"""
        if metric_name not in self.metrics or not self.metrics[metric_name]:
            return None
        
        return self.metrics[metric_name][-1].value

    def get_metric_statistics(self, metric_name: str, window_minutes: int = 60) -> Dict:
        """
        获取指标统计信息

        Args:
            metric_name: 指标名称
            window_minutes: 时间窗口（分钟）

        Returns:
            统计信息字典
        """
        if metric_name not in self.metrics:
            return {}
        
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        points = [p for p in self.metrics[metric_name] if p.timestamp >= cutoff_time]
        
        if not points:
            return {}
        
        values = [p.value for p in points]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "latest": values[-1],
        }

    def get_all_metrics(self) -> Dict[str, List[MetricPoint]]:
        """获取所有指标"""
        return {name: list(points) for name, points in self.metrics.items()}

    def clear_metrics(self, metric_name: Optional[str] = None):
        """清空指标"""
        if metric_name:
            if metric_name in self.metrics:
                self.metrics[metric_name].clear()
        else:
            self.metrics.clear()


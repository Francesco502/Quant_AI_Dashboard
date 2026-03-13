"""简单调度模块（阶段 4）

职责：
- 基于 schedule 库注册数据更新与模拟交易任务；
- 由 core.daemon 调用，在单独进程中长期运行。

说明：
- 需要先安装依赖：pip install schedule
"""

from __future__ import annotations

from typing import Callable, Dict, Any

try:
    import schedule  # type: ignore[import]

    SCHEDULE_AVAILABLE = True
except ImportError:
    schedule = None  # type: ignore[assignment]
    SCHEDULE_AVAILABLE = False


def setup_data_update_job(config: Dict[str, Any], job: Callable[[], None]) -> None:
    """根据配置注册数据更新任务

    支持两种形式：
    - 每日固定时间：{"enabled": true, "time": "23:30"}
    - 固定间隔分钟：{"enabled": true, "interval_minutes": 60}
    """
    if not SCHEDULE_AVAILABLE:
        return
    if not config.get("enabled", False):
        return

    time_str = config.get("time")
    interval_min = config.get("interval_minutes")

    if time_str:
        schedule.every().day.at(time_str).do(job)
    elif interval_min:
        schedule.every(int(interval_min)).minutes.do(job)


def setup_trading_job(config: Dict[str, Any], job: Callable[[], None]) -> None:
    """根据配置注册模拟交易任务，规则同数据更新"""
    if not SCHEDULE_AVAILABLE:
        return
    if not config.get("enabled", False):
        return

    time_str = config.get("time")
    interval_min = config.get("interval_minutes")

    if time_str:
        schedule.every().day.at(time_str).do(job)
    elif interval_min:
        schedule.every(int(interval_min)).minutes.do(job)


def setup_training_job(config: Dict[str, Any], job: Callable[[], None]) -> None:
    """根据配置注册模型训练任务
    
    支持两种形式：
    - 每日固定时间：{"enabled": true, "time": "16:00"}
    - 固定间隔小时：{"enabled": true, "interval_hours": 24}
    """
    if not SCHEDULE_AVAILABLE:
        return
    if not config.get("enabled", False):
        return

    time_str = config.get("time")
    interval_hours = config.get("interval_hours")

    if time_str:
        schedule.every().day.at(time_str).do(job)
    elif interval_hours:
        schedule.every(int(interval_hours)).hours.do(job)


def setup_daily_analysis_job(config: Dict[str, Any], job: Callable[[], None]) -> None:
    """根据配置注册每日智能分析任务

    支持两种形式：
    - 每日固定时间：{\"enabled\": true, \"time\": \"18:00\"}
    - 固定间隔小时：{\"enabled\": true, \"interval_hours\": 24}
    """
    if not SCHEDULE_AVAILABLE:
        return
    if not config.get("enabled", False):
        return

    time_str = config.get("time")
    interval_hours = config.get("interval_hours")

    if time_str:
        schedule.every().day.at(time_str).do(job)
    elif interval_hours:
        schedule.every(int(interval_hours)).hours.do(job)


def run_forever() -> None:
    """在 daemon 中调用：进入阻塞循环，按计划执行任务"""
    if not SCHEDULE_AVAILABLE:
        raise RuntimeError("schedule 库未安装，请先运行: pip install schedule")

    import time

    while True:
        schedule.run_pending()
        time.sleep(1)



"""每日分析配置读取

优先从环境变量读取必要配置，其次可以在后续接入用户态配置文件。
"""

from __future__ import annotations

import os
from typing import List


def get_bias_threshold() -> float:
    """获取乖离率阈值（用于“严禁追高”提示）"""
    try:
        return float(os.getenv("BIAS_THRESHOLD", "5.0"))
    except ValueError:
        return 5.0


def get_default_tickers() -> List[str]:
    """获取默认分析的自选股列表"""
    raw = os.getenv("DAILY_ANALYSIS_TICKERS", "")
    if not raw:
        # 若未显式配置，则退化为一个演示标的，避免空列表
        return ["600519"]
    return [t.strip() for t in raw.split(",") if t.strip()]


def get_default_market() -> str:
    """默认市场（cn/hk/us）"""
    return os.getenv("DAILY_ANALYSIS_MARKET", "cn").lower()


def get_news_max_age_days() -> int:
    """新闻/舆情最大时效（天），默认 3 天"""
    try:
        return int(os.getenv("NEWS_MAX_AGE_DAYS", "3"))
    except ValueError:
        return 3


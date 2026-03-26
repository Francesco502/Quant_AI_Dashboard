"""
外部数据源模块

提供宏观经济数据、行业轮动数据、市场情绪数据和资金流向数据的接入。
"""

from .economic import EconomicDataLoader
from .industry import IndustryDataLoader
from .sentiment import SentimentDataLoader
from .flow import FlowDataLoader
from .loader import ExternalDataLoader

__all__ = [
    "EconomicDataLoader",
    "IndustryDataLoader",
    "SentimentDataLoader",
    "FlowDataLoader",
    "ExternalDataLoader",
]

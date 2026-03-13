"""选股引擎

职责：
- 执行选股策略
- 策略组合评分
- 结果排序
"""

from __future__ import annotations

import pandas as pd
from typing import Dict, List, Optional
import logging

from core.scanner.strategies import (
    StockSelector,
    get_stock_selector,
    get_strategy,
    BaseStrategy,
    StrategySignal,
)


logger = logging.getLogger(__name__)


class ScannerEngine:
    """扫描器引擎"""

    def __init__(self, strategy_selector: Optional[StockSelector] = None):
        self.selector = strategy_selector or get_stock_selector()

    def scan(
        self,
        price_df: pd.DataFrame,
        strategy_weights: Optional[Dict[str, float]] = None,
        top_n: int = 20,
        min_score: int = 60,
    ) -> pd.DataFrame:
        """
        全市场扫描

        Args:
            price_df: 价格数据
            strategy_weights: 策略权重（None为默认权重）
            top_n: 返回前N个
            min_score: 最低评分阈值

        Returns:
            选股结果DataFrame
        """
        # 选股
        df = self.selector.select_stocks(price_df, top_n=top_n * 2)

        if df.empty:
            return pd.DataFrame()

        # 应用策略权重
        if strategy_weights:
            for ticker, weight in strategy_weights.items():
                mask = df["ticker"] == ticker
                df.loc[mask, "score"] = df.loc[mask, "score"] * weight

        # 过滤最低评分
        df = df[df["score"] >= min_score]

        # 排序
        df = df.sort_values("score", ascending=False).head(top_n)

        return df

    def scan_single_strategy(
        self,
        price_df: pd.DataFrame,
        strategy_name: str,
        top_n: int = 20,
        min_score: int = 60,
    ) -> pd.DataFrame:
        """
        按单个策略扫描

        Args:
            price_df: 价格数据
            strategy_name: 策略名称
            top_n: 返回前N个

        Returns:
            选股结果DataFrame
        """
        try:
            strategy = get_strategy(strategy_name)
            selector = StockSelector(strategies=[strategy])
            df = selector.select_stocks(price_df, top_n=top_n, min_score=min_score)
        except Exception as e:
            logger.warning("Single strategy scan fallback for %s: %s", strategy_name, e)
            df = self.scan(price_df, top_n=top_n, min_score=min_score)

        if df.empty:
            return pd.DataFrame()

        return df.sort_values("score", ascending=False).head(top_n)


def get_scanner_engine() -> ScannerEngine:
    """获取扫描器引擎"""
    return ScannerEngine()

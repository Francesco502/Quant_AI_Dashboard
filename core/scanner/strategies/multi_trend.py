"""多头趋势策略

本策略基于均线排列原理：
- 判断标准：MA5 > MA10 > MA20（多头排列）
- 买入信号：多头排列形成或持续
- 卖出信号：空头排列（MA5 < MA10 < MA20）
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List
from dataclasses import dataclass

from core.scanner.strategies import BaseStrategy, StrategySignal


class MultiTrendStrategy(BaseStrategy):
    """多头趋势策略"""

    def __init__(self, weight: float = 1.5):
        """
        初始化多头趋势策略

        Args:
            weight: 策略权重，默认1.5（趋势策略优先级较高）
        """
        super().__init__("多头趋势", weight)

    def name(self) -> str:
        """返回策略名称"""
        return "多头趋势策略"

    def description(self) -> str:
        """返回策略描述"""
        return "多头趋势策略 - 判断MA5 > MA10 > MA20多头排列，持续上涨趋势时产生买入信号"

    def calculate_signal(self, df: pd.DataFrame) -> float:
        """
        计算策略信号评分

        Args:
            df: OHLCV数据，包含open, high, low, close, volume列

        Returns:
            策略评分（0-100），分数越高信号越强
        """
        if len(df) < 30:
            return 50  # 数据不足，中性评分

        close_prices = df['close']

        # 计算均线
        ma5 = close_prices.rolling(window=5).mean()
        ma10 = close_prices.rolling(window=10).mean()
        ma20 = close_prices.rolling(window=20).mean()

        if len(ma5) < 3:
            return 50

        # 获取最近的均线值
        latest_ma5 = ma5.iloc[-1]
        latest_ma10 = ma10.iloc[-1]
        latest_ma20 = ma20.iloc[-1]

        prev_ma5 = ma5.iloc[-2] if len(ma5) > 2 else latest_ma5
        prev_ma10 = ma10.iloc[-2] if len(ma10) > 2 else latest_ma10
        prev_ma20 = ma20.iloc[-2] if len(ma20) > 2 else latest_ma20

        score = 50  # 默认中性评分

        # 多头排列检查（MA5 > MA10 > MA20）
        is_bullish_arrangement = latest_ma5 > latest_ma10 > latest_ma20
        is_bearish_arrangement = latest_ma5 < latest_ma10 < latest_ma20

        # 多头排列
        if is_bullish_arrangement:
            score = 75
            # 多头排列持续性加分
            if prev_ma5 > prev_ma10 > prev_ma20:
                score = min(100, score + 10)
            # 均线开口增大（趋势强劲）
            ma_spread = (latest_ma5 - latest_ma20) / latest_ma20
            if ma_spread > 0.05:
                score = min(100, score + 5)
            # 价格远离均线（可能回调，适度减分）
            latest_close = close_prices.iloc[-1]
            price偏离 = (latest_close - latest_ma5) / latest_ma5
            if price偏离 > 0.03:  # 价格涨幅过大，谨慎
                score = max(0, score - 5)
        # 空头排列
        elif is_bearish_arrangement:
            score = 25
            # 空头排列持续性减分
            if prev_ma5 < prev_ma10 < prev_ma20:
                score = max(0, score - 10)
            # 空头开口增大
            ma_spread = abs(latest_ma5 - latest_ma20) / latest_ma20
            if ma_spread > 0.05:
                score = max(0, score - 5)
        else:
            # 无明显排列
            score = 45
            # 判断趋势转变迹象
            if latest_ma5 > latest_ma10 and prev_ma5 <= prev_ma10:
                # 刚刚转多，信号较弱
                score = 55
            elif latest_ma5 < latest_ma10 and prev_ma5 >= prev_ma10:
                # 刚刚转空，信号较弱
                score = 45

        # 均线方向确认
        ma5_up = latest_ma5 > prev_ma5 > prev_ma20
        ma5_down = latest_ma5 < prev_ma5 < prev_ma20

        if ma5_up:
            score = min(100, score + 5)
        elif ma5_down:
            score = max(0, score - 5)

        # 均线斜率（趋势强度）
        if len(ma5) >= 5:
            ma5_slope = (latest_ma5 - ma5.iloc[-5]) / ma5.iloc[-5] * 5  # 年化斜率
            if is_bullish_arrangement and ma5_slope > 0.02:
                score = min(100, score + 10)
            elif is_bearish_arrangement and ma5_slope < -0.02:
                score = max(0, score - 10)

        return score

    def get_params(self) -> dict:
        """返回策略参数"""
        return {
            "weight": self.weight
        }

    def generate_signal(self, price_df: pd.DataFrame) -> List[StrategySignal]:
        """
        为多个股票生成信号

        Args:
            price_df: 股票价格数据DataFrame

        Returns:
            信号列表
        """
        signals = []
        for ticker in price_df.columns:
            series = price_df[ticker].dropna()
            if len(series) < 30:
                continue

            score = self.calculate_signal(pd.DataFrame({'close': series}))

            latest_close = series.iloc[-1]
            ma5 = series.rolling(window=5).mean().iloc[-1]
            ma10 = series.rolling(window=10).mean().iloc[-1]
            ma20 = series.rolling(window=20).mean().iloc[-1]

            # 判断动作
            if score >= 75:
                action = "买入"
                reason = f"多头排列买入：MA5({ma5:.2f}) > MA10({ma10:.2f}) > MA20({ma20:.2f})，评分：{score}"
            elif score <= 25:
                action = "卖出"
                reason = f"空头排列卖出：MA5({ma5:.2f}) < MA10({ma10:.2f}) < MA20({ma20:.2f})，评分：{score}"
            elif score > 55:
                action = "观望"
                reason = f"偏多排列：MA5({ma5:.2f}) > MA10({ma10:.2f}) > MA20({ma20:.2f})，评分：{score}"
            else:
                action = "观望"
                reason = f"均线混乱：MA5({ma5:.2f}), MA10({ma10:.2f}), MA20({ma20:.2f})，评分：{score}"

            signals.append(StrategySignal(
                ticker=ticker,
                score=score,
                action=action,
                reason=reason,
                metrics={
                    "MA5": float(ma5),
                    "MA10": float(ma10),
                    "MA20": float(ma20),
                    "close": float(latest_close)
                }
            ))

        return signals

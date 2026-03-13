"""MA金叉策略

本策略基于移动平均线交叉原理：
- 买入信号：短期均线上穿长期均线（ gold cross ）
- 卖出信号：短期均线下穿长期均线（death cross）
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List
from dataclasses import dataclass

from core.scanner.strategies import BaseStrategy, StrategySignal


class MAStrategy(BaseStrategy):
    """MA金叉策略"""

    def __init__(self, short_period: int = 5, long_period: int = 20, weight: float = 1.0):
        """
        初始化MA金叉策略

        Args:
            short_period: 短期均线周期，默认5日
            long_period: 长期均线周期，默认20日
            weight: 策略权重，默认1.0
        """
        super().__init__(f"MA金叉({short_period}/{long_period})", weight)
        self.short_period = short_period
        self.long_period = long_period

    def name(self) -> str:
        """返回策略名称"""
        return "MA金叉策略"

    def description(self) -> str:
        """返回策略描述"""
        return f"MA金叉策略（短期均线：{self.short_period}日，长期均线：{self.long_period}日）- 当短期均线上穿长期均线时产生买入信号"

    def calculate_signal(self, df: pd.DataFrame) -> float:
        """
        计算策略信号评分

        Args:
            df: OHLCV数据，包含open, high, low, close, volume列

        Returns:
            策略评分（0-100），分数越高信号越强
        """
        if len(df) < self.long_period + 5:
            return 50  # 数据不足，中性评分

        close_prices = df['close']

        # 计算短期和长期均线
        short_ma = close_prices.rolling(window=self.short_period).mean()
        long_ma = close_prices.rolling(window=self.long_period).mean()

        if len(short_ma) < 3 or len(long_ma) < 3:
            return 50

        # 获取最近的均线值
        latest_short = short_ma.iloc[-1]
        latest_long = long_ma.iloc[-1]
        prev_short = short_ma.iloc[-2]
        prev_long = long_ma.iloc[-2]
        prev_prev_short = short_ma.iloc[-3] if len(short_ma) > 2 else prev_short
        prev_prev_long = long_ma.iloc[-3] if len(long_ma) > 2 else prev_long

        score = 50  # 默认中性评分

        # 金叉判断
        if prev_prev_short <= prev_prev_long and prev_short <= prev_long and latest_short > latest_long:
            # 刚刚金叉，信号强烈
            score = 85
            # 进一步加分项
            if latest_short > latest_long * 1.02:  # 金叉幅度较大
                score = min(100, score + 5)
            if latest_long > short_ma.iloc[-5:].mean():  # 均线向上
                score = min(100, score + 5)
        elif prev_short <= prev_long and latest_short > latest_long:
            # 金叉确认
            score = 75
        elif prev_short >= prev_long and latest_short < latest_long:
            # 死叉信号
            score = 20
            # 进一步减分项
            if latest_short < latest_long * 0.98:
                score = max(0, score - 5)
        else:
            # 无明显交叉
            if latest_short > latest_long:
                score = 60  # 多头排列但无交叉
            elif latest_short < latest_long:
                score = 40  # 空头排列

        # MA排列加分
        ma5 = short_ma.iloc[-1] if self.short_period == 5 else short_ma.iloc[-1]
        ma10 = close_prices.rolling(window=10).mean().iloc[-1] if self.short_period != 10 else ma5
        ma20 = long_ma.iloc[-1] if self.long_period == 20 else long_ma.iloc[-1]

        # 多头排列检查
        if ma5 > ma10 > ma20:
            score = min(100, score + 10)
        # 空头排列检查
        elif ma5 < ma10 < ma20:
            score = max(0, score - 10)

        return score

    def get_params(self) -> dict:
        """返回策略参数"""
        return {
            "short_period": self.short_period,
            "long_period": self.long_period,
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
            if len(series) < self.long_period + 5:
                continue

            score = self.calculate_signal(pd.DataFrame({'close': series}))

            latest_close = series.iloc[-1]
            latest_short = series.rolling(window=self.short_period).mean().iloc[-1]
            latest_long = series.rolling(window=self.long_period).mean().iloc[-1]

            # 判断动作
            if score >= 75:
                action = "买入"
                reason = f"MA金叉信号：{self.short_period}日均线上穿{self.long_period}日均线，评分：{score}"
            elif score <= 25:
                action = "卖出"
                reason = f"MA死叉信号：{self.short_period}日均线下穿{self.long_period}日均线，评分：{score}"
            elif score > 50:
                action = "观望"
                reason = f"多头排列：价格在均线上方，评分：{score}"
            else:
                action = "观望"
                reason = f"空头排列：价格在均线下方，评分：{score}"

            signals.append(StrategySignal(
                ticker=ticker,
                score=score,
                action=action,
                reason=reason,
                metrics={
                    f"MA{self.short_period}": float(latest_short),
                    f"MA{self.long_period}": float(latest_long),
                    "close": float(latest_close)
                }
            ))

        return signals

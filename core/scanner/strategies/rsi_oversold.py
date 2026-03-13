"""RSI超卖策略

本策略基于相对强弱指数（RSI）：
- RSI周期：14天
- 超卖阈值：30
- 超买阈值：70
- 买入信号：RSI < 30（超卖反弹机会）
- 卖出信号：RSI > 70（超买回调风险）
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List
from dataclasses import dataclass

from core.scanner.strategies import BaseStrategy, StrategySignal


class RSIStrategy(BaseStrategy):
    """RSI超卖策略"""

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70, weight: float = 1.0):
        """
        初始化RSI超卖策略

        Args:
            period: RSI计算周期，默认14天
            oversold: 超卖阈值，默认30
            overbought: 超买阈值，默认70
            weight: 策略权重，默认1.0
        """
        super().__init__(f"RSI超卖({period})", weight)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def name(self) -> str:
        """返回策略名称"""
        return "RSI超卖策略"

    def description(self) -> str:
        """返回策略描述"""
        return f"RSI超卖策略（周期：{self.period}天，超卖阈值：{self.oversold}，超买阈值：{self.overbought}）- RSI低于超卖阈值时产生买入信号"

    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """
        计算RSI指标

        Args:
            prices: 价格序列

        Returns:
            RSI序列
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_signal(self, df: pd.DataFrame) -> float:
        """
        计算策略信号评分

        Args:
            df: OHLCV数据，包含open, high, low, close, volume列

        Returns:
            策略评分（0-100），分数越高信号越强
        """
        if len(df) < self.period + 10:
            return 50  # 数据不足，中性评分

        close_prices = df['close']
        rsi = self.calculate_rsi(close_prices)

        if len(rsi) < 3:
            return 50

        latest_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2] if len(rsi) > 2 else latest_rsi
        prev_prev_rsi = rsi.iloc[-3] if len(rsi) > 3 else prev_rsi

        score = 50  # 默认中性评分

        # 超卖买入信号
        if latest_rsi < self.oversold:
            if prev_prev_rsi >= self.oversold and prev_rsi >= self.oversold:
                # 刚进入超卖区，信号强烈
                score = 90
            elif prev_rsi < self.oversold:
                # 持续超卖，可能仍有下跌空间
                score = 80
            # RSI极低，超卖强烈
            if latest_rsi < 20:
                score = min(100, score + 5)
            if latest_rsi < 15:
                score = min(100, score + 5)
        # 超买卖出信号
        elif latest_rsi > self.overbought:
            if prev_prev_rsi <= self.overbought and prev_rsi <= self.overbought:
                # 刚进入超买区，信号强烈
                score = 10
            elif prev_rsi > self.overbought:
                # 持续超买，可能已有回调
                score = 20
            # RSI极高，超买强烈
            if latest_rsi > 80:
                score = max(0, score + 5)
            if latest_rsi > 85:
                score = max(0, score + 5)
        # 中性区域
        elif 40 < latest_rsi < 60:
            score = 55  # 趋势不明朗
        else:
            # 其他区域
            if latest_rsi < 40:
                score = 45  # 略偏 weakness
            else:
                score = 48  # 略偏 strength

        # RSI方向确认
        if latest_rsi > prev_rsi > prev_prev_rsi:
            # RSI向上，增强信号
            if latest_rsi < self.oversold:
                score = min(100, score + 10)
            score = min(100, score + 5)
        elif latest_rsi < prev_rsi < prev_prev_rsi:
            # RSI向下，减弱信号
            if latest_rsi > self.overbought:
                score = max(0, score - 10)
            score = max(0, score - 5)

        return score

    def get_params(self) -> dict:
        """返回策略参数"""
        return {
            "period": self.period,
            "oversold": self.oversold,
            "overbought": self.overbought,
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
            if len(series) < self.period + 10:
                continue

            score = self.calculate_signal(pd.DataFrame({'close': series}))

            latest_close = series.iloc[-1]
            rsi = self.calculate_rsi(series)
            latest_rsi = rsi.iloc[-1]

            # 判断动作
            if score >= 75:
                action = "买入"
                reason = f"RSI超卖买入：RSI={latest_rsi:.2f} < {self.oversold}，评分：{score}"
            elif score <= 25:
                action = "卖出"
                reason = f"RSI超买卖出：RSI={latest_rsi:.2f} > {self.overbought}，评分：{score}"
            elif score > 55:
                action = "观望"
                reason = f"RSI回升中：RSI={latest_rsi:.2f}，评分：{score}"
            else:
                action = "观望"
                reason = f"RSI中性：RSI={latest_rsi:.2f}，评分：{score}"

            signals.append(StrategySignal(
                ticker=ticker,
                score=score,
                action=action,
                reason=reason,
                metrics={
                    "rsi": float(latest_rsi),
                    "close": float(latest_close)
                }
            ))

        return signals

"""突破策略

本策略基于价格突破原理：
- 均线：20日均线
- 买入信号：价格突破20日高点
- 卖出信号：价格跌破20日低点
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List
from dataclasses import dataclass

from core.scanner.strategies import BaseStrategy, StrategySignal


class BreakoutStrategy(BaseStrategy):
    """突破策略"""

    def __init__(self, period: int = 20, threshold: float = 0.01, weight: float = 1.0):
        """
        初始化突破策略

        Args:
            period: 突破计算周期，默认20天
            threshold: 价格变动阈值，默认1%（用于微调信号强度）
            weight: 策略权重，默认1.0
        """
        super().__init__(f"突破策略({period})", weight)
        self.period = period
        self.threshold = threshold

    def name(self) -> str:
        """返回策略名称"""
        return "突破策略"

    def description(self) -> str:
        """返回策略描述"""
        return f"突破策略（周期：{self.period}天）- 当价格突破{self.period}日高点时产生买入信号"

    def calculate_signal(self, df: pd.DataFrame) -> float:
        """
        计算策略信号评分

        Args:
            df: OHLCV数据，包含open, high, low, close, volume列

        Returns:
            策略评分（0-100），分数越高信号越强
        """
        if len(df) < self.period * 2:
            return 50  # 数据不足，中性评分

        close_prices = df['close']
        high_prices = df['high']
        low_prices = df['low']
        volumes = df['volume'] if 'volume' in df.columns else None

        # 计算20日高点和低点
        high_20d = high_prices.rolling(window=self.period).max()
        low_20d = low_prices.rolling(window=self.period).min()
        close_20d_max = close_prices.rolling(window=self.period).max()

        if len(high_20d) < 3:
            return 50

        latest_close = close_prices.iloc[-1]
        latest_high_20d = high_20d.iloc[-1]
        latest_low_20d = low_20d.iloc[-1]
        prev_close = close_prices.iloc[-2] if len(close_prices) > 2 else latest_close
        prev_high_20d = high_20d.iloc[-2] if len(high_20d) > 2 else latest_high_20d

        # 计算突破程度
        breakout_threshold = latest_high_20d * (1 + self.threshold)
        breakdown_threshold = latest_low_20d * (1 - self.threshold)

        score = 50  # 默认中性评分

        # 价格突破20日高点
        if latest_close > latest_high_20d:
            score = 80
            # 突破幅度加分
            breakout_ratio = (latest_close - latest_high_20d) / latest_high_20d
            if breakout_ratio > 0.03:
                score = min(100, score + 10)
            elif breakout_ratio > 0.01:
                score = min(100, score + 5)

            # 成交量确认
            if volumes is not None:
                avg_volume = volumes.iloc[-self.period:].mean()
                latest_volume = volumes.iloc[-1]
                if latest_volume > avg_volume * 1.5:
                    score = min(100, score + 10)  # 放量突破
                elif latest_volume > avg_volume * 1.2:
                    score = min(100, score + 5)

            # 前期是否已突破
            if prev_close <= prev_high_20d:
                score = min(100, score + 5)  # 刚刚突破
        # 价格跌破20日低点
        elif latest_close < latest_low_20d:
            score = 20
            # 跌破幅度减分
            breakdown_ratio = abs(latest_close - latest_low_20d) / latest_low_20d
            if breakdown_ratio > 0.03:
                score = max(0, score - 10)
            elif breakdown_ratio > 0.01:
                score = max(0, score - 5)

            # 成交量确认
            if volumes is not None:
                avg_volume = volumes.iloc[-self.period:].mean()
                latest_volume = volumes.iloc[-1]
                if latest_volume > avg_volume * 1.5:
                    score = max(0, score - 10)  # 放量下跌

            if prev_close >= prev_low_20d:
                score = max(0, score - 5)  # 刚刚跌破
        else:
            # 价格在20日高点和低点之间
            score = 45

            # 价格接近高点
            if latest_close > breakout_threshold:
                score = 55
                if latest_close > latest_high_20d * 1.01:
                    score = 60
            # 价格接近低点
            elif latest_close < breakdown_threshold:
                score = 35
                if latest_close < latest_low_20d * 0.99:
                    score = 30

        # 价格动量确认
        if len(close_prices) >= 5:
            momentum = (latest_close - close_prices.iloc[-5]) / close_prices.iloc[-5]
            if score >= 70 and momentum > 0.03:
                score = min(100, score + 10)  # 突破伴随动量
            elif score <= 30 and momentum < -0.03:
                score = max(0, score - 10)

        # 布林带位置辅助判断
        if len(close_prices) >= 20:
            ma_20 = close_prices.rolling(window=20).mean().iloc[-1]
            std_20 = close_prices.rolling(window=20).std().iloc[-1]
            upper_band = ma_20 + std_20 * 2
            lower_band = ma_20 - std_20 * 2

            if latest_close > upper_band:
                score = min(100, score + 5)  # 超越布林带上轨
            elif latest_close < lower_band:
                score = max(0, score - 5)  # 跌破布林带下轨

        return score

    def get_params(self) -> dict:
        """返回策略参数"""
        return {
            "period": self.period,
            "threshold": self.threshold,
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
            if len(series) < self.period * 2:
                continue

            # 构建OHLCV数据（假设只有close，用close模拟其他）
            close_prices = series
            high_prices = series * 1.005  # 假设最高价略高于收盘价
            low_prices = series * 0.995  # 假设最低价略低于收盘价

            df_test = pd.DataFrame({
                'close': close_prices,
                'high': high_prices,
                'low': low_prices
            })

            # 检查是否有volume数据
            if len(price_df.columns) > 1 and 'volume' in price_df.index.get_level_values(0) if isinstance(price_df.columns, pd.MultiIndex) else True:
                pass  # 如果有volume数据会自动使用

            score = self.calculate_signal(df_test)

            latest_close = close_prices.iloc[-1]
            high_20d = high_prices.rolling(window=self.period).max().iloc[-1]
            low_20d = low_prices.rolling(window=self.period).min().iloc[-1]

            # 判断动作
            if score >= 75:
                action = "买入"
                reason = f"价格突破{self.period}日高点：{latest_close:.2f} > {high_20d:.2f}，评分：{score}"
            elif score <= 25:
                action = "卖出"
                reason = f"价格跌破{self.period}日低点：{latest_close:.2f} < {low_20d:.2f}，评分：{score}"
            elif score > 55:
                action = "观望"
                reason = f"价格接近{self.period}日高点：{latest_close:.2f} vs {high_20d:.2f}，评分：{score}"
            else:
                action = "观望"
                reason = f"价格在{self.period}日高低点之间：{low_20d:.2f} - {high_20d:.2f}，评分：{score}"

            signals.append(StrategySignal(
                ticker=ticker,
                score=score,
                action=action,
                reason=reason,
                metrics={
                    "high_20d": float(high_20d),
                    "low_20d": float(low_20d),
                    "close": float(latest_close),
                    "breakout_status": "突破高点" if score >= 75 else ("跌破低点" if score <= 25 else "震荡")
                }
            ))

        return signals

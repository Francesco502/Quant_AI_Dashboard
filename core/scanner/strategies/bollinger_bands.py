"""布林带策略

本策略基于布林带指标（Bollinger Bands）：
- 中轨：N日简单移动平均线
- 上轨：中轨 + K * N日标准差
- 下轨：中轨 - K * N日标准差

买入信号：
1. 价格触及下轨且RSI < 30（超卖反弹）
2. 价格突破中轨向上（趋势转强）
3. 带宽收窄后的放量突破（波动率扩张）

卖出信号：
1. 价格触及上轨且RSI > 70（超买回调）
2. 价格跌破中轨向下（趋势转弱）

策略特点：
- 优点：适应性强，可判断超买超卖和波动率
- 缺点：单边趋势中可能过早离场
- 适用：震荡市、趋势转折判断
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List

from core.scanner.strategies import BaseStrategy, StrategySignal


class BollingerBandsStrategy(BaseStrategy):
    """布林带策略"""

    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        weight: float = 1.0
    ):
        """
        初始化布林带策略

        Args:
            period: 计算周期，默认20日
            std_dev: 标准差倍数，默认2.0
            weight: 策略权重，默认1.0
        """
        super().__init__(f"布林带({period},{std_dev})", weight)
        self.period = period
        self.std_dev = std_dev

    def name(self) -> str:
        return "布林带策略"

    def description(self) -> str:
        return (
            f"布林带策略（周期：{self.period}日，标准差：{self.std_dev}倍）- "
            f"通过价格与布林带的位置关系判断超买超卖"
        )

    def _calculate_bollinger_bands(self, df: pd.DataFrame) -> tuple:
        """
        计算布林带

        Returns:
            (中轨, 上轨, 下轨, 带宽百分比)
        """
        close = df['close']

        # 中轨（简单移动平均线）
        middle = close.rolling(window=self.period).mean()

        # 标准差
        std = close.rolling(window=self.period).std()

        # 上轨和下轨
        upper = middle + self.std_dev * std
        lower = middle - self.std_dev * std

        # 带宽百分比（用于判断收缩/扩张）
        bandwidth = (upper - lower) / middle * 100

        return middle, upper, lower, bandwidth

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_signal(self, df: pd.DataFrame) -> float:
        """
        计算布林带策略信号评分

        Returns:
            0-100的评分，越高越强烈买入
        """
        if len(df) < self.period + 10:
            return 50

        close = df['close']
        volume = df.get('volume', pd.Series(index=close.index, dtype=float))

        # 计算布林带
        middle, upper, lower, bandwidth = self._calculate_bollinger_bands(df)

        # 计算RSI
        rsi = self._calculate_rsi(close)

        if len(middle) < 3 or len(rsi) < 3:
            return 50

        latest_close = close.iloc[-1]
        latest_middle = middle.iloc[-1]
        latest_upper = upper.iloc[-1]
        latest_lower = lower.iloc[-1]
        latest_bandwidth = bandwidth.iloc[-1]
        latest_rsi = rsi.iloc[-1]

        prev_close = close.iloc[-2]
        prev_middle = middle.iloc[-2]

        score = 50  # 默认中性

        # 1. 下轨反弹信号
        if latest_close <= latest_lower * 1.01:  # 触及或跌破下轨
            if latest_rsi < 30:  # RSI超卖确认
                score = 85
                # 下轨偏离程度加分
                deviation = (latest_lower - latest_close) / latest_lower
                if deviation > 0.02:
                    score = min(100, score + 10)
                elif deviation > 0.01:
                    score = min(100, score + 5)
            else:
                score = 70  # 触及下轨但RSI不极度超卖

        # 2. 上轨回调信号
        elif latest_close >= latest_upper * 0.99:  # 触及或突破上轨
            if latest_rsi > 70:  # RSI超买确认
                score = 15
                # 上轨偏离程度减分
                deviation = (latest_close - latest_upper) / latest_upper
                if deviation > 0.02:
                    score = max(0, score - 10)
            else:
                score = 30

        # 3. 中轨突破信号
        elif prev_close <= prev_middle and latest_close > latest_middle:
            # 向上突破中轨
            score = 70
            if latest_rsi > 50:
                score = min(85, score + 10)

        # 4. 中轨跌破信号
        elif prev_close >= prev_middle and latest_close < latest_middle:
            # 向下跌破中轨
            score = 30
            if latest_rsi < 50:
                score = max(15, score - 10)

        # 5. 带宽收窄后的突破（ squeeze breakout ）
        if len(bandwidth) >= 20:
            recent_bandwidth = bandwidth.iloc[-20:]
            bandwidth_low = recent_bandwidth.min()

            # 带宽处于近期低点且开始扩张
            if latest_bandwidth < bandwidth_low * 1.1 and latest_bandwidth > bandwidth.iloc[-2]:
                # 价格向上突破
                if latest_close > prev_close * 1.01:
                    score = min(100, score + 15)
                # 价格向下跌破
                elif latest_close < prev_close * 0.99:
                    score = max(0, score - 15)

        # 6. 价格在布林带内的位置
        if score == 50:  # 未触发以上信号
            # 计算%b指标（价格在布林带中的位置）
            percent_b = (latest_close - latest_lower) / (latest_upper - latest_lower)

            if percent_b < 0.2:
                score = 65  # 接近下轨
            elif percent_b < 0.4:
                score = 55  # 下轨到中下轨
            elif percent_b < 0.6:
                score = 50  # 中轨附近
            elif percent_b < 0.8:
                score = 45  # 中轨到上轨
            else:
                score = 35  # 接近上轨

        # 7. 成交量确认
        if 'volume' in df.columns and len(volume) >= self.period:
            avg_volume = volume.iloc[-self.period:].mean()
            latest_volume = volume.iloc[-1]

            if latest_volume > avg_volume * 1.5:  # 放量
                if score > 60:
                    score = min(100, score + 5)
                elif score < 40:
                    score = max(0, score - 5)

        return score

    def get_params(self) -> dict:
        return {
            "period": self.period,
            "std_dev": self.std_dev,
            "weight": self.weight
        }

    def generate_signal(self, price_df: pd.DataFrame) -> List[StrategySignal]:
        """为多个股票生成布林带信号"""
        signals = []

        for ticker in price_df.columns:
            series = price_df[ticker].dropna()
            if len(series) < self.period + 10:
                continue

            # 构建DataFrame
            df = pd.DataFrame({'close': series})

            # 尝试获取volume数据
            if isinstance(price_df.columns, pd.MultiIndex):
                if ('volume', ticker) in price_df.columns:
                    df['volume'] = price_df[('volume', ticker)]
            else:
                # 单只股票的情况
                pass

            score = self.calculate_signal(df)

            # 计算指标值
            middle, upper, lower, bandwidth = self._calculate_bollinger_bands(df)
            rsi = self._calculate_rsi(series)

            latest_close = series.iloc[-1]
            latest_middle = middle.iloc[-1]
            latest_upper = upper.iloc[-1]
            latest_lower = lower.iloc[-1]
            latest_bandwidth = bandwidth.iloc[-1]
            latest_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50

            # 计算%b
            percent_b = (latest_close - latest_lower) / (latest_upper - latest_lower) if latest_upper != latest_lower else 0.5

            # 判断动作和原因
            if score >= 75:
                action = "买入"
                if latest_close <= latest_lower * 1.01:
                    reason = f"布林带下轨反弹，价格={latest_close:.2f}触及下轨={latest_lower:.2f}，RSI={latest_rsi:.1f}，评分：{score}"
                elif latest_bandwidth < 10:
                    reason = f"布林带收窄后向上突破，带宽={latest_bandwidth:.1f}%，评分：{score}"
                else:
                    reason = f"突破布林中轨向上，价格={latest_close:.2f} > 中轨={latest_middle:.2f}，评分：{score}"
            elif score <= 25:
                action = "卖出"
                if latest_close >= latest_upper * 0.99:
                    reason = f"布林带上轨回调，价格={latest_close:.2f}触及上轨={latest_upper:.2f}，RSI={latest_rsi:.1f}，评分：{score}"
                else:
                    reason = f"跌破布林中轨向下，价格={latest_close:.2f} < 中轨={latest_middle:.2f}，评分：{score}"
            elif score > 55:
                action = "观望"
                reason = f"价格在布林带中下轨区间，%b={percent_b:.2f}，评分：{score}"
            elif score < 45:
                action = "观望"
                reason = f"价格在布林带中上轨区间，%b={percent_b:.2f}，评分：{score}"
            else:
                action = "观望"
                reason = f"价格在布林带中轨附近震荡，%b={percent_b:.2f}，评分：{score}"

            signals.append(StrategySignal(
                ticker=ticker,
                score=score,
                action=action,
                reason=reason,
                metrics={
                    "close": float(latest_close),
                    "middle": float(latest_middle),
                    "upper": float(latest_upper),
                    "lower": float(latest_lower),
                    "bandwidth": float(latest_bandwidth),
                    "rsi": float(latest_rsi),
                    "percent_b": float(percent_b)
                }
            ))

        return signals

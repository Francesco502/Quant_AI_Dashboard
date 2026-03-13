"""MACD策略

本策略基于MACD指标（指数平滑异同移动平均线）：
- DIF线：12日EMA - 26日EMA
- DEA线：DIF的9日EMA
- MACD柱：2 * (DIF - DEA)

买入信号：
1. DIF上穿DEA（金叉）且DIF > 0（强势区金叉）
2. MACD底背离：价格创新低，DIF未创新低

卖出信号：
1. DIF下穿DEA（死叉）
2. MACD顶背离：价格创新高，DIF未创新高

策略特点：
- 优点：趋势跟随效果好，信号明确
- 缺点：震荡市有假信号，滞后性
- 适用：趋势明显的市场
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List

from core.scanner.strategies import BaseStrategy, StrategySignal


class MACDStrategy(BaseStrategy):
    """MACD策略"""

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        weight: float = 1.0
    ):
        """
        初始化MACD策略

        Args:
            fast_period: 快线周期，默认12日
            slow_period: 慢线周期，默认26日
            signal_period: 信号线周期，默认9日
            weight: 策略权重，默认1.0
        """
        super().__init__(f"MACD({fast_period},{slow_period})", weight)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def name(self) -> str:
        return "MACD策略"

    def description(self) -> str:
        return (
            f"MACD策略（快线：{self.fast_period}日，慢线：{self.slow_period}日，"
            f"信号线：{self.signal_period}日）- 通过DIF与DEA的交叉判断趋势转折"
        )

    def _calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """计算指数移动平均线"""
        return prices.ewm(span=period, adjust=False).mean()

    def _calculate_macd(self, df: pd.DataFrame) -> tuple:
        """
        计算MACD指标

        Returns:
            (DIF, DEA, MACD柱)
        """
        close = df['close']

        # 计算EMA
        ema_fast = self._calculate_ema(close, self.fast_period)
        ema_slow = self._calculate_ema(close, self.slow_period)

        # DIF线
        dif = ema_fast - ema_slow

        # DEA线（信号线）
        dea = self._calculate_ema(dif, self.signal_period)

        # MACD柱
        macd_histogram = 2 * (dif - dea)

        return dif, dea, macd_histogram

    def _detect_divergence(
        self,
        prices: pd.Series,
        dif: pd.Series,
        lookback: int = 20
    ) -> str:
        """
        检测MACD背离

        Returns:
            'bullish': 底背离
            'bearish': 顶背离
            'none': 无背离
        """
        if len(prices) < lookback + 5:
            return 'none'

        # 获取近期数据
        recent_prices = prices.iloc[-lookback:]
        recent_dif = dif.iloc[-lookback:]

        # 找价格低点和DIF低点
        price_low_idx = recent_prices.idxmin()
        price_low = recent_prices.min()

        # 找前期低点（之前的一个低点）
        mid_point = len(recent_prices) // 2
        earlier_prices = recent_prices.iloc[:mid_point]
        earlier_dif = recent_dif.iloc[:mid_point]

        if len(earlier_prices) < 5:
            return 'none'

        earlier_price_low = earlier_prices.min()
        earlier_dif_low = earlier_dif.min()

        current_price_low = recent_prices.iloc[mid_point:].min()
        current_dif_low = recent_dif.iloc[mid_point:].min()

        # 底背离：价格创新低，DIF未创新低
        if current_price_low < earlier_price_low * 0.98 and current_dif_low > earlier_dif_low * 0.95:
            return 'bullish'

        # 找价格高点和DIF高点
        earlier_price_high = earlier_prices.max()
        earlier_dif_high = earlier_dif.max()

        current_price_high = recent_prices.iloc[mid_point:].max()
        current_dif_high = recent_dif.iloc[mid_point:].max()

        # 顶背离：价格创新高，DIF未创新高
        if current_price_high > earlier_price_high * 1.02 and current_dif_high < earlier_dif_high * 0.95:
            return 'bearish'

        return 'none'

    def calculate_signal(self, df: pd.DataFrame) -> float:
        """
        计算MACD策略信号评分

        Returns:
            0-100的评分，越高越强烈买入
        """
        min_periods = max(self.slow_period, self.fast_period) + self.signal_period + 10
        if len(df) < min_periods:
            return 50

        close = df['close']

        # 计算MACD
        dif, dea, macd_hist = self._calculate_macd(df)

        if len(dif) < 3 or len(dea) < 3:
            return 50

        # 获取最新值
        latest_dif = dif.iloc[-1]
        latest_dea = dea.iloc[-1]
        latest_hist = macd_hist.iloc[-1]
        latest_close = close.iloc[-1]

        prev_dif = dif.iloc[-2]
        prev_dea = dea.iloc[-2]
        prev_hist = macd_hist.iloc[-2]

        # 前前值（用于确认）
        prev_prev_dif = dif.iloc[-3] if len(dif) > 2 else prev_dif
        prev_prev_dea = dea.iloc[-3] if len(dea) > 2 else prev_dea

        score = 50  # 默认中性

        # 判断金叉/死叉
        is_golden_cross = prev_dif <= prev_dea and latest_dif > latest_dea
        is_death_cross = prev_dif >= prev_dea and latest_dif < latest_dea

        # 强势区金叉（DIF > 0）
        if is_golden_cross and latest_dif > 0:
            score = 90
            # 金叉角度加分
            dif_slope = latest_dif - prev_dif
            if dif_slope > 0:
                score = min(100, score + 5)
            # 柱状线由负转正加分
            if prev_hist <= 0 and latest_hist > 0:
                score = min(100, score + 5)

        # 弱势区金叉（DIF < 0）- 可能是反弹
        elif is_golden_cross and latest_dif <= 0:
            score = 70
            # 离0轴越近越强
            if abs(latest_dif) < abs(latest_dea):
                score = min(85, score + 10)

        # 死叉信号
        elif is_death_cross:
            score = 20
            if latest_dif < 0:  # 弱势区死叉，更强烈
                score = 10

        # 检查背离
        divergence = self._detect_divergence(close, dif)
        if divergence == 'bullish':
            score = min(100, score + 15)  # 底背离加分
        elif divergence == 'bearish':
            score = max(0, score - 15)  # 顶背离减分

        # DIF位置判断
        if not is_golden_cross and not is_death_cross:
            if latest_dif > 0 and latest_dif > latest_dea:
                score = 65  # 多头排列
            elif latest_dif > 0 and latest_dif <= latest_dea:
                score = 55  # 多头但可能走弱
            elif latest_dif <= 0 and latest_dif < latest_dea:
                score = 35  # 空头排列
            else:
                score = 45  # 空头但可能走强

        # MACD柱状线趋势
        if len(macd_hist) >= 3:
            hist_trend = macd_hist.iloc[-3:].values
            if hist_trend[0] < hist_trend[1] < hist_trend[2] and latest_hist < 0:
                score = min(100, score + 5)  # 负柱缩小，可能转强
            elif hist_trend[0] > hist_trend[1] > hist_trend[2] and latest_hist > 0:
                score = max(0, score - 5)  # 正柱缩小，可能转弱

        return score

    def get_params(self) -> dict:
        return {
            "fast_period": self.fast_period,
            "slow_period": self.slow_period,
            "signal_period": self.signal_period,
            "weight": self.weight
        }

    def generate_signal(self, price_df: pd.DataFrame) -> List[StrategySignal]:
        """为多个股票生成MACD信号"""
        signals = []

        for ticker in price_df.columns:
            series = price_df[ticker].dropna()
            if len(series) < self.slow_period + self.signal_period + 10:
                continue

            df = pd.DataFrame({'close': series})
            score = self.calculate_signal(df)

            # 计算指标值用于展示
            dif, dea, hist = self._calculate_macd(df)
            latest_dif = dif.iloc[-1]
            latest_dea = dea.iloc[-1]
            latest_hist = hist.iloc[-1]
            latest_close = series.iloc[-1]

            # 检测背离
            divergence = self._detect_divergence(series, dif)

            # 判断动作和原因
            if score >= 80:
                action = "买入"
                if divergence == 'bullish':
                    reason = f"MACD底背离买入信号，DIF={latest_dif:.2f}上穿DEA={latest_dea:.2f}，评分：{score}"
                else:
                    reason = f"MACD金叉买入信号，DIF={latest_dif:.2f}上穿DEA={latest_dea:.2f}，评分：{score}"
            elif score <= 25:
                action = "卖出"
                if divergence == 'bearish':
                    reason = f"MACD顶背离卖出信号，DIF={latest_dif:.2f}下穿DEA={latest_dea:.2f}，评分：{score}"
                else:
                    reason = f"MACD死叉卖出信号，DIF={latest_dif:.2f}下穿DEA={latest_dea:.2f}，评分：{score}"
            elif score > 60:
                action = "观望"
                reason = f"MACD多头排列，DIF={latest_dif:.2f} > DEA={latest_dea:.2f}，评分：{score}"
            elif score < 40:
                action = "观望"
                reason = f"MACD空头排列，DIF={latest_dif:.2f} < DEA={latest_dea:.2f}，评分：{score}"
            else:
                action = "观望"
                reason = f"MACD趋势不明朗，DIF={latest_dif:.2f}，DEA={latest_dea:.2f}，评分：{score}"

            signals.append(StrategySignal(
                ticker=ticker,
                score=score,
                action=action,
                reason=reason,
                metrics={
                    "dif": float(latest_dif),
                    "dea": float(latest_dea),
                    "macd": float(latest_hist),
                    "close": float(latest_close),
                    "divergence": divergence
                }
            ))

        return signals

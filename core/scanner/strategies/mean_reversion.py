"""均值回归策略

本策略基于价格均值回归原理：
- 价格围绕均线波动
- 价格偏离均值过大时倾向于回归
- 使用Z-score衡量偏离程度

买入信号：
- Z-score < -2（价格低于均值2个标准差）
- 或价格触及下轨后回升

卖出信号：
- Z-score > 2（价格高于均值2个标准差）
- 或价格触及上轨后回落

平仓信号：
- |Z-score| < 0.5（回归完成）

策略特点：
- 优点：震荡市表现好，回撤可控
- 缺点：趋势市可能持续亏损
- 适用：震荡市场、区间交易

风险管理：
- 必须设置止损，防止趋势延续
- 建议结合趋势过滤器使用
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List

from core.scanner.strategies import BaseStrategy, StrategySignal


class MeanReversionStrategy(BaseStrategy):
    """均值回归策略"""

    def __init__(
        self,
        period: int = 20,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        weight: float = 1.0
    ):
        """
        初始化均值回归策略

        Args:
            period: 计算均值和标准差的周期，默认20日
            entry_z: 入场Z-score阈值，默认2.0
            exit_z: 出场Z-score阈值，默认0.5
            weight: 策略权重，默认1.0
        """
        super().__init__(f"均值回归({period},{entry_z})", weight)
        self.period = period
        self.entry_z = entry_z
        self.exit_z = exit_z

    def name(self) -> str:
        return "均值回归策略"

    def description(self) -> str:
        return (
            f"均值回归策略（周期：{self.period}日，入场Z值：±{self.entry_z}，"
            f"出场Z值：±{self.exit_z}）- 价格偏离均值后回归"
        )

    def _calculate_z_score(self, df: pd.DataFrame) -> pd.Series:
        """
        计算Z-score（价格偏离均值的标准差倍数）

        Z = (Price - MA) / Std
        """
        close = df['close']
        ma = close.rolling(window=self.period).mean()
        std = close.rolling(window=self.period).std()

        z_score = (close - ma) / std
        return z_score

    def _detect_trend(self, df: pd.DataFrame, lookback: int = 50) -> str:
        """
        检测趋势状态，用于过滤

        Returns:
            'uptrend': 上升趋势
            'downtrend': 下降趋势
            'sideways': 震荡/无明显趋势
        """
        if len(df) < lookback:
            return 'sideways'

        close = df['close']

        # 使用线性回归斜率判断趋势
        from scipy import stats

        x = np.arange(lookback)
        y = close.iloc[-lookback:].values

        slope, _, r_value, _, _ = stats.linregress(x, y)

        # 根据斜率和R²判断趋势
        if r_value**2 > 0.6:  # 趋势较强
            if slope > 0:
                return 'uptrend'
            else:
                return 'downtrend'

        return 'sideways'

    def calculate_signal(self, df: pd.DataFrame) -> float:
        """
        计算均值回归策略信号评分

        Returns:
            0-100的评分，越高越强烈买入
            注意：高评分=超卖（应该买入），低评分=超买（应该卖出）
        """
        if len(df) < self.period + 5:
            return 50

        close = df['close']

        # 计算Z-score
        z_score = self._calculate_z_score(df)

        # 计算均值和距离
        ma = close.rolling(window=self.period).mean()
        std = close.rolling(window=self.period).std()

        if len(z_score) < 3 or len(ma) < 3:
            return 50

        latest_close = close.iloc[-1]
        latest_z = z_score.iloc[-1]
        latest_ma = ma.iloc[-1]
        latest_std = std.iloc[-1]

        prev_z = z_score.iloc[-2]
        prev_prev_z = z_score.iloc[-3] if len(z_score) > 2 else prev_z

        score = 50  # 默认中性

        # 1. 强烈超卖信号（买入）
        if latest_z < -self.entry_z:
            score = 85
            # Z值越极端，信号越强
            if latest_z < -2.5:
                score = 95
            elif latest_z < -3.0:
                score = 100

            # Z值开始回升确认
            if latest_z > prev_z:
                score = min(100, score + 5)

        # 2. 强烈超买信号（卖出）
        elif latest_z > self.entry_z:
            score = 15
            # Z值越极端，信号越强
            if latest_z > 2.5:
                score = 5
            elif latest_z > 3.0:
                score = 0

            # Z值开始回落确认
            if latest_z < prev_z:
                score = max(0, score - 5)

        # 3. 回归区域（平仓/观望）
        elif abs(latest_z) < self.exit_z:
            score = 50  # 回归完成，中性

        # 4. 轻度偏离
        elif latest_z < -1.0:
            score = 65  # 轻度超卖
        elif latest_z > 1.0:
            score = 35  # 轻度超买

        # 5. 趋势过滤（可选）
        # 在强趋势中降低均值回归信号强度
        trend = self._detect_trend(df)
        if trend == 'uptrend' and score < 50:
            # 上升趋势中，卖出信号减弱
            score = max(20, score + 10)
        elif trend == 'downtrend' and score > 50:
            # 下降趋势中，买入信号减弱
            score = min(80, score - 10)

        # 6. 价格与均线距离（百分比）
        distance_pct = (latest_close - latest_ma) / latest_ma * 100

        return score

    def get_params(self) -> dict:
        return {
            "period": self.period,
            "entry_z": self.entry_z,
            "exit_z": self.exit_z,
            "weight": self.weight
        }

    def generate_signal(self, price_df: pd.DataFrame) -> List[StrategySignal]:
        """为多个股票生成均值回归信号"""
        signals = []

        for ticker in price_df.columns:
            series = price_df[ticker].dropna()
            if len(series) < self.period + 5:
                continue

            df = pd.DataFrame({'close': series})
            score = self.calculate_signal(df)

            # 计算指标值
            z_score = self._calculate_z_score(df)
            ma = series.rolling(window=self.period).mean()
            std = series.rolling(window=self.period).std()

            latest_close = series.iloc[-1]
            latest_z = z_score.iloc[-1]
            latest_ma = ma.iloc[-1]
            latest_std = std.iloc[-1]

            prev_z = z_score.iloc[-2] if len(z_score) > 1 else latest_z

            # 计算距离百分比
            distance_pct = (latest_close - latest_ma) / latest_ma * 100

            # 检测趋势
            trend = self._detect_trend(df)

            # 判断动作和原因
            if score >= 80:
                action = "买入"
                if latest_z < -2.5:
                    reason = f"强烈均值回归买入：Z值={latest_z:.2f}（<-2.5），价格偏离{distance_pct:.1f}%，评分：{score}"
                else:
                    reason = f"均值回归买入：Z值={latest_z:.2f}（<-{self.entry_z}），价格偏离{distance_pct:.1f}%，评分：{score}"
            elif score <= 20:
                action = "卖出"
                if latest_z > 2.5:
                    reason = f"强烈均值回归卖出：Z值={latest_z:.2f}（>2.5），价格偏离+{distance_pct:.1f}%，评分：{score}"
                else:
                    reason = f"均值回归卖出：Z值={latest_z:.2f}（>{self.entry_z}），价格偏离+{distance_pct:.1f}%，评分：{score}"
            elif abs(latest_z) < self.exit_z:
                action = "观望"
                reason = f"价格回归均值完成，Z值={latest_z:.2f}（|Z|<{self.exit_z}），评分：{score}"
            elif latest_z < -1.0:
                action = "观望"
                reason = f"价格低于均值，Z值={latest_z:.2f}，偏离{distance_pct:.1f}%，等待更强信号，评分：{score}"
            elif latest_z > 1.0:
                action = "观望"
                reason = f"价格高于均值，Z值={latest_z:.2f}，偏离+{distance_pct:.1f}%，等待更强信号，评分：{score}"
            else:
                action = "观望"
                reason = f"价格在均值附近，Z值={latest_z:.2f}，评分：{score}"

            # 添加趋势提示
            if trend == 'uptrend':
                reason += " [上升趋势中，谨慎做空]"
            elif trend == 'downtrend':
                reason += " [下降趋势中，谨慎做多]"

            signals.append(StrategySignal(
                ticker=ticker,
                score=score,
                action=action,
                reason=reason,
                metrics={
                    "close": float(latest_close),
                    "ma": float(latest_ma),
                    "std": float(latest_std),
                    "z_score": float(latest_z),
                    "distance_pct": float(distance_pct),
                    "trend": trend
                }
            ))

        return signals

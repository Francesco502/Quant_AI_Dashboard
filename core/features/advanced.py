"""
高级特征工程模块

包含以下特征类别：
- 动量特征：momentum_5, momentum_10, momentum_20, streak
- 价格效率特征：efficiency_ratio_10, efficiency_ratio_20
- 均值回归特征：zscore_20, zscore_60, bb_position_20
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional


class MomentumFeatures:
    """
    动量特征

    特征列表：
    - momentum_5: 5日动量
    - momentum_10: 10日动量
    - momentum_20: 20日动量
    - streak: 连涨/连跌天数
    """

    @staticmethod
    def compute_all(price_series: pd.Series) -> pd.DataFrame:
        """
        计算所有动量特征

        参数:
            price_series: 价格序列

        返回:
            包含所有动量特征的DataFrame
        """
        df = pd.DataFrame(index=price_series.index)

        # 计算动量（收益率）
        df["momentum_5"] = price_series / price_series.shift(5) - 1
        df["momentum_10"] = price_series / price_series.shift(10) - 1
        df["momentum_20"] = price_series / price_series.shift(20) - 1

        # 连涨/连跌天数
        df["streak"] = MomentumFeatures._calculate_streak(price_series)

        return df

    @staticmethod
    def _calculate_streak(price_series: pd.Series) -> pd.Series:
        """
        计算连涨/连跌天数

        参数:
            price_series: 价格序列

        返回:
            连涨/连跌天数序列（正数表示连涨，负数表示连跌）
        """
        returns = price_series.pct_change()
        sign = np.sign(returns)

        # 初始化streak序列
        streak = pd.Series(0, index=price_series.index)

        # 遍历计算连涨连跌
        current_streak = 0
        for i in range(len(sign)):
            if sign.iloc[i] == 0:
                current_streak = 0
            elif current_streak == 0 or sign.iloc[i] == sign.iloc[i - 1]:
                current_streak += sign.iloc[i]
            else:
                current_streak = sign.iloc[i]
            streak.iloc[i] = current_streak

        return streak

    @staticmethod
    def momentum(price_series: pd.Series, period: int = 5) -> pd.Series:
        """
        计算动量指标

        参数:
            price_series: 价格序列
            period: 回看周期

        返回:
            动量序列
        """
        return price_series / price_series.shift(period) - 1


class EfficiencyFeatures:
    """
    价格效率特征（Kaufman效率比）

    效率比 = 方向性运动 / 总运动
    值越接近1表示价格趋势越强，效率越高
    值越接近0表示价格来回震荡，效率低

    特征列表：
    - efficiency_ratio_10: 10日Kaufman效率比
    - efficiency_ratio_20: 20日Kaufman效率比
    """

    @staticmethod
    def compute_all(price_series: pd.Series) -> pd.DataFrame:
        """
        计算所有效率特征

        参数:
            price_series: 价格序列

        返回:
            包含所有效率特征的DataFrame
        """
        df = pd.DataFrame(index=price_series.index)

        # 计算各周期的效率比
        for period in [10, 20]:
            df[f"efficiency_ratio_{period}"] = EfficiencyFeatures._calculate_er(
                price_series, period
            )

        return df

    @staticmethod
    def _calculate_er(price_series: pd.Series, period: int) -> pd.Series:
        """
        计算Kaufman效率比

        ER = |price - price.shift(period)| / sum(abs(returns), period)

        参数:
            price_series: 价格序列
            period: 回看周期

        返回:
            效率比序列
        """
        # 方向性运动（价格变动绝对值）
        direction = (price_series - price_series.shift(period)).abs()

        # 总运动（收益率绝对值的滚动和）
        returns = price_series.pct_change()
        volatility = returns.abs().rolling(period).sum()

        # 计算效率比
        er = direction / volatility.replace(0, np.nan)

        # 限制在0-1之间
        er = er.clip(0, 1)

        return er

    @staticmethod
    def efficiency_ratio(price_series: pd.Series, period: int = 10) -> pd.Series:
        """
        计算Kaufman效率比

        参数:
            price_series: 价格序列
            period: 回看周期

        返回:
            效率比序列
        """
        return EfficiencyFeatures._calculate_er(price_series, period)


class MeanReversionFeatures:
    """
    均值回归特征

    特征列表：
    - zscore_20: 20日Z分数
    - zscore_60: 60日Z分数
    - bb_position_20: 布林带位置（20日）
    """

    @staticmethod
    def compute_all(price_series: pd.Series) -> pd.DataFrame:
        """
        计算所有均值回归特征

        参数:
            price_series: 价格序列

        返回:
            包含所有均值回归特征的DataFrame
        """
        df = pd.DataFrame(index=price_series.index)

        # 20日Z分数
        df["zscore_20"] = MeanReversionFeatures._calculate_zscore(price_series, 20)

        # 60日Z分数
        df["zscore_60"] = MeanReversionFeatures._calculate_zscore(price_series, 60)

        # 布林带位置
        df["bb_position_20"] = MeanReversionFeatures._calculate_bb_position(price_series, 20)

        return df

    @staticmethod
    def _calculate_zscore(price_series: pd.Series, window: int) -> pd.Series:
        """
        计算Z分数

        Z-score = (price - sma) / std

        参数:
            price_series: 价格序列
            window: 回看窗口

        返回:
            Z分数序列
        """
        sma = price_series.rolling(window).mean()
        std = price_series.rolling(window).std()

        zscore = (price_series - sma) / std.replace(0, np.nan)

        return zscore

    @staticmethod
    def _calculate_bb_position(price_series: pd.Series, window: int = 20) -> pd.Series:
        """
        计算布林带位置

        BB Position = (price - bb_lower) / (bb_upper - bb_lower)

        参数:
            price_series: 价格序列
            window: 回看窗口

        返回:
            布林带位置序列（0-1之间）
        """
        sma = price_series.rolling(window).mean()
        std = price_series.rolling(window).std()

        bb_upper = sma + 2 * std
        bb_lower = sma - 2 * std

        bb_position = (price_series - bb_lower) / (bb_upper - bb_lower)

        # 限制在0-1之间，处理除零情况
        bb_position = bb_position.clip(0, 1)
        bb_position = bb_position.fillna(0.5)  # 当上下界相同时设为0.5

        return bb_position

    @staticmethod
    def zscore(price_series: pd.Series, window: int = 20) -> pd.Series:
        """
        计算Z分数

        参数:
            price_series: 价格序列
            window: 回看窗口

        返回:
            Z分数序列
        """
        return MeanReversionFeatures._calculate_zscore(price_series, window)

    @staticmethod
    def bb_position(price_series: pd.Series, window: int = 20) -> pd.Series:
        """
        计算布林带位置

        参数:
            price_series: 价格序列
            window: 回看窗口

        返回:
            布林带位置序列
        """
        return MeanReversionFeatures._calculate_bb_position(price_series, window)

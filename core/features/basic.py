"""
基础特征工程模块

包含以下特征类别：
- 波动率特征：realized_vol_5, realized_vol_20, realized_vol_60, vol_ratio_5_20
- 趋势特征：adx_14, plus_di_14, minus_di_14
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional


class VolatilityFeatures:
    """
    实现波动率相关特征

    特征列表：
    - realized_vol_5: 5日实现波动率
    - realized_vol_20: 20日实现波动率
    - realized_vol_60: 60日实现波动率
    - vol_ratio_5_20: 短期/长期波动率比值
    """

    @staticmethod
    def compute_all(price_series: pd.Series) -> pd.DataFrame:
        """
        计算所有波动率特征

        参数:
            price_series: 价格序列

        返回:
            包含所有波动率特征的DataFrame
        """
        df = pd.DataFrame(index=price_series.index)

        # 计算收益率
        returns = price_series.pct_change()

        # 5日实现波动率
        df["realized_vol_5"] = returns.rolling(5).std() * np.sqrt(252)

        # 20日实现波动率
        df["realized_vol_20"] = returns.rolling(20).std() * np.sqrt(252)

        # 60日实现波动率
        df["realized_vol_60"] = returns.rolling(60).std() * np.sqrt(252)

        # 波动率比值：短期/长期
        vol_5 = returns.rolling(5).std()
        vol_20 = returns.rolling(20).std()
        df["vol_ratio_5_20"] = vol_5 / vol_20.replace(0, np.nan)

        return df

    @staticmethod
    def realized_volatility(price_series: pd.Series, window: int = 20) -> pd.Series:
        """
        计算实现波动率

        参数:
            price_series: 价格序列
            window: 回看窗口

        返回:
            实现波动率序列
        """
        returns = price_series.pct_change()
        return returns.rolling(window).std() * np.sqrt(252)

    @staticmethod
    def vol_ratio(price_series: pd.Series, short_window: int = 5, long_window: int = 20) -> pd.Series:
        """
        计算波动率比值

        参数:
            price_series: 价格序列
            short_window: 短期窗口
            long_window: 长期窗口

        返回:
            波动率比值序列
        """
        returns = price_series.pct_change()
        short_vol = returns.rolling(short_window).std()
        long_vol = returns.rolling(long_window).std()
        return short_vol / long_vol.replace(0, np.nan)


class TrendFeatures:
    """
    趋势强度特征（简化版ADX）

    特征列表：
    - adx_14: 14日趋势强度指标
    - plus_di_14: 正方向运动
    - minus_di_14: 负方向运动
    """

    @staticmethod
    def compute_all(price_series: pd.Series) -> pd.DataFrame:
        """
        计算所有趋势特征

        参数:
            price_series: 价格序列

        返回:
            包含所有趋势特征的DataFrame
        """
        df = pd.DataFrame(index=price_series.index)

        # 计算真实波动幅度（True Range的简化版：价格绝对变动）
        tr = price_series.diff().abs()

        # 计算+DM和-DM（方向运动）
        price_diff = price_series.diff()
        plus_dm = price_diff.clip(lower=0)
        minus_dm = (-price_diff).clip(lower=0)

        # 计算ATR（简化版：直接用移动平均）
        atr = tr.rolling(14).mean().replace(0, np.nan)

        # 计算+DI和-DI
        df["plus_di_14"] = (plus_dm.rolling(14).mean() / atr) * 100
        df["minus_di_14"] = (minus_dm.rolling(14).mean() / atr) * 100

        # 计算DX并平滑得到ADX
        di_diff = (df["plus_di_14"] - df["minus_di_14"]).abs()
        di_sum = (df["plus_di_14"] + df["minus_di_14"]).replace(0, np.nan)
        dx = (di_diff / di_sum) * 100
        df["adx_14"] = dx.rolling(14).mean()

        return df

    @staticmethod
    def adx(price_series: pd.Series, window: int = 14) -> pd.Series:
        """
        计算ADX趋势强度指标

        参数:
            price_series: 价格序列
            window: 回看窗口

        返回:
            ADX序列
        """
        df = pd.DataFrame(index=price_series.index)

        tr = price_series.diff().abs()
        price_diff = price_series.diff()
        plus_dm = price_diff.clip(lower=0)
        minus_dm = (-price_diff).clip(lower=0)

        atr = tr.rolling(window).mean().replace(0, np.nan)

        plus_di = (plus_dm.rolling(window).mean() / atr) * 100
        minus_di = (minus_dm.rolling(window).mean() / atr) * 100

        di_diff = (plus_di - minus_di).abs()
        di_sum = (plus_di + minus_di).replace(0, np.nan)
        dx = (di_diff / di_sum) * 100

        return dx.rolling(window).mean()

    @staticmethod
    def plus_di(price_series: pd.Series, window: int = 14) -> pd.Series:
        """
        计算+DI（正方向运动）

        参数:
            price_series: 价格序列
            window: 回看窗口

        返回:
            +DI序列
        """
        tr = price_series.diff().abs()
        price_diff = price_series.diff()
        plus_dm = price_diff.clip(lower=0)
        atr = tr.rolling(window).mean().replace(0, np.nan)
        return (plus_dm.rolling(window).mean() / atr) * 100

    @staticmethod
    def minus_di(price_series: pd.Series, window: int = 14) -> pd.Series:
        """
        计算-DI（负方向运动）

        参数:
            price_series: 价格序列
            window: 回看窗口

        返回:
            -DI序列
        """
        tr = price_series.diff().abs()
        price_diff = price_series.diff()
        minus_dm = (-price_diff).clip(lower=0)
        atr = tr.rolling(window).mean().replace(0, np.nan)
        return (minus_dm.rolling(window).mean() / atr) * 100

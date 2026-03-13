"""价值策略（低PE/PB）

本策略基于价值投资原理：
- 数据来源：基本面数据（PE/PB）
- 买入信号：PE/PB低于历史均值（低估）
- 卖出信号：PE/PB高于历史均值（高估）

注：如果缺乏基本面数据，使用技术指标模拟价值策略
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass

from core.scanner.strategies import BaseStrategy, StrategySignal


class ValueStrategy(BaseStrategy):
    """价值策略（低PE/PB）"""

    def __init__(self, max_pe: float = 30, max_pb: float = 2.0, min_dividend: float = 0.02, weight: float = 1.2):
        """
        初始化价值策略

        Args:
            max_pe: 最大市盈率阈值，默认30
            max_pb: 最大市净率阈值，默认2.0
            min_dividend: 最小股息率阈值，默认2%
            weight: 策略权重，默认1.2
        """
        super().__init__("价值策略", weight)
        self.max_pe = max_pe
        self.max_pb = max_pb
        self.min_dividend = min_dividend

    def name(self) -> str:
        """返回策略名称"""
        return "价值策略"

    def description(self) -> str:
        """返回策略描述"""
        return f"价值策略 - 选择估值低位的价值股（PE<{self.max_pe}, PB<{self.max_pb}, 股息率>{self.min_dividend*100}%）"

    def calculate_signal(self, df: pd.DataFrame, fundamentals: Optional[Dict] = None) -> float:
        """
        计算策略信号评分

        Args:
            df: OHLCV数据，包含open, high, low, close, volume列
            fundamentals: 基本面数据字典，包含pe, pb, dividend_yield等字段

        Returns:
            策略评分（0-100），分数越高信号越强
        """
        if len(df) < 250:
            return 50  # 数据不足，中性评分

        close_prices = df['close']

        # 当前价格
        latest_close = close_prices.iloc[-1]

        score = 50  # 默认中性评分

        # 如果有基本面数据，使用基本面分析
        if fundamentals is not None:
            pe = fundamentals.get('pe', None)
            pb = fundamentals.get('pb', None)
            dividend_yield = fundamentals.get('dividend_yield', None)
            pe_history = fundamentals.get('pe_history', None)  # PE历史序列
            pb_history = fundamentals.get('pb_history', None)  # PB历史序列

            # PE分析
            if pe is not None and pe > 0:
                # 估值水平
                if pe < self.max_pe:
                    score += 20
                    # 相对历史估值
                    if pe_history is not None and len(pe_history) > 12:
                        pe_percentile = (pe_history < pe).mean() * 100
                        if pe_percentile < 30:
                            score += 15  # PE处于历史低位
                        elif pe_percentile < 50:
                            score += 10
                        elif pe_percentile > 70:
                            score = max(0, score - 10)  # PE处于历史高位
                else:
                    score = max(0, score - 10)

                # 检查PE是否在下降趋势
                if pe_history is not None and len(pe_history) >= 3:
                    if pe_history.iloc[-1] < pe_history.iloc[-3].mean():
                        score += 5  # PE下降，估值改善

            # PB分析
            if pb is not None and pb > 0:
                if pb < self.max_pb:
                    score += 20
                    # 相对历史估值
                    if pb_history is not None and len(pb_history) > 12:
                        pb_percentile = (pb_history < pb).mean() * 100
                        if pb_percentile < 30:
                            score += 15  # PB处于历史低位
                        elif pb_percentile < 50:
                            score += 10
                        elif pb_percentile > 70:
                            score = max(0, score - 10)
                else:
                    score = max(0, score - 10)

            # 股息率分析
            if dividend_yield is not None:
                if dividend_yield > self.min_dividend:
                    score += 20
                    # 高股息
                    if dividend_yield > self.min_dividend * 1.5:
                        score += 10
                elif dividend_yield > 0:
                    score += 5  # 有股息但不高
                # 股息率持续增加
                if fundamentals.get('dividend_trend', 0) > 0:
                    score += 5

        # 技术面辅助判断（模拟价值策略）
        # 价格偏离度（类似低估）

        # 计算200日均线
        ma_200 = close_prices.rolling(window=200).mean()

        if len(ma_200) >= 3:
            latest_ma_200 = ma_200.iloc[-1]
            deviation = (latest_close - latest_ma_200) / latest_ma_200

            # 价格低于均线，可能低估
            if deviation < -0.2:
                score += 15
            elif deviation < -0.1:
                score += 10
            elif deviation < 0:
                score += 5
            elif deviation > 0.3:
                score = max(0, score - 15)  # 价格过高

        # 动量辅助判断（价值股通常动量较弱）
        if len(close_prices) >= 250:
            returns = close_prices.pct_change().dropna()
            # 年化动量
            momentum_1y = (1 + returns).tail(250).prod() - 1 if len(returns) >= 250 else 0

            # 价值股通常涨幅适中
            if -0.1 < momentum_1y < 0.3:
                score += 10
            elif momentum_1y > 0.5:
                score = max(0, score - 10)  # 涨幅过大，可能高估
            elif momentum_1y < -0.2:
                score += 5  # 跌幅较大，可能低估

        # 波动率（价值股通常波动较小）
        if len(returns) >= 60:
            volatility = returns.tail(60).std() * np.sqrt(250)
            if volatility < 0.25:  # 低波动
                score += 10
            elif volatility > 0.4:
                score = max(0, score - 5)

        # 确保评分在合理范围
        score = max(0, min(100, score))

        return score

    def get_params(self) -> dict:
        """返回策略参数"""
        return {
            "max_pe": self.max_pe,
            "max_pb": self.max_pb,
            "min_dividend": self.min_dividend,
            "weight": self.weight
        }

    def generate_signal(self, price_df: pd.DataFrame, fundamentals_map: Optional[Dict] = None) -> List[StrategySignal]:
        """
        为多个股票生成信号

        Args:
            price_df: 股票价格数据DataFrame
            fundamentals_map: 基本面数据字典，{ticker: fundamentals_dict}

        Returns:
            信号列表
        """
        signals = []
        for ticker in price_df.columns:
            series = price_df[ticker].dropna()
            if len(series) < 250:
                continue

            # 获取基本面数据
            fundamentals = None
            if fundamentals_map is not None and ticker in fundamentals_map:
                fundamentals = fundamentals_map[ticker]

            score = self.calculate_signal(pd.DataFrame({'close': series}), fundamentals)

            latest_close = series.iloc[-1]
            ma_200 = series.rolling(window=200).mean().iloc[-1]
            deviation = (latest_close - ma_200) / ma_200

            # 判断动作
            action = "观望"
            reason = ""

            if score >= 75:
                action = "买入"
                reason = f"价值股买入：价格偏离均线{deviation*100:.1f}%，估值低位，评分：{score}"
            elif score <= 25:
                action = "卖出"
                reason = f"高估卖出：价格偏离均线{deviation*100:.1f}%，估值高位，评分：{score}"
            elif score > 55:
                action = "观望"
                reason = f"价值股观察：价格偏离均线{deviation*100:.1f}%，估值偏低，评分：{score}"
            else:
                action = "观望"
                reason = f"估值中性：价格偏离均线{deviation*100:.1f}%，评分：{score}"

            # 添加基本面信息（如果有）
            metrics = {
                "close": float(latest_close),
                "ma_200": float(ma_200),
                "deviation": float(deviation),
                "strategy_type": "value"
            }

            if fundamentals:
                metrics.update({
                    "pe": fundamentals.get('pe', 'N/A'),
                    "pb": fundamentals.get('pb', 'N/A'),
                    "dividend_yield": fundamentals.get('dividend_yield', 'N/A')
                })

            signals.append(StrategySignal(
                ticker=ticker,
                score=score,
                action=action,
                reason=reason,
                metrics=metrics
            ))

        return signals

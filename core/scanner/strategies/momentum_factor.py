"""动量因子策略 (Momentum Factor)

本策略基于动量效应（Momentum Effect）：
- 买入过去表现好的股票（赢家组合）
- 卖出过去表现差的股票（输家组合）

学术基础：
- Jegadeesh & Titman (1993) 发现美股存在显著动量效应
- 过去3-12个月表现好的股票未来3-12个月继续表现好

A股适用性：
- 牛市：动量效应显著，强势股持续走强
- 熊市：存在反转效应，需谨慎使用
- 建议回看周期：3-6个月

计算公式：
    Momentum = (Price_today - Price_n_months_ago) / Price_n_months_ago

策略特点：
- 优点：趋势跟随，牛市收益高
- 缺点：反转时回撤大，需严格止损
- 适用：趋势明显的市场

参数建议：
- 回看周期：3-6个月（太短噪音多，太长含反转）
- 持仓数量：前20%-30%
- 再平衡频率：月度
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime, timedelta

from core.scanner.strategies import BaseStrategy, StrategySignal


class MomentumFactorStrategy(BaseStrategy):
    """动量因子策略"""

    def __init__(
        self,
        lookback_days: int = 126,  # 约6个月交易日
        top_percentile: float = 20,  # 前20%
        min_price: float = 5.0,  # 最低股价5元（避免仙股）
        weight: float = 1.0
    ):
        """
        初始化动量因子策略

        Args:
            lookback_days: 回看周期（交易日），默认126日（约6个月）
            top_percentile: 选择前N%的股票，默认20%
            min_price: 最低股价过滤，默认5元
            weight: 策略权重
        """
        super().__init__(f"动量因子({lookback_days}日)", weight)
        self.lookback_days = lookback_days
        self.top_percentile = top_percentile
        self.min_price = min_price

    def name(self) -> str:
        return "动量因子策略"

    def description(self) -> str:
        months = round(self.lookback_days / 21)  # 约21个交易日/月
        return (
            f"动量因子策略（回看周期：约{months}个月，选择前{self.top_percentile}%）- "
            f"基于Jegadeesh & Titman (1993) 动量效应，买入过去表现好的股票"
        )

    def _calculate_momentum(self, prices: pd.Series) -> float:
        """
        计算动量收益率

        Returns:
            动量收益率（年化）
        """
        if len(prices) < self.lookback_days // 2:
            return 0

        # 获取回看周期前的价格
        past_price = prices.iloc[-min(self.lookback_days, len(prices))]
        current_price = prices.iloc[-1]

        if past_price <= 0:
            return 0

        # 计算收益率
        momentum = (current_price - past_price) / past_price

        # 年化处理
        days_held = min(self.lookback_days, len(prices))
        annualized_momentum = (1 + momentum) ** (252 / days_held) - 1

        return annualized_momentum

    def _calculate_momentum_consistency(self, prices: pd.Series) -> float:
        """
        计算动量一致性（避免高波动股票）

        Returns:
            一致性评分 0-1
        """
        if len(prices) < 60:
            return 0.5

        # 计算月度收益率
        monthly_returns = []
        for i in range(1, min(7, len(prices) // 21 + 1)):
            end_idx = -1
            start_idx = -i * 21 - 1
            if abs(start_idx) > len(prices):
                break
            monthly_return = (prices.iloc[end_idx] - prices.iloc[start_idx]) / prices.iloc[start_idx]
            monthly_returns.append(monthly_return)

        if len(monthly_returns) < 3:
            return 0.5

        # 计算正收益月份比例
        positive_months = sum(1 for r in monthly_returns if r > 0)
        consistency = positive_months / len(monthly_returns)

        return consistency

    def calculate_signal(self, df: pd.DataFrame) -> float:
        """
        计算动量策略信号

        注意：此函数在批量选股时使用，单只股票评分需要与其他股票比较
        这里返回的是原始动量得分（0-100）
        """
        if len(df) < self.lookback_days // 3:
            return 50  # 数据不足

        close = df['close']
        latest_close = close.iloc[-1]

        # 价格过滤
        if latest_close < self.min_price:
            return 30  # 低价股降权

        # 计算动量
        momentum = self._calculate_momentum(close)

        # 计算一致性
        consistency = self._calculate_momentum_consistency(close)

        # 综合评分
        # 动量得分：根据年化收益率映射到0-100
        if momentum > 1.0:  # 年化100%+
            momentum_score = 100
        elif momentum > 0.5:  # 年化50%+
            momentum_score = 85 + (momentum - 0.5) * 30
        elif momentum > 0.3:  # 年化30%+
            momentum_score = 70 + (momentum - 0.3) * 75
        elif momentum > 0.1:  # 年化10%+
            momentum_score = 50 + (momentum - 0.1) * 100
        elif momentum > 0:
            momentum_score = 40 + momentum * 100
        elif momentum > -0.1:
            momentum_score = 30 + (momentum + 0.1) * 100
        elif momentum > -0.3:
            momentum_score = 15 + (momentum + 0.3) * 75
        else:
            momentum_score = max(0, 15 + (momentum + 0.3) * 50)

        # 一致性调整
        consistency_bonus = (consistency - 0.5) * 10

        final_score = momentum_score + consistency_bonus
        return max(0, min(100, final_score))

    def get_params(self) -> dict:
        return {
            "lookback_days": self.lookback_days,
            "top_percentile": self.top_percentile,
            "min_price": self.min_price,
            "weight": self.weight
        }

    def generate_signal(self, price_df: pd.DataFrame) -> List[StrategySignal]:
        """
        为多个股票生成动量信号

        这里需要先计算所有股票的动量，然后排名选择前N%
        """
        signals = []
        momentum_data = []

        # 第一步：计算所有股票的动量
        for ticker in price_df.columns:
            series = price_df[ticker].dropna()
            if len(series) < self.lookback_days // 3:
                continue

            latest_close = series.iloc[-1]

            # 价格过滤
            if latest_close < self.min_price:
                continue

            momentum = self._calculate_momentum(series)
            consistency = self._calculate_momentum_consistency(series)

            momentum_data.append({
                'ticker': ticker,
                'momentum': momentum,
                'consistency': consistency,
                'close': latest_close
            })

        if not momentum_data:
            return signals

        # 第二步：按动量排序
        momentum_data.sort(key=lambda x: x['momentum'], reverse=True)

        # 第三步：确定阈值（前N%）
        n_select = max(1, int(len(momentum_data) * self.top_percentile / 100))
        momentum_threshold = momentum_data[n_select - 1]['momentum'] if n_select <= len(momentum_data) else momentum_data[-1]['momentum']

        # 第四步：生成信号
        for data in momentum_data:
            ticker = data['ticker']
            momentum = data['momentum']
            consistency = data['consistency']
            close = data['close']

            # 计算评分
            score = self.calculate_signal(pd.DataFrame({'close': [close]}))

            # 根据排名调整评分
            rank = next(i for i, d in enumerate(momentum_data) if d['ticker'] == ticker)
            rank_percentile = (len(momentum_data) - rank) / len(momentum_data) * 100

            if rank < n_select:
                score = max(score, 75 + (n_select - rank) / n_select * 25)
                action = "买入"
                reason = (
                    f"动量排名前{self.top_percentile}%（第{rank + 1}名），"
                    f"过去{self.lookback_days}日年化收益率{momentum * 100:.1f}%，"
                    f"动量一致性{consistency * 100:.0f}%"
                )
            elif momentum > 0:
                score = 50 + rank_percentile / 4
                action = "观望"
                reason = f"动量中等，年化收益率{momentum * 100:.1f}%，未进入前{self.top_percentile}%"
            else:
                score = max(10, 40 + momentum * 100)
                action = "观望"
                reason = f"动量较弱，年化收益率{momentum * 100:.1f}%，负收益"

            signals.append(StrategySignal(
                ticker=ticker,
                score=int(score),
                action=action,
                reason=reason,
                metrics={
                    "momentum_annual": round(momentum * 100, 2),
                    "consistency": round(consistency * 100, 1),
                    "close": float(close),
                    "rank": rank + 1,
                    "total": len(momentum_data)
                }
            ))

        return signals

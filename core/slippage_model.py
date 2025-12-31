"""滑点模型

职责：
- 模拟真实交易中的滑点成本
- 支持多种滑点模型（固定、基于成交量、基于波动率）
- 提高回测和模拟交易的准确性
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Optional
from dataclasses import dataclass
import logging

from .order_types import Order, OrderSide


logger = logging.getLogger(__name__)


@dataclass
class SlippageConfig:
    """滑点配置"""
    model_type: str = "fixed"  # 'fixed', 'volume', 'volatility'
    fixed_rate: float = 0.001  # 固定滑点率（0.1%）
    volume_impact_factor: float = 0.5  # 成交量影响因子
    volatility_factor: float = 0.3  # 波动率影响因子
    min_slippage: float = 0.0  # 最小滑点
    max_slippage: float = 0.01  # 最大滑点（1%）


class SlippageModel:
    """滑点模型"""

    def __init__(self, config: Optional[SlippageConfig] = None):
        """
        初始化滑点模型

        Args:
            config: 滑点配置
        """
        self.config = config or SlippageConfig()
        logger.info(f"滑点模型初始化: {self.config.model_type}")

    def calculate_slippage(
        self,
        order: Order,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """
        计算滑点

        Args:
            order: 订单对象
            current_price: 当前价格
            market_data: 市场数据（包含成交量、波动率等）

        Returns:
            滑点金额（正数表示成本）
        """
        notional = abs(order.quantity * current_price)
        
        if notional == 0:
            return 0.0
        
        if self.config.model_type == "fixed":
            slippage = self._fixed_slippage(notional)
        elif self.config.model_type == "volume":
            slippage = self._volume_based_slippage(order, current_price, market_data)
        elif self.config.model_type == "volatility":
            slippage = self._volatility_based_slippage(order, current_price, market_data)
        else:
            logger.warning(f"未知的滑点模型类型: {self.config.model_type}，使用固定滑点")
            slippage = self._fixed_slippage(notional)
        
        # 限制滑点范围
        slippage = max(self.config.min_slippage, min(slippage, self.config.max_slippage))
        
        return slippage * notional

    def _fixed_slippage(self, notional: float) -> float:
        """固定滑点"""
        return self.config.fixed_rate

    def _volume_based_slippage(
        self,
        order: Order,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """
        基于成交量的动态滑点

        滑点 = 基础滑点 * (1 + 订单规模 / 平均成交量)
        """
        base_slippage = self.config.fixed_rate
        
        if market_data is None or market_data.empty:
            # 没有市场数据，回退到固定滑点
            return base_slippage
        
        # 获取成交量数据
        if "volume" not in market_data.columns and order.symbol in market_data.columns:
            # 如果只有价格数据，使用固定滑点
            return base_slippage
        
        # 计算平均成交量
        if "volume" in market_data.columns:
            avg_volume = market_data["volume"].mean()
        else:
            avg_volume = 1000000  # 默认值
        
        if avg_volume <= 0:
            return base_slippage
        
        # 订单规模（以金额计算）
        order_size = abs(order.quantity * current_price)
        
        # 计算成交量影响
        volume_ratio = order_size / (avg_volume * current_price) if current_price > 0 else 0
        impact = 1 + self.config.volume_impact_factor * volume_ratio
        
        slippage = base_slippage * impact
        return slippage

    def _volatility_based_slippage(
        self,
        order: Order,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """
        基于波动率的滑点

        滑点 = 基础滑点 * (1 + 波动率 * 波动率因子)
        """
        base_slippage = self.config.fixed_rate
        
        if market_data is None or market_data.empty:
            return base_slippage
        
        # 计算波动率（使用收益率的标准差）
        if order.symbol in market_data.columns:
            price_series = market_data[order.symbol]
            returns = price_series.pct_change().dropna()
            
            if len(returns) > 0:
                volatility = returns.std()
                # 年化波动率（假设252个交易日）
                annual_volatility = volatility * np.sqrt(252)
                
                # 波动率影响
                volatility_impact = 1 + self.config.volatility_factor * annual_volatility
                slippage = base_slippage * volatility_impact
                return slippage
        
        return base_slippage

    def apply_slippage(
        self,
        order: Order,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """
        应用滑点到订单价格

        Args:
            order: 订单对象
            current_price: 当前价格
            market_data: 市场数据

        Returns:
            调整后的价格（考虑滑点）
        """
        slippage_rate = self.calculate_slippage(order, current_price, market_data) / abs(order.quantity * current_price)
        
        if order.side == OrderSide.BUY:
            # 买入：价格上涨（不利滑点）
            adjusted_price = current_price * (1 + slippage_rate)
        else:
            # 卖出：价格下跌（不利滑点）
            adjusted_price = current_price * (1 - slippage_rate)
        
        return adjusted_price

    def estimate_execution_price(
        self,
        order: Order,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """
        估算执行价格（考虑滑点）

        Args:
            order: 订单对象
            current_price: 当前价格
            market_data: 市场数据

        Returns:
            估算的执行价格
        """
        if order.order_type.value == "LIMIT" and order.price:
            # 限价单：使用限价，但考虑滑点
            base_price = order.price
        else:
            # 市价单：使用当前价格
            base_price = current_price
        
        return self.apply_slippage(order, base_price, market_data)


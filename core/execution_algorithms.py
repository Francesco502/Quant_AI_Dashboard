"""订单执行优化算法

职责：
- 实现TWAP（时间加权平均价格）算法
- 实现VWAP（成交量加权平均价格）算法
- 降低大单对市场的冲击
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

from .order_types import Order, OrderSide, Fill
from .order_manager import OrderManager


logger = logging.getLogger(__name__)


class ExecutionAlgorithm(ABC):
    """订单执行算法基类"""

    def __init__(self, order_manager: Optional[OrderManager] = None):
        """
        初始化执行算法

        Args:
            order_manager: 订单管理器（可选）
        """
        self.order_manager = order_manager

    @abstractmethod
    def execute(
        self,
        order: Order,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> List[Fill]:
        """
        执行订单

        Args:
            order: 订单对象
            current_price: 当前价格
            market_data: 市场数据
            **kwargs: 其他参数

        Returns:
            成交记录列表
        """
        pass


class MarketOrderAlgorithm(ExecutionAlgorithm):
    """市价单执行算法（立即全部成交）"""

    def execute(
        self,
        order: Order,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> List[Fill]:
        """立即执行全部订单"""
        fill = Fill(
            fill_id=f"FILL_{order.order_id}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=current_price,
            timestamp=datetime.now(),
            commission=0.0,
        )
        
        return [fill]


class TWAPAlgorithm(ExecutionAlgorithm):
    """时间加权平均价格算法（TWAP）

    将大单拆分，在指定时间内均匀执行
    """

    def __init__(
        self,
        order_manager: Optional[OrderManager] = None,
        duration_minutes: int = 30,
        num_slices: int = 10,
    ):
        """
        初始化TWAP算法

        Args:
            order_manager: 订单管理器
            duration_minutes: 执行时长（分钟）
            num_slices: 拆分数量
        """
        super().__init__(order_manager)
        self.duration_minutes = duration_minutes
        self.num_slices = num_slices

    def execute(
        self,
        order: Order,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> List[Fill]:
        """
        执行TWAP算法

        将订单拆分为多个子订单，在指定时间内均匀执行
        """
        fills: List[Fill] = []
        
        # 计算每个时间片的数量
        total_quantity = order.quantity
        quantity_per_slice = total_quantity // self.num_slices
        remainder = total_quantity % self.num_slices
        
        # 时间间隔
        time_interval = timedelta(minutes=self.duration_minutes / self.num_slices)
        current_time = datetime.now()
        
        # 执行每个时间片
        for i in range(self.num_slices):
            # 最后一个时间片包含余数
            slice_quantity = quantity_per_slice + (remainder if i == self.num_slices - 1 else 0)
            
            if slice_quantity <= 0:
                continue
            
            # 模拟价格（简化：使用当前价格，实际应该获取实时价格）
            slice_price = current_price
            
            fill = Fill(
                fill_id=f"FILL_{order.order_id}_{i}",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=slice_quantity,
                price=slice_price,
                timestamp=current_time + i * time_interval,
                commission=0.0,
            )
            
            fills.append(fill)
        
        logger.info(
            f"TWAP执行完成: {order.order_id} - "
            f"{total_quantity}股分{self.num_slices}次，"
            f"时长{self.duration_minutes}分钟"
        )
        
        return fills


class VWAPAlgorithm(ExecutionAlgorithm):
    """成交量加权平均价格算法（VWAP）

    根据历史成交量分布执行订单
    """

    def __init__(
        self,
        order_manager: Optional[OrderManager] = None,
        lookback_days: int = 20,
        num_slices: int = 10,
    ):
        """
        初始化VWAP算法

        Args:
            order_manager: 订单管理器
            lookback_days: 回看天数（用于计算成交量分布）
            num_slices: 拆分数量
        """
        super().__init__(order_manager)
        self.lookback_days = lookback_days
        self.num_slices = num_slices

    def execute(
        self,
        order: Order,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> List[Fill]:
        """
        执行VWAP算法

        根据历史成交量分布，在成交量较大的时段执行更多订单
        """
        fills: List[Fill] = []
        
        if market_data is None or market_data.empty:
            # 没有市场数据，回退到TWAP
            logger.warning(f"VWAP算法缺少市场数据，回退到均匀分布: {order.order_id}")
            twap = TWAPAlgorithm(self.order_manager, duration_minutes=30, num_slices=self.num_slices)
            return twap.execute(order, current_price, market_data, **kwargs)
        
        # 获取成交量数据
        if "volume" not in market_data.columns:
            # 没有成交量数据，回退到TWAP
            logger.warning(f"VWAP算法缺少成交量数据，回退到均匀分布: {order.order_id}")
            twap = TWAPAlgorithm(self.order_manager, duration_minutes=30, num_slices=self.num_slices)
            return twap.execute(order, current_price, market_data, **kwargs)
        
        # 计算成交量分布（按时间段）
        volume_data = market_data["volume"].tail(self.lookback_days * 20)  # 假设每天20个时间段
        
        if len(volume_data) < self.num_slices:
            # 数据不足，使用均匀分布
            twap = TWAPAlgorithm(self.order_manager, duration_minutes=30, num_slices=self.num_slices)
            return twap.execute(order, current_price, market_data, **kwargs)
        
        # 将成交量数据分成num_slices个时间段
        slice_size = len(volume_data) // self.num_slices
        volume_weights = []
        
        for i in range(self.num_slices):
            start_idx = i * slice_size
            end_idx = (i + 1) * slice_size if i < self.num_slices - 1 else len(volume_data)
            slice_volume = volume_data.iloc[start_idx:end_idx].sum()
            volume_weights.append(slice_volume)
        
        # 归一化权重
        total_volume = sum(volume_weights)
        if total_volume > 0:
            volume_weights = [w / total_volume for w in volume_weights]
        else:
            # 如果总成交量为0，使用均匀分布
            volume_weights = [1.0 / self.num_slices] * self.num_slices
        
        # 根据权重分配订单数量
        total_quantity = order.quantity
        quantities = []
        remaining = total_quantity
        
        for i, weight in enumerate(volume_weights):
            if i == len(volume_weights) - 1:
                # 最后一个包含余数
                quantities.append(remaining)
            else:
                qty = int(total_quantity * weight)
                quantities.append(qty)
                remaining -= qty
        
        # 生成成交记录
        current_time = datetime.now()
        time_interval = timedelta(minutes=30 / self.num_slices)  # 假设30分钟执行窗口
        
        for i, (quantity, weight) in enumerate(zip(quantities, volume_weights)):
            if quantity <= 0:
                continue
            
            # 模拟价格（简化：使用当前价格）
            slice_price = current_price
            
            fill = Fill(
                fill_id=f"FILL_{order.order_id}_{i}",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=quantity,
                price=slice_price,
                timestamp=current_time + i * time_interval,
                commission=0.0,
            )
            
            fills.append(fill)
        
        logger.info(
            f"VWAP执行完成: {order.order_id} - "
            f"{total_quantity}股分{self.num_slices}次，"
            f"基于{self.lookback_days}天成交量分布"
        )
        
        return fills


class AdaptiveAlgorithm(ExecutionAlgorithm):
    """自适应执行算法

    根据订单规模和市场条件自动选择执行策略
    """

    def __init__(
        self,
        order_manager: Optional[OrderManager] = None,
        large_order_threshold: float = 0.1,  # 大单阈值（占平均成交量的比例）
    ):
        """
        初始化自适应算法

        Args:
            order_manager: 订单管理器
            large_order_threshold: 大单阈值
        """
        super().__init__(order_manager)
        self.large_order_threshold = large_order_threshold
        self.twap = TWAPAlgorithm(order_manager)
        self.vwap = VWAPAlgorithm(order_manager)
        self.market = MarketOrderAlgorithm(order_manager)

    def execute(
        self,
        order: Order,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> List[Fill]:
        """
        自适应执行

        根据订单规模选择执行策略：
        - 小单：市价单立即执行
        - 中单：TWAP算法
        - 大单：VWAP算法
        """
        # 判断订单规模
        order_size = abs(order.quantity * current_price)
        
        if market_data is None or market_data.empty or "volume" not in market_data.columns:
            # 没有市场数据，使用TWAP
            return self.twap.execute(order, current_price, market_data, **kwargs)
        
        # 计算平均成交量
        avg_volume = market_data["volume"].tail(20).mean()
        avg_volume_value = avg_volume * current_price if current_price > 0 else 0
        
        if avg_volume_value <= 0:
            # 无法判断，使用TWAP
            return self.twap.execute(order, current_price, market_data, **kwargs)
        
        # 判断订单规模
        size_ratio = order_size / avg_volume_value
        
        if size_ratio < self.large_order_threshold * 0.5:
            # 小单：立即执行
            logger.info(f"自适应算法：小单，使用市价单: {order.order_id}")
            return self.market.execute(order, current_price, market_data, **kwargs)
        elif size_ratio < self.large_order_threshold:
            # 中单：使用TWAP
            logger.info(f"自适应算法：中单，使用TWAP: {order.order_id}")
            return self.twap.execute(order, current_price, market_data, **kwargs)
        else:
            # 大单：使用VWAP
            logger.info(f"自适应算法：大单，使用VWAP: {order.order_id}")
            return self.vwap.execute(order, current_price, market_data, **kwargs)


def get_execution_algorithm(
    algorithm_type: str = "market",
    order_manager: Optional[OrderManager] = None,
    **kwargs
) -> ExecutionAlgorithm:
    """
    获取执行算法实例

    Args:
        algorithm_type: 算法类型（'market', 'twap', 'vwap', 'adaptive'）
        order_manager: 订单管理器
        **kwargs: 算法特定参数

    Returns:
        执行算法实例
    """
    if algorithm_type.lower() == "market":
        return MarketOrderAlgorithm(order_manager)
    elif algorithm_type.lower() == "twap":
        return TWAPAlgorithm(
            order_manager,
            duration_minutes=kwargs.get("duration_minutes", 30),
            num_slices=kwargs.get("num_slices", 10),
        )
    elif algorithm_type.lower() == "vwap":
        return VWAPAlgorithm(
            order_manager,
            lookback_days=kwargs.get("lookback_days", 20),
            num_slices=kwargs.get("num_slices", 10),
        )
    elif algorithm_type.lower() == "adaptive":
        return AdaptiveAlgorithm(
            order_manager,
            large_order_threshold=kwargs.get("large_order_threshold", 0.1),
        )
    else:
        logger.warning(f"未知的算法类型: {algorithm_type}，使用市价单")
        return MarketOrderAlgorithm(order_manager)


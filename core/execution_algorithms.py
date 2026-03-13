"""订单执行算法（简化版）

职责：
- 实现市价单执行算法
- 注：TWAP/VWAP等复杂算法已移除，个人用户无需分批执行

优化说明：
- 2026-03-02: 移除TWAP/VWAP/Adaptive算法，仅保留市价单执行
- 原因：个人用户不需要机构级的分批执行算法
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import logging

from .order_types import Order, Fill


logger = logging.getLogger(__name__)


class ExecutionAlgorithm:
    """订单执行算法基类（简化版）"""

    def execute(
        self,
        order: Order,
        current_price: float,
        **kwargs
    ) -> List[Fill]:
        """
        执行订单

        Args:
            order: 订单对象
            current_price: 当前价格
            **kwargs: 其他参数（忽略）

        Returns:
            成交记录列表
        """
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


# 保留别名兼容
MarketOrderAlgorithm = ExecutionAlgorithm


def get_execution_algorithm(
    algorithm_type: str = "market",
    **kwargs
) -> ExecutionAlgorithm:
    """
    获取执行算法实例（简化版）

    Args:
        algorithm_type: 算法类型（仅支持 'market'，其他类型忽略）
        **kwargs: 忽略其他参数

    Returns:
        执行算法实例
    """
    # 所有类型统一返回市价单执行器
    return ExecutionAlgorithm()


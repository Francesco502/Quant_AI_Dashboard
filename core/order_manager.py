"""订单管理系统

职责：
- 完整的订单生命周期管理
- 订单状态追踪
- 订单修改和撤销
- 订单历史记录
"""

from __future__ import annotations

import uuid
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict

from .order_types import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    Fill,
)


logger = logging.getLogger(__name__)


class OrderManager:
    """订单管理器"""

    def __init__(self):
        """初始化订单管理器"""
        # 订单存储 {order_id: Order}
        self.orders: Dict[str, Order] = {}
        
        # 按标的索引 {symbol: [order_id, ...]}
        self.orders_by_symbol: Dict[str, List[str]] = defaultdict(list)
        
        # 按状态索引 {status: [order_id, ...]}
        self.orders_by_status: Dict[OrderStatus, List[str]] = defaultdict(list)
        
        # 订单历史（已完成的订单）
        self.order_history: List[Order] = []
        self.max_history = 10000
        
        # 成交日志
        self.execution_log: List[Fill] = []
        self.max_execution_log = 10000
        
        # 回调函数
        self.on_order_created: Optional[Callable[[Order], None]] = None
        self.on_order_filled: Optional[Callable[[Order], None]] = None
        self.on_order_cancelled: Optional[Callable[[Order], None]] = None
        self.on_order_rejected: Optional[Callable[[Order], None]] = None
        
        logger.info("订单管理器初始化完成")

    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        client_order_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        account_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Order:
        """
        创建订单

        Args:
            symbol: 标的代码
            side: 订单方向（BUY/SELL）
            quantity: 数量
            order_type: 订单类型（MARKET/LIMIT/STOP/STOP_LIMIT）
            price: 限价（限价单必需）
            stop_price: 止损价（止损单必需）
            time_in_force: 有效期
            client_order_id: 客户端订单ID
            strategy_id: 策略ID
            account_id: 账户ID
            metadata: 元数据

        Returns:
            创建的订单对象
        """
        # 生成订单ID
        order_id = f"ORD_{uuid.uuid4().hex[:12].upper()}"
        
        # 验证订单参数
        if order_type == OrderType.LIMIT and price is None:
            raise ValueError("限价单必须指定价格")
        if order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and stop_price is None:
            raise ValueError("止损单必须指定止损价")
        
        # 创建订单
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            client_order_id=client_order_id or order_id,
            strategy_id=strategy_id,
            account_id=account_id,
            metadata=metadata or {},
        )
        
        # 存储订单
        self.orders[order_id] = order
        self.orders_by_symbol[symbol].append(order_id)
        self.orders_by_status[OrderStatus.PENDING].append(order_id)
        
        # 触发回调
        if self.on_order_created:
            try:
                self.on_order_created(order)
            except Exception as e:
                logger.error(f"订单创建回调异常: {e}")
        
        logger.info(f"订单已创建: {order_id} - {symbol} {side.value} {quantity} {order_type.value}")
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单"""
        return self.orders.get(order_id)

    def get_orders_by_symbol(self, symbol: str, status: Optional[OrderStatus] = None) -> List[Order]:
        """获取指定标的的订单"""
        order_ids = self.orders_by_symbol.get(symbol, [])
        orders = [self.orders[oid] for oid in order_ids if oid in self.orders]
        
        if status:
            orders = [o for o in orders if o.status == status]
        
        return orders

    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        """获取指定状态的订单"""
        order_ids = self.orders_by_status.get(status, [])
        return [self.orders[oid] for oid in order_ids if oid in self.orders]

    def submit_order(self, order_id: str) -> bool:
        """
        提交订单

        Args:
            order_id: 订单ID

        Returns:
            是否成功
        """
        order = self.get_order(order_id)
        if not order:
            logger.error(f"订单不存在: {order_id}")
            return False
        
        if order.status != OrderStatus.PENDING:
            logger.warning(f"订单状态不允许提交: {order_id} - {order.status.value}")
            return False
        
        # 更新状态
        order.update_status(OrderStatus.SUBMITTED)
        self._update_status_index(order)
        
        logger.info(f"订单已提交: {order_id}")
        return True

    def cancel_order(self, order_id: str, reason: Optional[str] = None) -> bool:
        """
        撤销订单

        Args:
            order_id: 订单ID
            reason: 撤销原因

        Returns:
            是否成功
        """
        order = self.get_order(order_id)
        if not order:
            logger.error(f"订单不存在: {order_id}")
            return False
        
        # 只有待提交、已提交、部分成交的订单可以撤销
        if order.status not in [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED
        ]:
            logger.warning(f"订单状态不允许撤销: {order_id} - {order.status.value}")
            return False
        
        # 更新状态
        order.update_status(OrderStatus.CANCELLED, reason)
        self._update_status_index(order)
        
        # 触发回调
        if self.on_order_cancelled:
            try:
                self.on_order_cancelled(order)
            except Exception as e:
                logger.error(f"订单撤销回调异常: {e}")
        
        logger.info(f"订单已撤销: {order_id} - {reason or ''}")
        return True

    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
    ) -> bool:
        """
        修改订单

        Args:
            order_id: 订单ID
            quantity: 新数量
            price: 新价格（限价单）

        Returns:
            是否成功
        """
        order = self.get_order(order_id)
        if not order:
            logger.error(f"订单不存在: {order_id}")
            return False
        
        # 只有待提交、已提交的订单可以修改
        if order.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
            logger.warning(f"订单状态不允许修改: {order_id} - {order.status.value}")
            return False
        
        # 修改数量
        if quantity is not None and quantity > 0:
            # 调整剩余数量
            old_remaining = order.remaining_quantity
            order.quantity = order.filled_quantity + quantity
            order.remaining_quantity = quantity
        
        # 修改价格
        if price is not None and order.order_type == OrderType.LIMIT:
            order.price = price
        
        logger.info(f"订单已修改: {order_id}")
        return True

    def reject_order(self, order_id: str, reason: str) -> bool:
        """
        拒绝订单

        Args:
            order_id: 订单ID
            reason: 拒绝原因

        Returns:
            是否成功
        """
        order = self.get_order(order_id)
        if not order:
            return False
        
        order.update_status(OrderStatus.REJECTED, reason)
        self._update_status_index(order)
        
        # 移动到历史
        self._move_to_history(order)
        
        # 触发回调
        if self.on_order_rejected:
            try:
                self.on_order_rejected(order)
            except Exception as e:
                logger.error(f"订单拒绝回调异常: {e}")
        
        logger.warning(f"订单已拒绝: {order_id} - {reason}")
        return True

    def add_fill(self, order_id: str, fill: Fill) -> bool:
        """
        添加成交记录

        Args:
            order_id: 订单ID
            fill: 成交记录

        Returns:
            是否成功
        """
        order = self.get_order(order_id)
        if not order:
            return False
        
        # 添加成交
        success = order.add_fill(fill)
        if success:
            # 记录到执行日志
            self.execution_log.append(fill)
            if len(self.execution_log) > self.max_execution_log:
                self.execution_log = self.execution_log[-self.max_execution_log:]
            
            # 更新状态索引
            self._update_status_index(order)
            
            # 如果全部成交，移动到历史
            if order.status == OrderStatus.FILLED:
                self._move_to_history(order)
                
                # 触发回调
                if self.on_order_filled:
                    try:
                        self.on_order_filled(order)
                    except Exception as e:
                        logger.error(f"订单成交回调异常: {e}")
            
            logger.info(f"订单成交: {order_id} - {fill.quantity}@{fill.price}")
        
        return success

    def _update_status_index(self, order: Order):
        """更新状态索引"""
        # 从旧状态移除
        for status, order_ids in self.orders_by_status.items():
            if order.order_id in order_ids:
                order_ids.remove(order.order_id)
                break
        
        # 添加到新状态
        self.orders_by_status[order.status].append(order.order_id)

    def _move_to_history(self, order: Order):
        """移动到历史"""
        if order.order_id in self.orders:
            del self.orders[order.order_id]
            
            # 从索引中移除
            if order.symbol in self.orders_by_symbol:
                if order.order_id in self.orders_by_symbol[order.symbol]:
                    self.orders_by_symbol[order.symbol].remove(order.order_id)
            
            self._update_status_index(order)
            
            # 添加到历史
            self.order_history.append(order)
            if len(self.order_history) > self.max_history:
                self.order_history = self.order_history[-self.max_history:]
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """获取订单状态"""
        order = self.get_order(order_id)
        if not order:
            return None
        
        return {
            "order_id": order.order_id,
            "status": order.status.value,
            "filled_quantity": order.filled_quantity,
            "remaining_quantity": order.remaining_quantity,
            "avg_fill_price": order.avg_fill_price,
            "total_commission": order.total_commission,
        }
    
    def get_order_statistics(self) -> Dict:
        """获取订单统计信息"""
        stats = {
            "total_orders": len(self.orders) + len(self.order_history),
            "active_orders": len(self.orders),
            "history_orders": len(self.order_history),
            "by_status": {
                status.value: len(order_ids)
                for status, order_ids in self.orders_by_status.items()
            },
            "total_fills": len(self.execution_log),
            "total_commission": sum(
                order.total_commission
                for order in list(self.orders.values()) + self.order_history
            ),
        }
        return stats
    
    def cleanup_expired_orders(self):
        """清理过期订单"""
        now = datetime.now()
        expired_orders = []
        
        for order in list(self.orders.values()):
            if order.time_in_force == TimeInForce.DAY:
                # 当日有效订单，检查是否过期
                if order.created_time.date() < now.date():
                    expired_orders.append(order.order_id)
        
        for order_id in expired_orders:
            self.cancel_order(order_id, reason="订单已过期")


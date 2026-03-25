"""订单管理器 - 持久化版本

职责：
- 完整的订单生命周期管理（PENDING, SUBMITTED, FILLED, CANCELLED, REJECTED等）
- 订单状态追踪
- 订单修改和撤销
- 订单历史记录
- 止损止盈规则管理
"""

from __future__ import annotations

import uuid
import logging
from typing import Dict, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from core.database import Database, get_database
from core.order_types import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    Fill,
)

logger = logging.getLogger(__name__)


class OrderManager:
    """
    订单管理器 - 持久化版本

    所有订单状态变更立即写入数据库
    """

    def __init__(self, db: Database):
        """初始化订单管理器"""
        self.db = db

        # 内存缓存
        self._order_cache: Dict[str, Order] = {}
        self._order_by_symbol: Dict[str, List[str]] = defaultdict(list)
        self._order_by_status: Dict[OrderStatus, List[str]] = defaultdict(list)

        logger.info("订单管理器初始化完成")

    # ==================== 订单创建与持久化 ====================

    def create_order(
        self,
        account_id: int,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        strategy_id: Optional[str] = None,
    ) -> Order:
        """
        创建订单 - 立即持久化

        Args:
            account_id: 账户ID
            symbol: 标的代码
            side: 订单方向（BUY/SELL）
            order_type: 订单类型（MARKET/LIMIT/STOP/STOP_LIMIT）
            quantity: 数量
            price: 限价（限价单必需）
            stop_price: 止损价（止损单必需）
            time_in_force: 有效期
            strategy_id: 策略ID

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

        # 创建订单对象
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            strategy_id=strategy_id,
            account_id=str(account_id),
            status=OrderStatus.PENDING,
        )

        # 持久化到数据库
        self._persist_order(order)

        # 更新内存缓存
        self._order_cache[order_id] = order
        self._order_by_symbol[symbol].append(order_id)
        self._order_by_status[OrderStatus.PENDING].append(order_id)

        logger.info(f"订单已创建: {order_id} - {symbol} {side.value} {quantity} {order_type.value}")
        return order

    def _persist_order(self, order: Order):
        """将订单持久化到数据库"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO orders
            (order_id, account_id, symbol, side, order_type,
             quantity, price, stop_price, status, time_in_force,
             strategy_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            order.order_id,
            order.account_id,
            order.symbol,
            order.side.value,
            order.order_type.value,
            order.quantity,
            order.price,
            order.stop_price,
            order.status.value,
            order.time_in_force.value,
            order.strategy_id
        ))
        self.db.conn.commit()

    def submit_order(self, order_id: str) -> bool:
        """提交订单"""
        order = self._order_cache.get(order_id)
        if not order:
            order = self._load_order(order_id)
            if not order:
                logger.error(f"订单不存在: {order_id}")
                return False

        if order.status != OrderStatus.PENDING:
            logger.warning(f"订单状态不允许提交: {order_id} - {order.status.value}")
            return False

        # 更新订单状态
        order.update_status(OrderStatus.SUBMITTED)

        # 持久化状态
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE orders
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ?
        """, (order.status.value, order_id))
        self.db.conn.commit()

        # 更新内存索引
        self._order_by_status[OrderStatus.PENDING].remove(order_id)
        self._order_by_status[OrderStatus.SUBMITTED].append(order_id)

        logger.info(f"订单已提交: {order_id}")
        return True

    def _load_order(self, order_id: str) -> Optional[Order]:
        """从数据库加载订单"""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_order(row)
        return None

    def _row_to_order(self, row) -> Order:
        """从数据库行转换为Order对象"""
        return Order(
            order_id=row["order_id"],
            symbol=row["symbol"],
            side=OrderSide(row["side"]),
            order_type=OrderType(row["order_type"]),
            quantity=row["quantity"],
            price=row["price"],
            stop_price=row["stop_price"],
            time_in_force=TimeInForce(row["time_in_force"]) if "time_in_force" in row and row["time_in_force"] else TimeInForce.DAY,
            status=OrderStatus(row["status"]),
            created_time=datetime.fromisoformat(row["created_at"]) if "created_at" in row and row["created_at"] else datetime.now(),
            filled_quantity=row["filled_quantity"] if "filled_quantity" in row else 0,
            avg_fill_price=row["avg_fill_price"] if "avg_fill_price" in row else 0.0,
            strategy_id=row["strategy_id"] if "strategy_id" in row else None,
            account_id=row["account_id"] if "account_id" in row else None,
        )

    # ==================== 订单查询 ====================

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单（优先从缓存，其次从数据库）"""
        order = self._order_cache.get(order_id)
        if order:
            return order
        return self._load_order(order_id)

    def get_orders_by_account(self, account_id: int, status: Optional[OrderStatus] = None) -> List[Order]:
        """获取账户的订单列表"""
        cursor = self.db.conn.cursor()
        query = """
            SELECT * FROM orders
            WHERE account_id = ?
        """
        params = [account_id]

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)

        return [self._row_to_order(row) for row in cursor.fetchall()]

    def get_active_orders(self, account_id: Optional[int] = None) -> List[Order]:
        """获取活跃订单（未完成的订单）"""
        active_statuses = [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]

        cursor = self.db.conn.cursor()
        if account_id:
            cursor.execute("""
                SELECT * FROM orders
                WHERE status IN (?, ?, ?) AND account_id = ?
                ORDER BY created_at DESC
            """, (OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value, OrderStatus.PARTIALLY_FILLED.value, account_id))
        else:
            cursor.execute("""
                SELECT * FROM orders
                WHERE status IN (?, ?, ?)
                ORDER BY created_at DESC
            """, (OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value, OrderStatus.PARTIALLY_FILLED.value))

        return [self._row_to_order(row) for row in cursor.fetchall()]

    def get_orders_by_symbol(self, symbol: str, status: Optional[OrderStatus] = None) -> List[Order]:
        """获取指定标的的订单"""
        cursor = self.db.conn.cursor()
        query = """
            SELECT * FROM orders
            WHERE symbol = ?
        """
        params = [symbol]

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)

        return [self._row_to_order(row) for row in cursor.fetchall()]

    # ==================== 订单修改与取消 ====================

    def modify_order(self, order_id: str, quantity: Optional[int] = None, price: Optional[float] = None) -> bool:
        """
        修改订单（仅支持PENDING状态的订单）
        """
        order = self.get_order(order_id)
        if not order:
            logger.error(f"订单不存在: {order_id}")
            return False

        # 只能修改PENDING状态的订单
        if order.status != OrderStatus.PENDING:
            logger.warning(f"订单状态不允许修改: {order_id} - {order.status.value}")
            return False

        # 修改数量
        if quantity is not None and quantity > 0:
            order.quantity = quantity
            order.remaining_quantity = quantity

        # 修改价格
        if price is not None and order.order_type == OrderType.LIMIT:
            order.price = price

        # 持久化修改
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE orders
            SET quantity = ?, price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ?
        """, (order.quantity, order.price, order_id))
        self.db.conn.commit()

        logger.info(f"订单已修改: {order_id}")
        return True

    def cancel_order(self, order_id: str, reason: Optional[str] = None) -> bool:
        """
        取消订单
        """
        order = self.get_order(order_id)
        if not order:
            logger.error(f"订单不存在: {order_id}")
            return False

        # 只能取消未完成的订单
        if order.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
            logger.warning(f"订单状态不允许撤销: {order_id} - {order.status.value}")
            return False

        # 更新订单状态
        order.update_status(OrderStatus.CANCELLED, reason)

        # 持久化状态
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE orders
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ?
        """, (order.status.value, order_id))
        self.db.conn.commit()

        # 处理冻结资源的解冻
        self._release_frozen_resources(order)

        # 更新内存索引
        self._update_status_index(order)

        logger.info(f"订单已撤销: {order_id} - {reason or ''}")
        return True

    def _release_frozen_resources(self, order: Order):
        """释放冻结的资源"""
        account_id = int(order.account_id)

        if order.side == OrderSide.BUY:
            # 买入订单：解冻资金
            cost = order.quantity * (order.price or 0)
            cursor = self.db.conn.cursor()
            cursor.execute("""
                UPDATE accounts
                SET frozen = frozen - ?, balance = balance + ?
                WHERE id = ? AND frozen >= ?
            """, (cost, cost, account_id, cost))
        else:
            # 卖出订单：解冻持仓（如果订单未成交）
            cursor = self.db.conn.cursor()
            cursor.execute("""
                UPDATE positions
                SET available_shares = available_shares + ?
                WHERE account_id = ? AND ticker = ?
            """, (order.quantity, account_id, order.symbol))

        self.db.conn.commit()

    # ==================== 成交处理 ====================

    def add_fill(self, order_id: str, fill: Fill) -> bool:
        """
        添加成交记录
        """
        order = self.get_order(order_id)
        if not order:
            logger.error(f"订单不存在: {order_id}")
            return False

        # 添加成交
        order.add_fill(fill)

        # 持久化成交记录
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO fills
            (fill_id, order_id, account_id, symbol, side, quantity, price, commission, slippage, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fill.fill_id,
            fill.order_id,
            int(fill.account_id) if hasattr(fill, 'account_id') else 1,
            fill.symbol,
            fill.side.value,
            fill.quantity,
            fill.price,
            fill.commission,
            getattr(fill, 'slippage', 0) or 0,
            fill.timestamp.isoformat()
        ))

        # 更新订单状态
        cursor.execute("""
            UPDATE orders
            SET filled_quantity = ?, avg_fill_price = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ?
        """, (
            order.filled_quantity,
            order.avg_fill_price,
            order.status.value,
            order_id
        ))

        self.db.conn.commit()

        # 更新内存缓存
        self._order_cache[order_id] = order
        self._update_status_index(order)

        logger.info(f"订单成交: {order_id} - {fill.quantity}@{fill.price}")
        return True

    def batch_add_fills(self, order_id: str, fills: List[Fill]) -> bool:
        """
        批量添加成交记录（优化性能）

        Args:
            order_id: 订单ID
            fills: 成交记录列表

        Returns:
            是否成功
        """
        if not fills:
            return True

        order = self.get_order(order_id)
        if not order:
            logger.error(f"订单不存在: {order_id}")
            return False

        # 添加所有成交
        for fill in fills:
            order.add_fill(fill)

        try:
            cursor = self.db.conn.cursor()

            # 批量插入fills
            fills_data = [(
                fill.fill_id,
                fill.order_id,
                int(fill.account_id) if hasattr(fill, 'account_id') else 1,
                fill.symbol,
                fill.side.value,
                fill.quantity,
                fill.price,
                fill.commission,
                getattr(fill, 'slippage', 0) or 0,
                fill.timestamp.isoformat()
            ) for fill in fills]

            cursor.executemany("""
                INSERT INTO fills
                (fill_id, order_id, account_id, symbol, side, quantity, price, commission, slippage, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, fills_data)

            # 批量更新订单状态
            cursor.execute("""
                UPDATE orders
                SET filled_quantity = ?, avg_fill_price = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ?
            """, (
                order.filled_quantity,
                order.avg_fill_price,
                order.status.value,
                order_id
            ))

            self.db.conn.commit()

            # 更新内存缓存
            self._order_cache[order_id] = order
            self._update_status_index(order)

            logger.info(f"批量订单成交: {order_id} - {len(fills)}笔成交")
            return True

        except Exception as e:
            logger.error(f"批量添加成交失败: {order_id}, error={e}")
            if self.db.conn:
                self.db.conn.rollback()
            return False

    def _update_status_index(self, order: Order):
        """更新订单状态索引"""
        # 移除旧索引
        for status, order_ids in self._order_by_status.items():
            if order.order_id in order_ids:
                order_ids.remove(order.order_id)
                break

        # 添加新索引
        self._order_by_status[order.status].append(order.order_id)

    # ==================== 止损止盈规则管理 ====================

    def set_stop_loss(
        self,
        account_id: int,
        symbol: str,
        entry_price: float,
        stop_type: str = "percentage",
        stop_price: Optional[float] = None,
        stop_percentage: Optional[float] = None,
        quantity: Optional[int] = None
    ):
        """设置止损规则"""
        rule = self._build_stop_loss_rule(
            account_id, symbol, entry_price, stop_type, stop_price, stop_percentage, quantity
        )

        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO stop_loss_rules
            (account_id, symbol, rule_type, stop_type, trigger_price, quantity, enabled, created_at, last_triggered_at, cooldown_seconds)
            VALUES (?, ?, 'STOP_LOSS', ?, ?, ?, 1, CURRENT_TIMESTAMP, NULL, 60)
        """, (
            account_id,
            symbol,
            rule["stop_type"],
            rule["trigger_price"],
            rule.get("quantity")
        ))
        self.db.conn.commit()

        logger.info(f"设置止损规则: {symbol}, 价格={rule['trigger_price']:.2f}")

    def set_take_profit(
        self,
        account_id: int,
        symbol: str,
        entry_price: float,
        take_profit_type: str = "percentage",
        take_profit_price: Optional[float] = None,
        take_profit_percentage: Optional[float] = None,
        quantity: Optional[int] = None
    ):
        """设置止盈规则"""
        rule = self._build_take_profit_rule(
            account_id,
            symbol,
            entry_price,
            take_profit_type,
            take_profit_price,
            take_profit_percentage,
            quantity,
        )

        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO stop_loss_rules
            (account_id, symbol, rule_type, stop_type, trigger_price, quantity, enabled, created_at, last_triggered_at, cooldown_seconds)
            VALUES (?, ?, 'TAKE_PROFIT', ?, ?, ?, 1, CURRENT_TIMESTAMP, NULL, 60)
        """, (
            account_id,
            symbol,
            rule["stop_type"],
            rule["trigger_price"],
            rule.get("quantity")
        ))
        self.db.conn.commit()

        logger.info(f"设置止盈规则: {symbol}, 价格={rule['trigger_price']:.2f}")

    def _build_stop_loss_rule(
        self,
        account_id: int,
        symbol: str,
        entry_price: float,
        stop_type: str,
        stop_price: Optional[float],
        stop_percentage: Optional[float],
        quantity: Optional[int]
    ) -> Dict:
        """构建止损规则"""
        trigger_price = self._resolve_exit_trigger_price(
            entry_price=entry_price,
            exit_type=stop_type,
            explicit_price=stop_price,
            percentage=stop_percentage,
            direction="down",
            default_multiplier=0.95,
        )

        return {
            "account_id": account_id,
            "symbol": symbol,
            "stop_type": stop_type,
            "trigger_price": trigger_price,
            "quantity": quantity
        }

    def _build_take_profit_rule(
        self,
        account_id: int,
        symbol: str,
        entry_price: float,
        take_profit_type: str,
        take_profit_price: Optional[float],
        take_profit_percentage: Optional[float],
        quantity: Optional[int]
    ) -> Dict:
        """构建止盈规则"""
        trigger_price = self._resolve_exit_trigger_price(
            entry_price=entry_price,
            exit_type=take_profit_type,
            explicit_price=take_profit_price,
            percentage=take_profit_percentage,
            direction="up",
            default_multiplier=1.10,
        )

        return {
            "account_id": account_id,
            "symbol": symbol,
            "stop_type": take_profit_type,
            "trigger_price": trigger_price,
            "quantity": quantity
        }

    def _resolve_exit_trigger_price(
        self,
        *,
        entry_price: float,
        exit_type: str,
        explicit_price: Optional[float],
        percentage: Optional[float],
        direction: str,
        default_multiplier: float,
    ) -> float:
        """根据出场方向统一计算止损/止盈触发价。"""
        normalized_type = (exit_type or "percentage").strip().lower()
        pct = float(percentage or 0)

        if normalized_type in {"percentage", "trailing"} and pct > 0:
            multiplier = 1 + pct if direction == "up" else 1 - pct
            return entry_price * multiplier

        if explicit_price and explicit_price > 0:
            return explicit_price

        return entry_price * default_multiplier

    def remove_stop_loss(self, account_id: int, symbol: str):
        """移除止损规则"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            DELETE FROM stop_loss_rules
            WHERE account_id = ? AND symbol = ? AND rule_type = 'STOP_LOSS'
        """, (account_id, symbol))
        self.db.conn.commit()
        logger.info(f"移除止损规则: {symbol}")

    def remove_take_profit(self, account_id: int, symbol: str):
        """移除止盈规则"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            DELETE FROM stop_loss_rules
            WHERE account_id = ? AND symbol = ? AND rule_type = 'TAKE_PROFIT'
        """, (account_id, symbol))
        self.db.conn.commit()
        logger.info(f"移除止盈规则: {symbol}")

    def deactivate_rule(self, rule_id: int):
        """停用止损止盈规则（触发后调用）"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE stop_loss_rules
            SET enabled = 0, last_triggered_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (rule_id,))
        self.db.conn.commit()

    def get_active_stop_rules(self, account_id: Optional[int] = None) -> List[Dict]:
        """获取活跃的止损止盈规则（带有冷却时间检查）"""
        cursor = self.db.conn.cursor()
        if account_id:
            cursor.execute("""
                SELECT * FROM stop_loss_rules
                WHERE account_id = ? AND enabled = 1
                ORDER BY created_at
            """, (account_id,))
        else:
            cursor.execute("""
                SELECT * FROM stop_loss_rules
                WHERE enabled = 1
                ORDER BY created_at
            """)

        rules = [dict(row) for row in cursor.fetchall()]

        # 过滤冷却中的规则
        now = datetime.now()
        filtered_rules = []
        for rule in rules:
            # 检查是否在冷却期内
            if rule.get("last_triggered_at"):
                try:
                    last_triggered = datetime.fromisoformat(rule["last_triggered_at"])
                    cooldown = rule.get("cooldown_seconds", 60)
                    if (now - last_triggered).total_seconds() < cooldown:
                        continue  # 仍在冷却期，跳过
                except (ValueError, TypeError):
                    pass  # 时间格式错误，继续使用
            filtered_rules.append(rule)

        return filtered_rules

    def get_account_stop_rules(self, account_id: int) -> Dict[str, Dict]:
        """获取账户所有止损止盈规则"""
        rules = self.get_active_stop_rules(account_id)

        result = {}
        for rule in rules:
            symbol = rule["symbol"]
            if symbol not in result:
                result[symbol] = {"stop_loss": None, "take_profit": None}

            if rule["rule_type"] == "STOP_LOSS":
                result[symbol]["stop_loss"] = rule
            else:
                result[symbol]["take_profit"] = rule

        return result

    # ==================== 统计信息 ====================

    def get_order_statistics(self, account_id: Optional[int] = None) -> Dict:
        """获取订单统计信息"""
        cursor = self.db.conn.cursor()
        if account_id:
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM orders
                WHERE account_id = ?
                GROUP BY status
            """, (account_id,))
        else:
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM orders
                GROUP BY status
            """)

        by_status = {row["status"]: row["count"] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT COUNT(*) as total FROM orders
        """)
        total = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COALESCE(SUM(quantity), 0) as total_filled FROM fills
        """)
        total_filled = cursor.fetchone()["total_filled"]

        return {
            "total_orders": total,
            "by_status": by_status,
            "total_filled_quantity": total_filled,
        }

    # ==================== 订单转交易 ====================

    def order_to_trade(self, order: Order) -> Dict:
        """将订单转换为交易记录（用于历史回溯）"""
        return {
            "ticker": order.symbol,
            "action": "BUY" if order.side == OrderSide.BUY else "SELL",
            "price": order.avg_fill_price,
            "shares": order.filled_quantity,
            "fee": order.total_commission,
            "trade_time": order.filled_time.isoformat() if order.filled_time else None,
            "order_id": order.order_id,
        }

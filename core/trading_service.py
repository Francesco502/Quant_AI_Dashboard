"""统一交易服务

职责：
- 提供统一的交易API入口
- 协调账户、订单、风控的完整流程
- 强制风控检查，不可绕过
- 自动触发止损止盈
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal

from core.database import Database, get_database
from core.account_manager import AccountManager, Position, Account, Portfolio, InsufficientFundsError, InsufficientSharesError
from core.order_manager import OrderManager
from core.risk_monitor import RiskMonitor
from core.risk_types import RiskAction, RiskLevel
from core.interfaces.broker_adapter import BrokerAdapter, Position as BrokerPosition
from core.order_types import Order, OrderSide, OrderType, OrderStatus, Fill
from core.broker_simulator import Trade, generate_rebalance_trades, apply_trades_to_account

logger = logging.getLogger(__name__)


class TradingError(Exception):
    """交易异常基类"""
    pass


class TradingService:
    """
    统一交易服务 - 协调账户、订单、风控的入口

    职责：
    - 提供统一的交易API入口
    - 强制风控检查，不可绕过
    - 管理订单全生命周期
    - 自动触发止损止盈
    """

    def __init__(
        self,
        account_manager: AccountManager,
        order_manager: OrderManager,
        risk_monitor: RiskMonitor,
        broker_adapter: BrokerAdapter,
        db: Database
    ):
        self.account_mgr = account_manager
        self.order_mgr = order_manager
        self.risk_monitor = risk_monitor
        self.broker = broker_adapter
        self.db = db

        # 启动止损止盈监控线程
        self._start_stop_loss_monitor()

    # ==================== 订单管理 ====================

    def submit_order(
        self,
        user_id: int,
        account_id: int,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        strategy_id: Optional[str] = None
    ) -> Dict:
        """
        提交订单 - 完整流程

        1. 验证用户/账户权限
        2. 创建订单(持久化)
        3. 强制风控检查
        4. 预占资源
        5. 提交执行
        """
        # 1. 验证用户/账户
        account = self.account_mgr.get_account(account_id, user_id)
        if not account:
            return {"success": False, "message": "账户不存在或无权访问"}

        # 2. 创建订单
        order = self.order_mgr.create_order(
            account_id=account_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            strategy_id=strategy_id
        )

        # 3. 风控检查（强制）
        portfolio = self.account_mgr.get_positions(account_id)
        account_info = self.broker.get_account_info()
        current_prices = self._get_current_prices([symbol])

        portfolio_dict = self._portfolio_to_dict(account, portfolio, account_info)

        risk_result = self.risk_monitor.check_order_risk(
            order=self._order_to_dict(order),
            portfolio=portfolio_dict,
            current_prices=current_prices
        )

        if risk_result.action == RiskAction.REJECT:
            self.order_mgr.cancel_order(order.order_id, reason=f"风控拒绝: {risk_result.message}")
            return {
                "success": False,
                "order_id": order.order_id,
                "message": f"风控拒绝: {risk_result.message}"
            }

        # 记录警告但继续
        if risk_result.action == RiskAction.WARN:
            logger.warning(f"订单警告: {risk_result.message}")

        # 4. 预占资源
        try:
            self._reserve_resources(order, account_id)
        except Exception as e:
            self.order_mgr.cancel_order(order.order_id, reason=f"资源预占失败: {str(e)}")
            return {"success": False, "order_id": order.order_id, "message": str(e)}

        # 5. 提交执行
        return self._execute_order(order)

    def _execute_order(self, order: Order) -> Dict:
        """执行订单"""
        # 更新订单状态
        self.order_mgr.submit_order(order.order_id)

        # 调用券商适配器
        filled_order = self.broker.place_order(order)

        # 处理成交
        if filled_order.status == OrderStatus.FILLED:
            fills = self._process_fills(filled_order)
            # 设置止损止盈（仅买入订单）
            if order.side == OrderSide.BUY:
                self._setup_stop_loss_take_profit(order)

            return {
                "success": True,
                "order_id": order.order_id,
                "status": filled_order.status.value,
                "fills": [f.to_dict() for f in fills]
            }
        elif filled_order.status in [OrderStatus.REJECTED, OrderStatus.FAILED]:
            # 释放冻结资源
            self._release_frozen_resources(order)
            return {
                "success": False,
                "order_id": order.order_id,
                "status": filled_order.status.value,
                "message": filled_order.error_message or "订单执行失败"
            }
        else:
            # 部分成交或其他状态
            return {
                "success": True,
                "order_id": order.order_id,
                "status": filled_order.status.value,
                "message": "订单已提交"
            }

    def _order_to_dict(self, order: Order) -> Dict:
        """Order对象转字典（用于风控检查）"""
        return {
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "price": order.price or 0,
            "order_type": order.order_type.value,
            "account_id": order.account_id
        }

    def _reserve_resources(self, order: Order, account_id: int):
        """预占资源"""
        if order.side == OrderSide.BUY:
            # 买入：冻结资金
            cost = order.quantity * (order.price or 0)
            self.account_mgr.freeze_funds(account_id, cost)
        else:
            # 卖出：冻结持仓
            self.account_mgr.freeze_shares(account_id, order.symbol, order.quantity)

    def _release_frozen_resources(self, order: Order):
        """释放冻结资源"""
        account_id = int(order.account_id)
        if order.side == OrderSide.BUY:
            cost = order.quantity * (order.price or 0)
            self.account_mgr.unfreeze_funds(account_id, cost)
        else:
            self.account_mgr.unfreeze_shares(account_id, order.symbol, order.quantity)

    def _process_fills(self, order: Order) -> List[Fill]:
        """处理订单成交（优化为批量插入）"""
        cursor = None
        try:
            cursor = self.db.conn.cursor()

            if not order.fills:
                logger.warning(f"订单没有成交记录: {order.order_id}")
                return []

            # 开始事务
            self.db.conn.execute("BEGIN TRANSACTION")

            # 批量插入 fills 表
            fills_data = []
            for fill in order.fills:
                fills_data.append((
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

            cursor.executemany("""
                INSERT INTO fills
                (fill_id, order_id, account_id, symbol, side, quantity, price, commission, slippage, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, fills_data)

            # 批量更新账户
            for fill in order.fills:
                self.account_mgr.apply_fill(
                    account_id=int(order.account_id),
                    symbol=order.symbol,
                    side=order.side.value,
                    quantity=fill.quantity,
                    price=fill.price,
                    commission=fill.commission or 0
                )

            # 批量记录交易历史
            for fill in order.fills:
                self.account_mgr.add_trade_history(
                    account_id=int(order.account_id),
                    ticker=order.symbol,
                    action=order.side.value,
                    price=fill.price,
                    shares=fill.quantity,
                    fee=fill.commission or 0,
                    order_id=order.order_id,
                    pnl=0  # 卖出时才计算
                )

            # 批量更新订单状态
            cursor.execute("""
                UPDATE orders
                SET filled_quantity = ?, avg_fill_price = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ?
            """, (
                order.filled_quantity,
                order.avg_fill_price,
                order.status.value,
                order.order_id
            ))

            # 提交事务
            self.db.conn.commit()

            logger.info(f"处理订单成交: {order.order_id} - {len(order.fills)}笔成交")
            return order.fills

        except Exception as e:
            logger.error(f"_process_fills 失败: order_id={order.order_id}, error={e}")
            try:
                self.db.conn.rollback()
            except Exception:
                pass
            raise

    def _portfolio_to_dict(
        self,
        account: Account,
        positions: List[Position],
        account_info: Dict
    ) -> Dict:
        """Portfolio对象转字典（用于风控检查）"""
        positions_dict = {p.ticker: p.shares for p in positions}
        return {
            "cash": account.balance,
            "positions": positions_dict,
            "total_assets": account.total_assets,
            "initial_capital": account.initial_capital
        }

    # ==================== 查询接口 ====================

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单"""
        return self.order_mgr.get_order(order_id)

    def get_orders_by_account(self, user_id: int, account_id: int) -> List[Order]:
        """获取账户订单列表"""
        if not self.account_mgr.account_exists(account_id, user_id):
            return []
        return self.order_mgr.get_orders_by_account(account_id)

    def get_active_orders(self, user_id: int, account_id: Optional[int] = None) -> List[Order]:
        """获取活跃订单"""
        if account_id and not self.account_mgr.account_exists(account_id, user_id):
            return []
        return self.order_mgr.get_active_orders(account_id)

    def get_positions(self, user_id: int, account_id: int) -> List[Dict]:
        """获取持仓列表"""
        if not self.account_mgr.account_exists(account_id, user_id):
            return []
        positions = self.account_mgr.get_positions(account_id, refresh_prices=True)
        return [
            {
                "ticker": p.ticker,
                "shares": p.shares,
                "available_shares": p.available_shares,
                "avg_cost": p.avg_cost,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "unrealized_return_pct": p.unrealized_return_pct
            }
            for p in positions
        ]

    def get_portfolio(self, user_id: int, account_id: int) -> Dict:
        """获取账户投资组合"""
        account = self.account_mgr.get_account(account_id, user_id)
        if not account:
            return {}

        positions = self.account_mgr.get_positions(account_id, refresh_prices=True)
        position_value = sum(p.market_value for p in positions)

        return {
            "account_id": account.id,
            "account_name": account.account_name,
            "total_assets": account.total_assets + position_value,
            "cash": account.balance,
            "frozen": account.frozen,
            "position_value": position_value,
            "initial_capital": account.initial_capital
        }

    # ==================== 止损止盈 ====================

    def set_stop_loss(
        self,
        user_id: int,
        account_id: int,
        symbol: str,
        stop_type: str = "percentage",
        stop_percentage: float = 0.05
    ) -> Dict:
        """设置止损规则"""
        if not self.account_mgr.account_exists(account_id, user_id):
            return {"success": False, "message": "账户不存在或无权访问"}

        # 获取持仓成本价
        position = self.account_mgr.get_position(account_id, symbol)
        if not position:
            return {"success": False, "message": "未找到持仓"}

        self.order_mgr.set_stop_loss(
            account_id=account_id,
            symbol=symbol,
            entry_price=position.avg_cost,
            stop_type=stop_type,
            stop_percentage=stop_percentage
        )

        return {"success": True, "message": f"止损规则已设置: {symbol}"}

    def set_take_profit(
        self,
        user_id: int,
        account_id: int,
        symbol: str,
        take_profit_percentage: float = 0.10
    ) -> Dict:
        """设置止盈规则"""
        if not self.account_mgr.account_exists(account_id, user_id):
            return {"success": False, "message": "账户不存在或无权访问"}

        # 获取持仓成本价
        position = self.account_mgr.get_position(account_id, symbol)
        if not position:
            return {"success": False, "message": "未找到持仓"}

        self.order_mgr.set_take_profit(
            account_id=account_id,
            symbol=symbol,
            entry_price=position.avg_cost,
            take_profit_percentage=take_profit_percentage
        )

        return {"success": True, "message": f"止盈规则已设置: {symbol}"}

    def _setup_stop_loss_take_profit(self, order: Order):
        """为新持仓设置止损止盈（默认5%止损，10%止盈）"""
        account_id = int(order.account_id)
        entry_price = order.avg_fill_price or order.price or 0

        if entry_price > 0:
            self.order_mgr.set_stop_loss(
                account_id=account_id,
                symbol=order.symbol,
                entry_price=entry_price,
                stop_type="percentage",
                stop_percentage=0.05
            )

            self.order_mgr.set_take_profit(
                account_id=account_id,
                symbol=order.symbol,
                entry_price=entry_price,
                take_profit_percentage=0.10
            )

    def _start_stop_loss_monitor(self):
        """启动止损止盈监控线程"""
        def monitor_loop():
            while True:
                try:
                    self._check_and_execute_stop_loss()
                except Exception as e:
                    logger.error(f"止损监控异常: {e}")
                import time
                time.sleep(5)  # 5秒检查一次

        import threading
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        logger.info("止损止盈监控线程已启动")

    def _check_and_execute_stop_loss(self):
        """检查并执行止损止盈（修复竞态条件问题）"""
        # 获取所有活跃规则
        rules = self.order_mgr.get_active_stop_rules()

        # 为每个规则检查价格
        for rule in rules:
            symbol = rule["symbol"]
            current_price = self._get_current_price(symbol)

            if not current_price:
                continue

            # 判断是否触发
            should_trigger = self._should_trigger_stop_rule(rule, current_price)

            if should_trigger:
                # 执行平仓
                account_id = rule["account_id"]
                rule_id = rule["id"]

                # 重新查询当前持仓（代替使用 rule.get("quantity")）
                position = self.account_mgr.get_position(account_id, symbol)
                if not position or position.shares <= 0:
                    continue  # 持仓已不存在

                # 使用实际持仓数量，而不是规则中的数量
                exec_quantity = position.shares
                if rule.get("quantity"):
                    exec_quantity = min(exec_quantity, rule["quantity"])

                # 乐观锁：尝试停用规则（防止重复触发）
                # 在创建订单前先更新规则为禁用状态
                cursor = self.db.conn.cursor()
                cursor.execute("""
                    UPDATE stop_loss_rules
                    SET enabled = 0
                    WHERE id = ? AND enabled = 1
                """, (rule_id,))

                if cursor.rowcount == 0:
                    # 规则已被其他线程停用，跳过
                    self.db.conn.rollback()
                    continue

                self.db.conn.commit()

                # 创建市价单平仓
                try:
                    order = self.order_mgr.create_order(
                        account_id=account_id,
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=exec_quantity
                    )

                    # 立即执行
                    result = self._execute_order(order)
                    if result.get("success"):
                        logger.warning(f"触发止损/止盈: {symbol}, 数量={exec_quantity}, 规则ID={rule_id}")
                        # 规则已在上面停用，这里不再重复调用 deactivate_rule
                    else:
                        # 执行失败，恢复规则（可选：记录日志）
                        logger.error(f"止损/止盈执行失败: {symbol}, 规则ID={rule_id}, result={result}")
                except Exception as e:
                    logger.error(f"止损/止盈异常: {symbol}, 规则ID={rule_id}, error={e}")
                    # 异常时规则已停用，无需恢复

    def _should_trigger_stop_rule(self, rule: Dict, current_price: Optional[float]) -> bool:
        """判断是否应该触发止损止盈规则（添加最小时间间隔检查）"""
        # 价格有效性检查
        if current_price is None or current_price <= 0:
            return False  # 价格无效，不触发

        # 检查最小时间间隔（避免同一价格波动反复触发）
        last_triggered = rule.get("last_triggered_at")
        if last_triggered:
            try:
                from datetime import datetime
                last_triggered_dt = datetime.fromisoformat(last_triggered)
                cooldown = rule.get("cooldown_seconds", 60)
                now = datetime.now()
                if (now - last_triggered_dt).total_seconds() < cooldown:
                    return False  # 仍在冷却期，跳过
            except (ValueError, TypeError):
                pass  # 时间格式错误，继续检查

        trigger_price = rule["trigger_price"]
        rule_type = rule["rule_type"]

        if rule_type == "STOP_LOSS":
            # 多头止损：价格跌破触发价
            return current_price <= trigger_price
        elif rule_type == "TAKE_PROFIT":
            # 多头止盈：价格涨破触发价
            return current_price >= trigger_price

        return False

    # ==================== 辅助方法 ====================

    def _get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """获取当前价格（批量）"""
        result = {}
        for symbol in symbols:
            price = self._get_current_price(symbol)
            if price:
                result[symbol] = price
        return result

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """获取单个标的当前价格"""
        try:
            from core.data_service import load_price_data
            df = load_price_data([symbol], days=1)
            if not df.empty and symbol in df.columns:
                valid_prices = df[symbol].dropna()
                if not valid_prices.empty:
                    return float(valid_prices.iloc[-1])
        except Exception as e:
            logger.debug(f"获取价格失败: {symbol} - {e}")
        return None

    def _get_account_positions(self, account_id: int) -> Dict[str, int]:
        """获取账户持仓字典"""
        positions = self.account_mgr.get_positions(account_id)
        return {p.ticker: p.shares for p in positions}

    # ==================== 账户管理 ====================

    def create_account(
        self,
        user_id: int,
        name: str,
        initial_balance: float
    ) -> Dict:
        """创建账户"""
        account_id = self.account_mgr.create_account(user_id, name, initial_balance)
        return {
            "success": True,
            "account_id": account_id,
            "message": "账户创建成功"
        }

    def list_user_accounts(self, user_id: int) -> List[Dict]:
        """获取用户所有账户"""
        return self.account_mgr.list_accounts_with_positions(user_id)

    def cancel_order(self, order_id: str) -> Dict:
        """取消订单"""
        order = self.order_mgr.get_order(order_id)
        if not order:
            return {"success": False, "message": "订单不存在"}

        if self.order_mgr.cancel_order(order_id, reason="用户取消"):
            return {"success": True, "message": "订单已取消"}
        return {"success": False, "message": "订单无法取消"}

    def modify_order(self, order_id: str, quantity: Optional[int] = None, price: Optional[float] = None) -> Dict:
        """修改订单"""
        order = self.order_mgr.get_order(order_id)
        if not order:
            return {"success": False, "message": "订单不存在"}

        if self.order_mgr.modify_order(order_id, quantity, price):
            return {"success": True, "message": "订单已修改"}
        return {"success": False, "message": "订单无法修改"}

    def check_order_risk(
        self,
        user_id: int,
        account_id: int,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Dict:
        """预检查订单风险（提交前）"""
        if not self.account_mgr.account_exists(account_id, user_id):
            return {"success": False, "message": "账户不存在或无权访问"}

        order = Order(
            order_id="TEMP",
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            account_id=str(account_id)
        )

        account = self.account_mgr.get_account(account_id, user_id)
        portfolio = self.account_mgr.get_positions(account_id)
        account_info = self.broker.get_account_info()
        current_prices = self._get_current_prices([symbol])

        portfolio_dict = self._portfolio_to_dict(account, portfolio, account_info)

        risk_result = self.risk_monitor.check_order_risk(
            order=self._order_to_dict(order),
            portfolio=portfolio_dict,
            current_prices=current_prices
        )

        return {
            "passed": risk_result.action in [RiskAction.ALLOW, RiskAction.WARN],
            "action": risk_result.action.value,
            "risk_level": risk_result.risk_level.value,
            "message": risk_result.message
        }

"""统一交易服务

职责：
- 提供统一的交易API入口
- 协调账户、订单、风控的完整流程
- 强制风控检查，不可绕过
- 自动触发止损止盈
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal

from core.database import Database, get_database
from core.account_manager import (
    AccountManager,
    Position,
    Account,
    Portfolio,
    InsufficientFundsError as AccountInsufficientFundsError,
    InsufficientSharesError as AccountInsufficientSharesError,
)
from core.order_manager import OrderManager
from core.position_manager import PositionManager
from core.risk_monitor import RiskMonitor
from core.risk_types import RiskAction, RiskLevel
from core.interfaces.broker_adapter import BrokerAdapter, Position as BrokerPosition
from core.order_types import Order, OrderSide, OrderType, OrderStatus, Fill
from core.broker_simulator import Trade, generate_rebalance_trades, apply_trades_to_account
from core.paper_trading_fees import estimate_buy_total_cost

logger = logging.getLogger(__name__)


PaperAccountManager = AccountManager


class TradingError(Exception):
    """交易异常基类"""
    pass


class InsufficientFundsError(TradingError, AccountInsufficientFundsError):
    """资金不足异常"""
    pass


class InsufficientSharesError(TradingError, AccountInsufficientSharesError):
    """持仓不足异常"""
    pass


class _NoopBrokerAdapter(BrokerAdapter):
    """默认纸面券商适配器：用于单元测试和惰性初始化。"""

    def connect(self) -> bool:
        return True

    def get_account_info(self) -> Dict[str, Any]:
        return {}

    def get_positions(self) -> List[BrokerPosition]:
        return []

    def place_order(self, order: Order) -> Order:
        order.update_status(OrderStatus.SUBMITTED)
        return order

    def cancel_order(self, order_id: str) -> bool:
        return True

    def get_order_status(self, order_id: str) -> OrderStatus:
        return OrderStatus.SUBMITTED

    def get_history(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        return []


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
        account_manager: Optional[AccountManager] = None,
        order_manager: Optional[OrderManager] = None,
        risk_monitor: Optional[RiskMonitor] = None,
        broker_adapter: Optional[BrokerAdapter] = None,
        db: Optional[Database] = None,
        start_stop_loss_monitor: Optional[bool] = None,
    ):
        self.db = db or get_database()
        self.account_mgr = account_manager or PaperAccountManager(self.db)
        self.order_mgr = order_manager or OrderManager(self.db)
        self.risk_monitor = risk_monitor or RiskMonitor()
        self.broker = broker_adapter or _NoopBrokerAdapter()
        self._position_mgr = getattr(self.account_mgr, "position_manager", self.account_mgr)

        # 启动止损止盈监控线程
        if start_stop_loss_monitor is None:
            start_stop_loss_monitor = (
                account_manager is not None
                and order_manager is not None
                and broker_adapter is not None
            )
        if start_stop_loss_monitor:
            self._start_stop_loss_monitor()

    @property
    def account_mgr(self):
        return self._paper_account_mgr

    @account_mgr.setter
    def account_mgr(self, value):
        self._paper_account_mgr = value

    @property
    def order_mgr(self):
        return self._order_mgr

    @order_mgr.setter
    def order_mgr(self, value):
        self._order_mgr = value

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
            raise TradingError("账户不存在或无权访问")

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
        current_prices = self._get_current_prices([symbol])
        reference_price = current_prices.get(symbol)

        portfolio_dict = self._portfolio_to_dict(account, portfolio, {})

        risk_result = self.risk_monitor.check_order_risk(
            order=self._order_to_dict(order, reference_price),
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
            self._reserve_resources(order, account_id, reference_price)
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

    def _order_to_dict(self, order: Order, reference_price: Optional[float] = None) -> Dict:
        """Order对象转字典（用于风控检查）"""
        price = order.price if order.price is not None else reference_price
        return {
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "price": price,
            "order_type": order.order_type.value,
            "account_id": order.account_id
        }

    def _reserve_resources(self, order: Order, account_id: int, reference_price: Optional[float] = None):
        """预占资源"""
        if order.side == OrderSide.BUY:
            reservation_price = order.price if order.price is not None else reference_price
            if reservation_price is None or reservation_price <= 0:
                raise TradingError(f"无法估算订单价格: {order.symbol}")
            cost = estimate_buy_total_cost(reservation_price, order.quantity)
            order.metadata["reserved_cash"] = cost
            self.account_mgr.freeze_funds(account_id, cost)
        else:
            # 卖出：冻结持仓
            self.account_mgr.freeze_shares(account_id, order.symbol, order.quantity)

    def _release_frozen_resources(self, order: Order):
        """释放冻结资源"""
        account_id = int(order.account_id)
        if order.side == OrderSide.BUY:
            cost = float(order.metadata.get("reserved_cash") or 0)
            if cost <= 0 and order.price is not None and order.price > 0:
                cost = estimate_buy_total_cost(order.price, order.quantity)
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
                    int(order.account_id) if order.account_id else 1,
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
        if isinstance(account, dict):
            portfolio = account.get("portfolio") or {}
            raw_positions = portfolio.get("positions") or positions or {}
            if isinstance(raw_positions, dict):
                positions_dict = dict(raw_positions)
            else:
                positions_dict = {
                    (p.get("ticker") if isinstance(p, dict) else getattr(p, "ticker", "")):
                    (p.get("shares") if isinstance(p, dict) else getattr(p, "shares", 0))
                    for p in raw_positions
                    if (p.get("ticker") if isinstance(p, dict) else getattr(p, "ticker", None))
                }
            cash = account.get("balance", portfolio.get("cash", 0))
            total_assets = portfolio.get("total_assets", account.get("total_assets", cash))
            initial_capital = account.get("initial_capital", portfolio.get("initial_capital", cash))
            return {
                "cash": cash,
                "positions": positions_dict,
                "total_assets": total_assets,
                "initial_capital": initial_capital,
            }

        positions_dict = {p.ticker: p.shares for p in positions or []}
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
        list_orders = getattr(self.order_mgr, "list_orders", None)
        if callable(list_orders):
            try:
                return list_orders(account_id=account_id)
            except TypeError:
                return list_orders()
        return self.order_mgr.get_orders_by_account(account_id)

    def get_active_orders(self, user_id: int, account_id: Optional[int] = None) -> List[Order]:
        """获取活跃订单"""
        if account_id and not self.account_mgr.account_exists(account_id, user_id):
            return []
        list_orders = getattr(self.order_mgr, "list_orders", None)
        if callable(list_orders):
            try:
                return list_orders(account_id=account_id, active_only=True)
            except TypeError:
                return list_orders()
        return self.order_mgr.get_active_orders(account_id)

    def get_positions(self, user_id: int, account_id: int, refresh_prices: bool = True) -> List[Dict]:
        """获取持仓列表"""
        if not self.account_mgr.account_exists(account_id, user_id):
            return []
        position_source = self._position_mgr if self._position_mgr is not self.account_mgr else self.account_mgr
        try:
            positions = position_source.get_positions(account_id, refresh_prices=refresh_prices)
        except TypeError:
            positions = position_source.get_positions(account_id)
        return [
            {
                "ticker": p.get("ticker") if isinstance(p, dict) else p.ticker,
                "shares": p.get("shares") if isinstance(p, dict) else p.shares,
                "available_shares": p.get("available_shares") if isinstance(p, dict) else p.available_shares,
                "avg_cost": p.get("avg_cost") if isinstance(p, dict) else p.avg_cost,
                "current_price": p.get("current_price") if isinstance(p, dict) else p.current_price,
                "market_value": p.get("market_value") if isinstance(p, dict) else p.market_value,
                "unrealized_pnl": p.get("unrealized_pnl") if isinstance(p, dict) else p.unrealized_pnl,
                "unrealized_return_pct": p.get("unrealized_return_pct", 0) if isinstance(p, dict) else p.unrealized_return_pct
            }
            for p in positions or []
        ]

    def get_portfolio(self, user_id: int, account_id: int, refresh_prices: bool = True) -> Dict:
        """获取账户投资组合"""
        account = self.account_mgr.get_account(account_id, user_id)
        if not account:
            return {}

        if isinstance(account, dict):
            portfolio = account.get("portfolio") or {}
            return {
                "account_id": account.get("account_id", account_id),
                "account_name": account.get("account_name", account.get("name", "")),
                "portfolio": portfolio,
                "total_assets": portfolio.get("total_assets", account.get("total_assets", 0)),
                "cash": portfolio.get("cash", account.get("balance", 0)),
                "positions": portfolio.get("positions", []),
            }

        positions = self.account_mgr.get_positions(account_id, refresh_prices=refresh_prices)
        position_value = sum(p.market_value for p in positions or [])

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
                    # Rule already disabled by another thread — skip.
                    self.db.conn.rollback()
                    continue

                # Create the market order BEFORE committing the rule update so
                # a crash between the two leaves the rule active for retry.
                try:
                    order = self.order_mgr.create_order(
                        account_id=account_id,
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=exec_quantity
                    )
                    result = self._execute_order(order)
                    if not result.get("success"):
                        # Order failed — roll back the rule change.
                        self.db.conn.rollback()
                        logger.error(f"止损/止盈执行失败: {symbol}, 规则ID={rule_id}, result={result}")
                        continue
                except Exception as e:
                    # Order never placed — roll back the rule change.
                    self.db.conn.rollback()
                    logger.error(f"止损/止盈异常: {symbol}, 规则ID={rule_id}, error={e}")
                    continue

                self.db.conn.commit()
                logger.warning(f"触发止损/止盈: {symbol}, 数量={exec_quantity}, 规则ID={rule_id}")

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
            df = load_price_data([symbol], days=5, remote_cache_days=30)
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
        list_accounts = getattr(self.account_mgr, "list_accounts", None)
        if callable(list_accounts):
            return list_accounts(user_id)
        return self.account_mgr.list_accounts_with_positions(user_id)

    def reset_account(
        self,
        user_id: int,
        account_id: int,
        initial_balance: float,
        account_name: Optional[str] = None,
    ) -> Dict:
        """Reset an account back to cash-only state."""
        account = self.account_mgr.reset_account(
            account_id=account_id,
            user_id=user_id,
            initial_balance=initial_balance,
            account_name=account_name,
        )
        return {
            "success": True,
            "account_id": account.id,
            "account_name": account.account_name,
            "balance": account.balance,
            "initial_capital": account.initial_capital,
            "message": "账户已重置为初始状态",
        }

    def cancel_order(self, order_id: str) -> Dict:
        """取消订单"""
        order = self.order_mgr.get_order(order_id)
        if not order:
            return {"success": False, "message": "订单不存在"}

        releasable_statuses = [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]
        status_value = getattr(order.status, "value", order.status)
        if status_value == OrderStatus.FILLED.value:
            raise TradingError("订单已成交，无法取消")
        should_release = status_value in {status.value for status in releasable_statuses}

        if self.order_mgr.cancel_order(order_id, reason="用户取消"):
            if should_release:
                try:
                    self._release_frozen_resources(order)
                except Exception as exc:
                    logger.warning(f"释放冻结资源失败: {order_id} - {exc}")
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
        current_prices = self._get_current_prices([symbol])
        reference_price = current_prices.get(symbol)

        portfolio_dict = self._portfolio_to_dict(account, portfolio, {})

        risk_result = self.risk_monitor.check_order_risk(
            order=self._order_to_dict(order, reference_price),
            portfolio=portfolio_dict,
            current_prices=current_prices
        )

        return {
            "passed": risk_result.action in [RiskAction.ALLOW, RiskAction.WARN],
            "action": risk_result.action.value,
            "risk_level": risk_result.risk_level.value,
            "message": risk_result.message
        }

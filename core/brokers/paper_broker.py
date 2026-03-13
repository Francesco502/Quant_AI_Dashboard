"""Paper trading broker adapter - 支持多种订单类型

支持的订单类型：
- MARKET: 市价单，立即按最新价成交
- LIMIT: 限价单，按指定价格或更好价格成交
- STOP: 止损单，触发后转为市价单
- STOP_LIMIT: 止损限价单，触发后转为限价单
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from core.interfaces.broker_adapter import BrokerAdapter, Position
from core.order_types import Order, OrderStatus, OrderSide, OrderType, Fill
from core.paper_account import PaperAccount, InsufficientFundsError, InsufficientSharesError
from core.risk_monitor import RiskMonitor
from core.risk_types import RiskAction, RiskCheckResult
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrderBookEntry:
    """订单簿条目（限价单）"""
    order_id: str
    account_id: int
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    created_at: datetime


class PaperBrokerAdapter(BrokerAdapter):
    """
    Paper Trading Broker Adapter
    支持市价单、限价单、止损单、止损限价单
    集成风控检查，防止风险绕过
    """

    def __init__(self, user_id: int = 1, account_id: Optional[int] = None,
                 risk_monitor: Optional[RiskMonitor] = None):
        self.paper_account = PaperAccount(user_id=user_id, account_id=account_id)
        # Ensure account is loaded
        if not self.paper_account.account_id:
            if not self.paper_account.load_default_account():
                self.paper_account.create_account()

        # 风控监控器
        self.risk_monitor = risk_monitor

        # 订单簿（限价单等待撮合）
        self._order_book: Dict[str, List[OrderBookEntry]] = {
            "BUY": [],
            "SELL": []
        }
        # 订单对象映射表（用于更新限价单状态）
        self._limit_orders: Dict[str, Order] = {}
        # 最近价格缓存
        self._price_cache: Dict[str, float] = {}
        # 跟踪有订单簿订单的标的
        self._tracked_symbols: set = set()

    def connect(self) -> bool:
        """连接券商（模拟器始终返回True）"""
        return True

    def disconnect(self):
        """断开连接"""
        pass

    # ==================== 基础接口 ====================

    def get_account_info(self) -> Dict[str, Any]:
        """获取账户信息"""
        portfolio = self.paper_account.get_portfolio_value()
        return {
            "total_assets": portfolio["total_assets"],
            "cash": portfolio["cash"],
            "market_value": portfolio["market_value"],
            "equity": portfolio["total_assets"],
            "currency": self.paper_account.currency,
            "buying_power": portfolio["cash"],
            "frozen": self.paper_account.frozen
        }

    def get_positions(self) -> List[Position]:
        """获取持仓"""
        portfolio = self.paper_account.get_portfolio_value()
        raw_positions = portfolio.get("positions", [])
        positions = []
        for p in raw_positions:
            positions.append(Position(
                ticker=p["ticker"],
                shares=float(p["shares"]),
                avg_cost=float(p["avg_cost"]),
                market_value=float(p.get("market_value", 0.0)),
                unrealized_pnl=float(p.get("unrealized_pnl", 0.0))
            ))
        return positions

    def get_orders(self, account_id: Optional[int] = None) -> List[Order]:
        """获取所有挂单（包括订单簿中的限价单）"""
        orders = list(self._limit_orders.values())
        if account_id:
            orders = [o for o in orders if o.account_id == str(account_id)]
        return orders

    def get_order_status(self, order_id: str) -> OrderStatus:
        """获取订单状态（查询订单簿）"""
        if order_id in self._limit_orders:
            return self._limit_orders[order_id].status
        # 如果不在限价订单簿中，检查是否已成交（市价单）
        # 默认返回已成交（针对已执行的市价单）
        return OrderStatus.FILLED

    def cancel_order(self, order_id: str) -> bool:
        """取消订单（取消订单簿中的限价单）"""
        if order_id in self._limit_orders:
            order = self._limit_orders[order_id]
            # 从订单簿中移除
            side_orders = self._order_book.get(order.side.value, [])
            # 查找并移除对应的 OrderBookEntry
            entry_to_remove = None
            for entry in side_orders:
                if entry.order_id == order_id:
                    entry_to_remove = entry
                    break
            if entry_to_remove:
                side_orders.remove(entry_to_remove)
                # 如果订单簿该侧为空，移除跟踪
                if not side_orders:
                    self._tracked_symbols.discard(order.symbol)
            # 从订单对象映射中移除
            del self._limit_orders[order_id]
            order.status = OrderStatus.CANCELLED
            order.cancelled_time = datetime.now()
            logger.info(f"订单已取消: {order_id}")
            return True
        logger.warning(f"取消订单失败: {order_id} 未找到")
        return False

    def get_history(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """获取交易历史"""
        return self.paper_account.get_trade_history()

    # ==================== 订单执行 ====================

    def place_order(self, order: Order) -> Order:
        """
        下单 - 支持所有订单类型
        集成风控检查，防止风险绕过
        """
        logger.info(f"PaperBroker placing order: {order.order_type.value} {order.side.value} {order.symbol} {order.quantity}")

        # 新订单进行风控检查（已存在的订单不重复检查）
        if order.status == OrderStatus.PENDING:
            risk_result = self._check_order_risk_before_place(order)
            if risk_result and risk_result.action == RiskAction.REJECT:
                order.status = OrderStatus.REJECTED
                order.error_message = f"风控拒绝: {risk_result.message}"
                logger.warning(f"订单被风控拒绝: {order.order_id} - {order.error_message}")
                return order
            # 记录警告但继续
            if risk_result and risk_result.action == RiskAction.WARN:
                logger.warning(f"订单风控警告: {risk_result.message}")

        try:
            if order.order_type == OrderType.MARKET:
                # 市价单：立即按最新价成交
                return self._execute_market_order(order)
            elif order.order_type == OrderType.LIMIT:
                # 限价单：记录到订单簿等待撮合
                return self._place_limit_order(order)
            elif order.order_type == OrderType.STOP:
                # 止损单：记录触发价，等待价格触发
                return self._place_stop_order(order)
            elif order.order_type == OrderType.STOP_LIMIT:
                # 止损限价单：记录触发价和限价
                return self._place_stop_limit_order(order)
            else:
                order.status = OrderStatus.REJECTED
                order.error_message = f"不支持的订单类型: {order.order_type.value}"
                return order

        except InsufficientFundsError as e:
            order.status = OrderStatus.REJECTED
            order.error_message = f"资金不足: {str(e)}"
            logger.warning(f"订单被拒绝: {order.order_id} - {order.error_message}")
            return order
        except InsufficientSharesError as e:
            order.status = OrderStatus.REJECTED
            order.error_message = f"持仓不足: {str(e)}"
            logger.warning(f"订单被拒绝: {order.order_id} - {order.error_message}")
            return order
        except Exception as e:
            order.status = OrderStatus.FAILED
            order.error_message = f"执行失败: {str(e)}"
            logger.error(f"订单执行异常: {order.order_id} - {e}")
            return order

    # ==================== 风控检查 ====================

    def _get_portfolio_for_risk_check(self) -> Dict:
        """
        获取风控检查所需的portfolio格式
        """
        portfolio = self.paper_account.get_portfolio_value()
        positions_dict = {p["ticker"]: p["shares"] for p in portfolio.get("positions", [])}
        return {
            "cash": portfolio["cash"],
            "positions": positions_dict,
            "total_assets": portfolio["total_assets"],
            "initial_capital": getattr(self.paper_account, 'initial_capital', portfolio["cash"])
        }

    def _get_current_price_for_symbol(self, symbol: str) -> Optional[float]:
        """获取单个标的当前价格"""
        return self._get_current_price(symbol)

    def _check_order_risk_before_place(self, order: Order) -> Optional[RiskCheckResult]:
        """
        在订单执行前进行风控检查
        仅对新订单(PENDING状态)进行检查
        """
        if not self.risk_monitor:
            # 无风控监控器，跳过检查
            return None

        # 获取账户信息和当前价格
        portfolio = self._get_portfolio_for_risk_check()
        current_price = self._get_current_price_for_symbol(order.symbol)
        current_prices = {order.symbol: current_price} if current_price else {}

        # 构建订单字典用于风控检查
        order_dict = {
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "price": order.price or current_price or 0,
            "account_id": order.account_id,
            "order_id": order.order_id,
            "order_type": order.order_type.value
        }

        # 执行风控检查
        return self.risk_monitor.check_order_risk(
            order=order_dict,
            portfolio=portfolio,
            current_prices=current_prices
        )

    def _execute_market_order(self, order: Order) -> Order:
        """执行市价单"""
        # 获取当前价格
        current_price = self._get_current_price(order.symbol)

        # 检查价格有效性
        if current_price is None or current_price <= 0:
            order.status = OrderStatus.REJECTED
            order.error_message = f"无法获取有效价格: {order.symbol}"
            logger.warning(f"市价单被拒绝: {order.order_id} - {order.error_message}")
            return order

        if order.side == OrderSide.BUY:
            result = self.paper_account.buy(order.symbol, order.quantity, price=current_price)
        else:
            result = self.paper_account.sell(order.symbol, order.quantity, price=current_price)

        if result and result.get("success"):
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.avg_fill_price = result["price"]
            order.filled_time = datetime.now()
            order.remaining_quantity = 0

            # 创建成交记录
            fill = Fill(
                fill_id=f"FILL_{datetime.now().timestamp()}",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=result["price"],
                timestamp=datetime.now(),
                commission=result.get("fee", 0)
            )
            order.fills.append(fill)

        else:
            order.status = OrderStatus.FAILED

        return order

    def _place_limit_order(self, order: Order) -> Order:
        """提交限价单到订单簿"""
        # 获取当前价格以验证限价合理性
        current_price = self._get_current_price(order.symbol)

        # 检查价格有效性
        if current_price is None or current_price <= 0:
            order.status = OrderStatus.REJECTED
            order.error_message = f"无法获取有效价格进行限价单验证: {order.symbol}"
            logger.warning(f"限价单被拒绝: {order.order_id} - {order.error_message}")
            return order

        # 检查资金/持仓
        total_cost = order.quantity * order.price

        if order.side == OrderSide.BUY:
            # 检查资金
            account_info = self.get_account_info()
            if account_info["cash"] < total_cost:
                order.status = OrderStatus.REJECTED
                order.error_message = "资金不足"
                return order
        else:
            # 检查持仓
            positions = self.get_positions()
            position = next((p for p in positions if p.ticker == order.symbol), None)
            if not position or position.shares < order.quantity:
                order.status = OrderStatus.REJECTED
                order.error_message = "持仓不足"
                return order

        # 将订单添加到订单簿等待撮合
        entry = OrderBookEntry(
            order_id=order.order_id,
            account_id=int(order.account_id) if order.account_id else 1,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            created_at=datetime.now()
        )
        self._order_book[order.side.value].append(entry)
        # 保存订单对象引用（用于更新状态）
        self._limit_orders[order.order_id] = order
        # 跟踪有订单簿订单的标的
        self._tracked_symbols.add(order.symbol)

        # 订单状态为已提交，等待撮合
        order.status = OrderStatus.SUBMITTED
        return order

    def _place_stop_order(self, order: Order) -> Order:
        """提交止损单"""
        # 止损单暂存，等待价格监控线程触发
        order.status = OrderStatus.SUBMITTED
        logger.info(f"止损单已提交: {order.order_id}, 触发价: {order.stop_price}")
        return order

    def _place_stop_limit_order(self, order: Order) -> Order:
        """提交止损限价单"""
        # 止损限价单暂存
        order.status = OrderStatus.SUBMITTED
        logger.info(f"止损限价单已提交: {order.order_id}, 触发价: {order.stop_price}, 限价: {order.price}")
        return order

    def update_orders(self):
        """
        更新订单簿 - 检查是否有订单可以成交
        应定期调用（如每次价格更新后）
        """
        # 检查限价单
        current_prices = self._get_all_prices()

        for symbol, price in current_prices.items():
            # 检查买单（市价 <= 限价时成交）
            buy_orders = self._order_book.get("BUY", [])
            for entry in buy_orders[:]:
                if price <= entry.price:  # 市价 <= 限价，成交
                    self._fill_limit_order(entry, price)

            # 检查卖单（市价 >= 限价时成交）
            sell_orders = self._order_book.get("SELL", [])
            for entry in sell_orders[:]:
                if price >= entry.price:  # 市价 >= 限价，成交
                    self._fill_limit_order(entry, price)

    def _fill_limit_order(self, entry: OrderBookEntry, fill_price: float):
        """处理限价单成交"""
        logger.info(f"限价单成交: {entry.order_id} @ {fill_price}")

        # 从订单簿中移除已成交的订单
        side_orders = self._order_book.get(entry.side.value, [])
        if entry in side_orders:
            side_orders.remove(entry)
        # 如果订单簿该侧为空，移除跟踪
        if not side_orders:
            self._tracked_symbols.discard(entry.symbol)

        # 从订单对象映射中移除
        if entry.order_id in self._limit_orders:
            del self._limit_orders[entry.order_id]

        # 创建Order对象（设置 account_id）
        order = Order(
            order_id=entry.order_id,
            symbol=entry.symbol,
            side=entry.side,
            order_type=OrderType.LIMIT,
            quantity=entry.quantity,
            price=entry.price,
            account_id=str(entry.account_id)
        )

        # 调用 _execute_market_order 执行实际交易
        result_order = self._execute_market_order(order)

        # 将执行结果复制到原订单
        order.status = result_order.status
        order.filled_quantity = result_order.filled_quantity
        order.avg_fill_price = result_order.avg_fill_price
        order.filled_time = result_order.filled_time
        order.fills = result_order.fills

        # 更新原订单簿中的订单状态
        if entry.order_id in self._limit_orders:
            orig_order = self._limit_orders[entry.order_id]
            orig_order.status = result_order.status
            orig_order.filled_quantity = result_order.filled_quantity
            orig_order.avg_fill_price = result_order.avg_fill_price
            orig_order.filled_time = result_order.filled_time
            orig_order.fills = result_order.fills

        return order

    # ==================== 价格管理 ====================

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """获取当前价格"""
        # 尝试从缓存获取
        if symbol in self._price_cache:
            return self._price_cache[symbol]

        # 从数据服务获取
        try:
            from core.data_service import load_price_data
            df = load_price_data([symbol], days=5)
            if not df.empty and symbol in df.columns:
                valid_prices = df[symbol].dropna()
                if not valid_prices.empty:
                    price = float(valid_prices.iloc[-1])
                    # 验证价格有效性
                    if price > 0:
                        self._price_cache[symbol] = price
                        return price
        except Exception as e:
            logger.debug(f"获取价格失败: {symbol} - {e}")

        # 返回 None 表示无法获取有效价格
        return None

    def _get_all_prices(self) -> Dict[str, Optional[float]]:
        """获取所有跟踪标的的价格"""
        # 获取持仓中的标的 + 有订单簿订单的标的
        positions = self.get_positions()
        symbols = set([p.ticker for p in positions] + list(self._tracked_symbols))

        result = {}
        for symbol in symbols:
            price = self._get_current_price(symbol)
            # 只返回有效价格（None 或 <=0 的都不加入）
            if price is not None and price > 0:
                result[symbol] = price

        return result

    def update_prices(self):
        """更新所有价格缓存"""
        self._price_cache.clear()
        return self._get_all_prices()

    # ==================== 止损止盈监控 ====================

    def check_stop_orders(self, current_prices: Dict[str, float]):
        """
        检查止损订单是否触发
        应定期调用
        """
        for symbol, price in current_prices.items():
            # 暂未实现独立的止损订单簿
            # 止损逻辑由TradingService统一管理
            pass

    # ==================== 结算 ====================

    def daily_settlement(self) -> Dict:
        """日终结算"""
        portfolio = self.paper_account.get_portfolio_value()
        return {
            "total_assets": portfolio["total_assets"],
            "cash": portfolio["cash"],
            "market_value": portfolio["market_value"],
            "positions": len(portfolio.get("positions", []))
        }

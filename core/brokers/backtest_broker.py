from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from core.interfaces.broker_adapter import BrokerAdapter, Position
from core.order_types import Order, OrderStatus, OrderSide, Fill

logger = logging.getLogger(__name__)

class BacktestBroker(BrokerAdapter):
    """
    In-memory Broker for Backtesting.
    Simulates execution without persistence.
    """
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {} 
        self.orders: Dict[str, Order] = {}
        self.fills: List[Fill] = []
        self.current_time = datetime.now()
        self.commission_rate = 0.0003 # Default 0.03%

    def connect(self) -> bool:
        return True
    
    def set_time(self, dt: datetime):
        self.current_time = dt

    def get_account_info(self) -> Dict[str, Any]:
        market_value = sum(p.market_value for p in self.positions.values())
        return {
            "total_assets": self.cash + market_value,
            "cash": self.cash,
            "market_value": market_value,
            "equity": self.cash + market_value,
            "currency": "CNY",
            "buying_power": self.cash
        }

    def get_positions(self) -> List[Position]:
        return list(self.positions.values())

    def place_order(self, order: Order) -> Order:
        order.submitted_time = self.current_time
        order.status = OrderStatus.SUBMITTED
        self.orders[order.order_id] = order
        return order

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            self.orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False

    def get_order_status(self, order_id: str) -> OrderStatus:
        if order_id in self.orders:
            return self.orders[order_id].status
        return OrderStatus.UNKNOWN

    def get_history(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        # Return fills as history
        return [f.to_dict() for f in self.fills]

    def match_orders(self, market_data: Dict[str, float]):
        """
        Process pending orders against current market data.
        To be called by BacktestEngine at each step.
        """
        for order_id, order in self.orders.items():
            if order.status != OrderStatus.SUBMITTED:
                continue
                
            price = market_data.get(order.symbol)
            if not price:
                continue
                
            # Execute
            quantity = order.quantity
            notional = price * quantity
            commission = notional * self.commission_rate
            
            if order.side == OrderSide.BUY:
                cost = notional + commission
                if self.cash >= cost:
                    self.cash -= cost
                    self._update_position(order.symbol, quantity, price)
                    self._create_fill(order, price, quantity, commission)
                    order.status = OrderStatus.FILLED
                else:
                    order.status = OrderStatus.REJECTED
                    logger.warning(f"Backtest Rejected BUY {order.symbol}: Insufficient funds")
                    
            elif order.side == OrderSide.SELL:
                pos = self.positions.get(order.symbol)
                if pos and pos.shares >= quantity:
                    proceeds = notional - commission
                    self.cash += proceeds
                    self._update_position(order.symbol, -quantity, price)
                    self._create_fill(order, price, quantity, commission)
                    order.status = OrderStatus.FILLED
                else:
                    order.status = OrderStatus.REJECTED
                    logger.warning(f"Backtest Rejected SELL {order.symbol}: Insufficient shares")

    def _update_position(self, ticker: str, delta_shares: float, current_price: float):
        pos = self.positions.get(ticker)
        if not pos:
            if delta_shares > 0:
                self.positions[ticker] = Position(
                    ticker=ticker,
                    shares=delta_shares,
                    avg_cost=current_price,
                    market_value=delta_shares * current_price,
                    unrealized_pnl=0.0
                )
        else:
            new_shares = pos.shares + delta_shares
            if new_shares <= 0:
                del self.positions[ticker]
            else:
                if delta_shares > 0:
                    # Update average cost
                    total_cost = pos.shares * pos.avg_cost + delta_shares * current_price
                    pos.avg_cost = total_cost / new_shares
                
                pos.shares = new_shares
                pos.market_value = new_shares * current_price
                pos.unrealized_pnl = (current_price - pos.avg_cost) * new_shares

    def _create_fill(self, order: Order, price: float, quantity: float, commission: float):
        fill = Fill(
            fill_id=f"FILL_{len(self.fills)+1}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=price,
            timestamp=self.current_time,
            commission=commission
        )
        self.fills.append(fill)
        order.fills.append(fill)
        order.filled_quantity = quantity
        order.avg_fill_price = price
        order.filled_time = self.current_time

from typing import Dict, List, Optional, Any
from datetime import datetime
from core.interfaces.broker_adapter import BrokerAdapter, Position
from core.order_types import Order, OrderStatus, OrderSide, OrderType, Fill
from core.paper_account import PaperAccount
import logging

logger = logging.getLogger(__name__)

class PaperBrokerAdapter(BrokerAdapter):
    """
    Paper Trading Broker Adapter
    Wraps the internal PaperAccount to provide a standard Broker interface.
    """
    
    def __init__(self, user_id: int, account_id: Optional[int] = None):
        self.paper_account = PaperAccount(user_id=user_id, account_id=account_id)
        # Ensure account is loaded
        if not self.paper_account.account_id:
             if not self.paper_account.load_default_account():
                 self.paper_account.create_account()

    def connect(self) -> bool:
        return True

    def get_account_info(self) -> Dict[str, Any]:
        portfolio = self.paper_account.get_portfolio_value()
        return {
            "total_assets": portfolio["total_assets"],
            "cash": portfolio["cash"],
            "market_value": portfolio["market_value"],
            "equity": portfolio["total_assets"],
            "currency": self.paper_account.currency,
            "buying_power": portfolio["cash"] # Simplified
        }

    def get_positions(self) -> List[Position]:
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

    def place_order(self, order: Order) -> Order:
        """
        Execute an order immediately against current market price.
        """
        logger.info(f"PaperBroker placing order: {order}")
        
        if order.order_type != OrderType.MARKET:
             # TODO: Support Limit/Stop orders in PaperAccount (requires pending order table)
             logger.warning(f"PaperBroker only supports MARKET orders for now. Rejected {order.order_type}")
             order.status = OrderStatus.REJECTED
             return order

        try:
            result = None
            if order.side == OrderSide.BUY:
                result = self.paper_account.buy(order.symbol, order.quantity)
            elif order.side == OrderSide.SELL:
                result = self.paper_account.sell(order.symbol, order.quantity)
            else:
                order.status = OrderStatus.REJECTED
                return order

            if result and result.get("success"):
                order.status = OrderStatus.FILLED
                order.filled_quantity = order.quantity
                order.avg_fill_price = result["price"]
                order.filled_time = datetime.now()
                order.remaining_quantity = 0
                
                # Create a Fill record
                fill = Fill(
                    fill_id=f"FILL_{datetime.now().timestamp()}",
                    order_id=order.order_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    price=result["price"],
                    timestamp=datetime.now(),
                    commission=result.get("cost", 0) - (result["price"] * order.quantity) if order.side == OrderSide.BUY else (result["price"] * order.quantity) - result.get("income", 0)
                )
                order.fills.append(fill)
            else:
                order.status = OrderStatus.FAILED
                
            return order
            
        except Exception as e:
            logger.error(f"PaperBroker order execution failed: {e}")
            order.status = OrderStatus.FAILED
            return order

    def cancel_order(self, order_id: str) -> bool:
        # Immediate execution means nothing to cancel
        return False

    def get_order_status(self, order_id: str) -> OrderStatus:
        # Without persistent order storage, we can't look up old orders by ID easily 
        # unless we add an Orders table to PaperAccount. 
        # For now, return UNKNOWN or assume FILLED if it was just placed.
        return OrderStatus.FILLED
    
    def get_history(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        return self.paper_account.get_trade_history()

from typing import Dict, List, Optional, Any
from core.interfaces.broker_adapter import BrokerAdapter, Position
from core.order_types import Order, OrderStatus
import logging

logger = logging.getLogger(__name__)

class MockRealBrokerAdapter(BrokerAdapter):
    """
    Mock Real Broker Adapter
    Simulates a connection to a real broker API (e.g. IBKR, Futu).
    Useful for testing the architecture without actual trading.
    """
    def connect(self) -> bool:
        logger.info("Connecting to Mock Real Broker...")
        return True

    def get_account_info(self) -> Dict[str, Any]:
        return {
            "total_assets": 1000000.0,
            "cash": 500000.0,
            "market_value": 500000.0,
            "equity": 1000000.0,
            "currency": "CNY",
            "buying_power": 500000.0
        }

    def get_positions(self) -> List[Position]:
        return [
            Position(ticker="000001.SZ", shares=1000, avg_cost=10.0, market_value=12000, unrealized_pnl=2000),
            Position(ticker="600519.SH", shares=100, avg_cost=1500.0, market_value=160000, unrealized_pnl=10000)
        ]

    def place_order(self, order: Order) -> Order:
        logger.info(f"Mock Broker received order: {order}")
        # Simulate successful submission
        order.status = OrderStatus.SUBMITTED
        return order

    def cancel_order(self, order_id: str) -> bool:
        logger.info(f"Mock Broker canceling order: {order_id}")
        return True

    def get_order_status(self, order_id: str) -> OrderStatus:
        return OrderStatus.FILLED
    
    def get_history(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        return []

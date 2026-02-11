from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from core.order_types import Order, OrderStatus

@dataclass
class Position:
    ticker: str
    shares: float
    avg_cost: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0

class BrokerAdapter(ABC):
    """
    Abstract Base Class for Broker Adapters.
    Defines the standard interface for interacting with different brokers (Paper, Real, etc.)
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the broker"""
        pass

    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """Get account summary (cash, equity, etc.)"""
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get current positions"""
        pass

    @abstractmethod
    def place_order(self, order: Order) -> Order:
        """Place a new order"""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get the status of an order"""
        pass
    
    @abstractmethod
    def get_history(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Get trade history"""
        pass

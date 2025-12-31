"""订单类型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid


class OrderType(Enum):
    """订单类型"""
    MARKET = "MARKET"  # 市价单
    LIMIT = "LIMIT"  # 限价单
    STOP = "STOP"  # 止损单
    STOP_LIMIT = "STOP_LIMIT"  # 止损限价单


class OrderSide(Enum):
    """订单方向"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "PENDING"  # 待提交
    SUBMITTED = "SUBMITTED"  # 已提交
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # 部分成交
    FILLED = "FILLED"  # 全部成交
    CANCELLED = "CANCELLED"  # 已撤销
    REJECTED = "REJECTED"  # 已拒绝
    EXPIRED = "EXPIRED"  # 已过期
    FAILED = "FAILED"  # 失败


class TimeInForce(Enum):
    """订单有效期"""
    DAY = "DAY"  # 当日有效
    GTC = "GTC"  # 撤销前有效（Good Till Cancel）
    IOC = "IOC"  # 立即成交或撤销（Immediate Or Cancel）
    FOK = "FOK"  # 全部成交或撤销（Fill Or Kill）


@dataclass
class Fill:
    """成交记录"""
    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    timestamp: datetime
    commission: float = 0.0
    exchange: Optional[str] = None
    
    @property
    def notional(self) -> float:
        """成交金额"""
        return float(self.quantity * self.price)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "commission": self.commission,
            "notional": self.notional,
            "exchange": self.exchange,
        }


@dataclass
class Order:
    """订单类"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float] = None  # 限价单价格
    stop_price: Optional[float] = None  # 止损单触发价格
    time_in_force: TimeInForce = TimeInForce.DAY
    status: OrderStatus = OrderStatus.PENDING
    created_time: datetime = field(default_factory=datetime.now)
    submitted_time: Optional[datetime] = None
    filled_time: Optional[datetime] = None
    cancelled_time: Optional[datetime] = None
    filled_quantity: int = 0
    remaining_quantity: int = 0
    avg_fill_price: float = 0.0
    total_commission: float = 0.0
    fills: List[Fill] = field(default_factory=list)
    client_order_id: Optional[str] = None
    strategy_id: Optional[str] = None
    account_id: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.remaining_quantity == 0:
            self.remaining_quantity = self.quantity
    
    @property
    def notional(self) -> float:
        """订单金额（基于限价或估算）"""
        if self.price:
            return float(self.quantity * self.price)
        return 0.0
    
    @property
    def filled_notional(self) -> float:
        """已成交金额"""
        return sum(fill.notional for fill in self.fills)
    
    def add_fill(self, fill: Fill) -> bool:
        """添加成交记录"""
        if fill.order_id != self.order_id:
            return False
        
        self.fills.append(fill)
        self.filled_quantity += fill.quantity
        self.remaining_quantity = self.quantity - self.filled_quantity
        self.total_commission += fill.commission
        
        # 更新平均成交价
        if self.filled_quantity > 0:
            self.avg_fill_price = self.filled_notional / self.filled_quantity
        
        # 更新状态
        if self.remaining_quantity == 0:
            self.status = OrderStatus.FILLED
            self.filled_time = datetime.now()
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIALLY_FILLED
        
        return True
    
    def update_status(self, status: OrderStatus, error_message: Optional[str] = None):
        """更新订单状态"""
        self.status = status
        if error_message:
            self.error_message = error_message
        
        if status == OrderStatus.SUBMITTED:
            self.submitted_time = datetime.now()
        elif status == OrderStatus.CANCELLED:
            self.cancelled_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force.value,
            "status": self.status.value,
            "created_time": self.created_time.isoformat(),
            "submitted_time": self.submitted_time.isoformat() if self.submitted_time else None,
            "filled_time": self.filled_time.isoformat() if self.filled_time else None,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "avg_fill_price": self.avg_fill_price,
            "total_commission": self.total_commission,
            "notional": self.notional,
            "filled_notional": self.filled_notional,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "fill_count": len(self.fills),
        }


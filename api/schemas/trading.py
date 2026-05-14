"""Trading API request models — extracted from routers/trading.py."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

class SubmitOrderRequest(BaseModel):
    """提交订单请求"""
    account_id: int = Field(..., description="账户ID")
    symbol: str = Field(..., description="标的代码")
    side: str = Field(..., description="方向: BUY/SELL")
    order_type: str = Field(default="MARKET", description="订单类型: MARKET/LIMIT/STOP/STOP_LIMIT")
    quantity: int = Field(..., ge=1, description="数量")
    price: Optional[float] = Field(default=None, description="限价（限价单必需）")
    stop_price: Optional[float] = Field(default=None, description="止损价（止损单必需）")
    strategy_id: Optional[str] = Field(default=None, description="策略ID")

class OrderUpdateRequest(BaseModel):
    """修改订单请求"""
    quantity: Optional[int] = Field(default=None, description="新数量")
    price: Optional[float] = Field(default=None, description="新价格（限价单）")

class CreateAccountRequest(BaseModel):
    """创建账户请求"""
    name: str = Field(..., description="账户名称")
    initial_balance: float = Field(default=100000.0, description="初始资金")

class ResetAccountRequest(BaseModel):
    """重置账户请求"""
    initial_balance: float = Field(default=100000.0, gt=0, description="重置后的初始资金")
    account_name: Optional[str] = Field(default=None, description="可选的新账户名称")

class AutoTradingConfigUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    username: Optional[str] = None
    account_name: Optional[str] = None
    initial_capital: Optional[float] = Field(default=None, gt=0)
    strategy_ids: Optional[List[str]] = None
    universe_mode: Optional[str] = None
    universe: Optional[List[str]] = None
    universe_limit: Optional[int] = Field(default=None, ge=0, le=6000)
    max_positions: Optional[int] = Field(default=None, ge=1, le=20)
    evaluation_days: Optional[int] = Field(default=None, ge=30, le=720)
    min_total_return: Optional[float] = None
    min_sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = Field(default=None, ge=0, le=1)
    top_n_strategies: Optional[int] = Field(default=None, ge=1, le=10)

class AutoTradingRunRequest(BaseModel):
    reset_account: bool = False
    initial_balance: Optional[float] = Field(default=None, gt=0)

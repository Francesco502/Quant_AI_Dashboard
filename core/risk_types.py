"""风险管理类型定义"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskAction(Enum):
    """风险检查结果动作"""
    ALLOW = "allow"  # 允许
    WARN = "warn"  # 警告但允许
    REJECT = "reject"  # 拒绝
    EMERGENCY_STOP = "emergency_stop"  # 紧急停止


class AlertSeverity(Enum):
    """告警严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class RiskLimits:
    """风险限制配置"""
    max_position_size: float = 0.1  # 单仓位最大10%
    max_total_exposure: float = 0.95  # 总敞口最大95%
    max_sector_exposure: float = 0.3  # 单行业最大30%
    max_single_stock: float = 0.05  # 单股票最大5%
    max_daily_loss: float = 0.05  # 单日最大亏损5%
    max_total_loss: float = 0.2  # 总亏损最大20%
    stop_loss_threshold: float = 0.08  # 止损阈值8%
    max_correlation: float = 0.8  # 最大相关性阈值
    min_liquidity_ratio: float = 0.1  # 最小流动性比例


@dataclass
class RiskCheckResult:
    """风险检查结果"""
    action: RiskAction
    risk_level: RiskLevel
    message: str
    violations: list[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.violations is None:
            self.violations = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class RiskEvent:
    """风险事件"""
    event_id: str
    timestamp: datetime
    event_type: str
    severity: AlertSeverity
    message: str
    symbol: Optional[str] = None
    portfolio_id: Optional[str] = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class PositionLimit:
    """仓位限制"""
    symbol: str
    max_position: float  # 最大持仓数量
    max_weight: float  # 最大权重（占组合比例）
    max_value: Optional[float] = None  # 最大市值（可选）


@dataclass
class StopLossRule:
    """止损规则"""
    symbol: str
    stop_type: str  # 'fixed', 'trailing', 'percentage'
    stop_price: Optional[float] = None  # 固定止损价格
    stop_percentage: Optional[float] = None  # 百分比止损
    trailing_distance: Optional[float] = None  # 跟踪止损距离
    entry_price: float = 0.0  # 入场价格
    enabled: bool = True


@dataclass
class TakeProfitRule:
    """止盈规则"""
    symbol: str
    take_profit_type: str  # 'fixed', 'percentage'
    take_profit_price: Optional[float] = None  # 固定止盈价格
    take_profit_percentage: Optional[float] = None  # 百分比止盈
    entry_price: float = 0.0  # 入场价格
    enabled: bool = True


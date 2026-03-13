"""
核心逻辑模块：
- forecasting: 时序预测（当前为轻量级 Demo，可替换为 LSTM/Transformer）
- portfolio: 组合优化（Markowitz 均值-方差 + 夏普比率）
- tuning: 自动化调参（网格搜索 + 贝叶斯优化）
- external: 外部数据源（宏观经济、行业轮动、市场情绪、资金流向）
"""

# 导出版本信息
from .version import VERSION, __version__, get_version, get_version_info

__all__ = [
    "VERSION",
    "__version__",
    "get_version",
    "get_version_info",
]

# 阶段一：基础设施升级 - 新增模块
from .feature_store import FeatureStore, get_feature_store

# 阶段二：特征工程增强 - 新增子模块
from .features.basic import VolatilityFeatures, TrendFeatures
from .features.advanced import (
    MomentumFeatures,
    EfficiencyFeatures,
    MeanReversionFeatures,
)

from .signal_store import SignalStore, get_signal_store

# 阶段二：训练/预测解耦 - 新增模块
from .training_pipeline import TrainingPipeline

# 阶段三：策略与AI融合 - 新增模块
from .strategy_framework import (
    BaseStrategy,
    TechnicalStrategy,
    AIStrategy,
    EnsembleStrategy,
    StrategySignal,
)
from .strategy_manager import StrategyManager, get_strategy_manager

# 阶段一新增：持仓分析
from .portfolio_analyzer import PortfolioAnalyzer
from .decision_dashboard import DecisionDashboard, get_decision_dashboard

# 阶段四：完整信号执行闭环 - 新增模块
from .signal_executor import SignalExecutor, RiskChecker, get_signal_executor

# 阶段五：风险管理模块 - 新增模块
from .risk_types import (
    RiskLimits,
    RiskCheckResult,
    RiskAction,
    RiskLevel,
    AlertSeverity,
    PositionLimit,
    StopLossRule,
    TakeProfitRule,
    RiskEvent,
)
from .risk_monitor import RiskMonitor
from .position_manager import PositionManager, SectorInfo
from .stop_loss_manager import StopLossManager
from .risk_alerting import RiskAlerting
# 订单管理模块
from .order_types import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    Fill,
)
from .order_manager import OrderManager
# 滑点模型
from .slippage_model import SlippageModel, SlippageConfig
# 执行算法
from .execution_algorithms import ExecutionAlgorithm, get_execution_algorithm
# 数据质量模块
from .data_validation import (
    DataValidator,
    ValidationRule,
    ValidationResult,
)
from .data_repair import (
    DataRepair,
    RepairStrategy,
    RepairResult,
)
from .data_versioning import DataVersionManager
# 性能优化模块
from .database import Database, get_database
from .multi_level_cache import (
    MultiLevelCache,
    MemoryCache,
    DiskCache,
    get_cache,
)
from .async_data_service import (
    AsyncDataService,
    fetch_multiple_tickers_async,
    fetch_multiple_tickers_sync,
)
from .data_store_adapter import DataStoreAdapter, get_data_store_adapter
# 安全性模块
from .rbac import Role, Permission, RBAC, get_rbac
from .audit_log import AuditAction, AuditLogger, get_audit_logger
# 监控模块
from .monitoring import (
    SystemMonitor,
    MetricsCollector,
    HealthChecker,
    HealthStatus,
    AlertManager,
    AlertRule,
    AlertSeverity,
    ComparisonOperator,
)
# 性能监控
from .memory_monitor import MemoryMonitor, get_memory_monitor, check_and_cleanup
from .trading_calendar import TradingCalendar, get_trading_calendar, is_trading_day

# 阶段六：外部数据源模块 - 新增
from .data.external import (
    EconomicDataLoader,
    IndustryDataLoader,
    SentimentDataLoader,
    FlowDataLoader,
    ExternalDataLoader,
)
from .data_service import (
    load_external_data,
    merge_price_with_external,
    get_external_features,
    get_economic_summary,
    get_industry_summary,
    get_sentiment_summary,
    get_flow_summary,
)

# 阶段七：自动化调参模块 - 新增
from .tuner import (
    auto_tune,
    quick_tune,
    precise_tune,
    get_tuning_results,
    load_best_params,
    tune_and_update_registry,
    compare_tuning_results,
)
from .tuning.grid_search import (
    grid_search,
    get_quick_grid,
    get_full_grid,
)
from .tuning.bayesian_opt import (
    bayesian_search,
    get_bayesian_space,
)

__all__ = [
    "FeatureStore",
    "get_feature_store",
    # 特征工程子模块
    "VolatilityFeatures",
    "TrendFeatures",
    "MomentumFeatures",
    "EfficiencyFeatures",
    "MeanReversionFeatures",
    "SignalStore",
    "get_signal_store",
    "TrainingPipeline",
    "BaseStrategy",
    "TechnicalStrategy",
    "AIStrategy",
    "EnsembleStrategy",
    "StrategySignal",
    "StrategyManager",
    "get_strategy_manager",
    # 阶段一新增：持仓分析
    "PortfolioAnalyzer",
    "DecisionDashboard",
    "get_decision_dashboard",
    "SignalExecutor",
    "RiskChecker",
    "get_signal_executor",
    # 风险管理模块
    "RiskLimits",
    "RiskCheckResult",
    "RiskAction",
    "RiskLevel",
    "AlertSeverity",
    "PositionLimit",
    "StopLossRule",
    "TakeProfitRule",
    "RiskEvent",
    "RiskMonitor",
    "PositionManager",
    "SectorInfo",
    "StopLossManager",
    "RiskAlerting",
    # 订单管理模块
    "Order",
    "OrderType",
    "OrderSide",
    "OrderStatus",
    "TimeInForce",
    "Fill",
    "OrderManager",
    # 滑点模型
    "SlippageModel",
    "SlippageConfig",
    # 执行算法
    "ExecutionAlgorithm",
    "get_execution_algorithm",
    # 数据质量模块
    "DataValidator",
    "ValidationRule",
    "ValidationResult",
    "DataRepair",
    "RepairStrategy",
    "RepairResult",
    "DataVersionManager",
    # 性能优化模块
    "Database",
    "get_database",
    "MultiLevelCache",
    "MemoryCache",
    "DiskCache",
    "get_cache",
    "AsyncDataService",
    "fetch_multiple_tickers_async",
    "fetch_multiple_tickers_sync",
    "DataStoreAdapter",
    "get_data_store_adapter",
    # 安全性模块
    "Role",
    "Permission",
    "RBAC",
    "get_rbac",
    "AuditAction",
    "AuditLogger",
    "get_audit_logger",
    # 监控模块
    "SystemMonitor",
    "MetricsCollector",
    "HealthChecker",
    "HealthStatus",
    "AlertManager",
    "AlertRule",
    "AlertSeverity",
    "ComparisonOperator",
    # 性能监控
    "MemoryMonitor",
    "get_memory_monitor",
    "check_and_cleanup",
    "TradingCalendar",
    "get_trading_calendar",
    "is_trading_day",
    # 阶段六：自动化调参模块 - 新增
    "auto_tune",
    "quick_tune",
    "precise_tune",
    "get_tuning_results",
    "load_best_params",
    "tune_and_update_registry",
    "compare_tuning_results",
    "grid_search",
    "get_quick_grid",
    "get_full_grid",
    "bayesian_search",
    "get_bayesian_space",
    # 阶段七：外部数据源模块 - 新增
    "EconomicDataLoader",
    "IndustryDataLoader",
    "SentimentDataLoader",
    "FlowDataLoader",
    "ExternalDataLoader",
    "load_external_data",
    "merge_price_with_external",
    "get_external_features",
    "get_economic_summary",
    "get_industry_summary",
    "get_sentiment_summary",
    "get_flow_summary",
]


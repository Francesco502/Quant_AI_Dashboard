"""交易引擎模块单元测试 - 补充测试"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock
from typing import Dict, List

from core.trading_engine import TradingEngine, apply_equal_weight_rebalance
from core.risk_monitor import RiskMonitor
from core.risk_types import RiskAction, RiskLevel, RiskCheckResult
from core.order_types import Order, OrderType, OrderSide, OrderStatus, Fill
from core.broker_simulator import Trade
from core.account import ensure_account_dict


class MockBroker:
    """模拟 Broker 用于测试"""

    def __init__(self, initial_cash: float = 100000):
        self.cash = initial_cash
        self.positions: List[Dict] = []
        self.orders: List[Order] = []
        self.current_price: Dict[str, float] = {}

    def set_current_price(self, ticker: str, price: float):
        self.current_price[ticker] = price

    def get_positions(self):
        return [DictWrapper(**p) for p in self.positions]

    def get_account_info(self):
        total_assets = self.cash
        for pos in self.positions:
            price = self.current_price.get(pos.get("ticker", ""), 0)
            total_assets += pos.get("shares", 0) * price
        return {"cash": self.cash, "total_assets": total_assets, "equity": total_assets}

    def place_order(self, order):
        self.orders.append(order)

        if order.side == OrderSide.BUY:
            price = order.price or self.current_price.get(order.symbol, 0)
            cost = price * order.quantity
            if cost <= self.cash:
                self.cash -= cost
                existing = next((p for p in self.positions if p["ticker"] == order.symbol), None)
                if existing:
                    existing["shares"] += order.quantity
                else:
                    self.positions.append({"ticker": order.symbol, "shares": order.quantity})

        return Order(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price or 0,
            status=OrderStatus.FILLED
        )


class DictWrapper:
    """字典包装器"""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestTradingEngineExtra:
    """交易引擎补充测试"""

    @pytest.fixture
    def broker(self):
        return MockBroker(initial_cash=100000)

    @pytest.fixture
    def risk_monitor(self):
        monitor = MagicMock()
        monitor.check_order_risk.return_value = RiskCheckResult(
            action=RiskAction.ALLOW,
            risk_level=RiskLevel.LOW,
            message="通过",
            violations=[]
        )
        return monitor

    @pytest.fixture
    def engine(self, broker, risk_monitor):
        return TradingEngine(broker=broker, risk_monitor=risk_monitor)

    def test_execute_rebalance_buy(self, engine):
        """验证执行调仓 - 买入"""
        prices = {"600519": 100.0}
        target_positions = {"600519": 100}

        orders, messages = engine.execute_rebalance(target_positions, prices)

        assert len(orders) == 1
        assert orders[0].symbol == "600519"
        assert orders[0].side == OrderSide.BUY

    def test_execute_rebalance_no_change(self, engine):
        """验证执行调仓 - 无需变化"""
        engine.broker.positions = [{"ticker": "600519", "shares": 100}]

        target_positions = {"600519": 100}
        orders, messages = engine.execute_rebalance(target_positions, {})

        assert len(orders) == 0

    def test_execute_rebalance_risk_reject(self, engine, risk_monitor):
        """验证执行调仓 - 风控拒绝"""
        prices = {"600519": 100.0}
        target_positions = {"600519": 100}

        risk_monitor.check_order_risk.return_value = RiskCheckResult(
            action=RiskAction.REJECT,
            risk_level=RiskLevel.HIGH,
            message="仓位超限",
            violations=["仓位超限"]
        )

        orders, messages = engine.execute_rebalance(target_positions, prices)

        assert len(orders) == 0
        # 检查是否包含拒绝消息（英文实现）
        assert any("Risk Rejected" in msg for msg in messages)


class TestEqualWeightRebalanceExtra:
    """等权调仓补充测试"""

    @pytest.fixture
    def account(self):
        return ensure_account_dict({
            "cash": 100000.0,
            "positions": {},
            "initial_capital": 100000.0
        })

    @pytest.fixture
    def signal_table(self):
        return pd.DataFrame({
            "ticker": ["600519", "000001"],
            "action": ["买入", "买入"],
            "combined_signal": [0.8, 0.7],
            "last_price": [100.0, 50.0]
        })

    @pytest.fixture
    def price_data(self):
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        return pd.DataFrame({
            "600519": np.linspace(100, 120, 100),
            "000001": np.linspace(50, 60, 100),
        }, index=dates)

    def test_rebalance_executes_trades(self, account, signal_table, price_data):
        """验证调仓执行交易"""
        result_account, msg = apply_equal_weight_rebalance(
            account=account,
            signal_table=signal_table,
            data=price_data,
            total_capital=100000.0,
            max_positions=10
        )

        assert "调仓" in msg
        assert len(result_account.get("positions", {})) > 0

    def test_rebalance_with_risk_monitor_reject(self, account, signal_table, price_data):
        """验证带风险监控的调仓 - 拒绝"""
        risk_monitor = MagicMock()
        risk_monitor.check_order_risk.return_value = RiskCheckResult(
            action=RiskAction.REJECT,
            risk_level=RiskLevel.HIGH,
            message="仓位超限",
            violations=[]
        )

        result_account, msg = apply_equal_weight_rebalance(
            account=account,
            signal_table=signal_table,
            data=price_data,
            total_capital=100000.0,
            max_positions=10,
            risk_monitor=risk_monitor
        )

        # 所有交易被拒绝
        assert "所有交易均未通过风险检查" in msg

    def test_rebalance_with_risk_monitor_emergency_stop(self, account, signal_table, price_data):
        """验证带风险监控的调仓 - 紧急停止"""
        risk_monitor = MagicMock()
        risk_monitor.check_order_risk.return_value = RiskCheckResult(
            action=RiskAction.EMERGENCY_STOP,
            risk_level=RiskLevel.CRITICAL,
            message="总亏损超限",
            violations=[]
        )

        result_account, msg = apply_equal_weight_rebalance(
            account=account,
            signal_table=signal_table,
            data=price_data,
            total_capital=100000.0,
            max_positions=10,
            risk_monitor=risk_monitor
        )

        assert "触发紧急停止" in msg

    def test_rebalance_empty_signal(self, account, price_data):
        """验证空信号调仓"""
        empty_signal = pd.DataFrame(columns=["ticker", "action", "combined_signal", "last_price"])

        result_account, msg = apply_equal_weight_rebalance(
            account=account,
            signal_table=empty_signal,
            data=price_data,
            total_capital=100000.0,
            max_positions=10
        )

        assert "无有效信号" in msg or "未执行调仓" in msg

    def test_rebalance_none_signal(self, account, price_data):
        """验证None信号调仓"""
        result_account, msg = apply_equal_weight_rebalance(
            account=account,
            signal_table=None,
            data=price_data,
            total_capital=100000.0,
            max_positions=10
        )

        assert "无有效信号" in msg


class TestAccountUtils:
    """账户工具函数测试"""

    def test_ensure_account_dict_with_data(self):
        """验证带数据的账户字典保证"""
        data = {
            "cash": 500000.0,
            "positions": {"AAPL": 100},
            "initial_capital": 1000000.0
        }

        account = ensure_account_dict(data)

        assert account["cash"] == 500000.0
        assert "AAPL" in account["positions"]

    def test_ensure_account_dict_empty(self):
        """验证空账户字典保证"""
        account = ensure_account_dict(None)

        assert account["cash"] == 1000000.0
        assert len(account["positions"]) == 0

    def test_compute_equity(self):
        """验证权益计算"""
        from core.account import compute_equity

        account = {
            "cash": 500000.0,
            "positions": {"AAPL": 100}
        }

        prices = {"AAPL": 150.0}

        equity = compute_equity(account, prices)

        # 500000 + 100 * 150 = 515000
        assert equity == 515000.0


class TestRiskMonitorIntegration:
    """风险监控集成测试"""

    def test_risk_check_workflow(self):
        """验证完整风险检查流程"""
        monitor = RiskMonitor()

        account = {
            "cash": 1000000.0,
            "positions": {},
            "initial_capital": 1000000.0
        }

        prices = {"600519": 100.0}

        # 正常检查
        order = {
            "symbol": "600519",
            "side": "BUY",
            "quantity": 100,
            "price": 100.0
        }

        result = monitor.check_order_risk(order, account, prices)

        assert result.action == RiskAction.ALLOW

        # 触发紧急停止
        account["cash"] = 500000.0  # 亏损50%
        result = monitor.check_order_risk(order, account, prices)

        assert result.action == RiskAction.EMERGENCY_STOP


    def test_full_risk_check_workflow(self):
        """验证完整风险检查流程 - 独立测试"""
        monitor = RiskMonitor()

        account = {
            "cash": 1000000.0,
            "positions": {},
            "initial_capital": 1000000.0
        }

        prices = {"600519": 100.0}

        # 正常检查
        order = {
            "symbol": "600519",
            "side": "BUY",
            "quantity": 100,
            "price": 100.0
        }

        result = monitor.check_order_risk(order, account, prices)
        assert result.action == RiskAction.ALLOW

        # 触发紧急停止
        account["cash"] = 500000.0
        result = monitor.check_order_risk(order, account, prices)
        assert result.action == RiskAction.EMERGENCY_STOP


class TestPositionManager:
    """仓位管理器测试"""

    @pytest.fixture
    def manager(self):
        from core.position_manager import PositionManager
        return PositionManager()

    @pytest.fixture
    def portfolio(self):
        return {
            "cash": 1000000,
            "positions": {},
            "initial_capital": 1000000
        }

    @pytest.fixture
    def prices(self):
        return {"600519": 100.0, "AAPL": 150.0}

    def test_check_position_limit_pass(self, manager, portfolio, prices):
        """验证仓位限制检查通过"""
        passed, msg = manager.check_position_limit(
            symbol="600519",
            quantity=100,
            portfolio=portfolio,
            current_prices=prices
        )

        assert passed is True

    def test_check_position_limit_with_limit(self, manager, portfolio, prices):
        """验证仓位限制检查 - 有配置限制"""
        from core.risk_types import PositionLimit

        manager.add_position_limit(PositionLimit(
            symbol="600519",
            max_position=50,
            max_weight=0.02
        ))

        passed, msg = manager.check_position_limit(
            symbol="600519",
            quantity=100,  # 超出限制
            portfolio=portfolio,
            current_prices=prices
        )

        assert passed is False

    def test_calculate_total_position_weight(self, manager, portfolio, prices):
        """验证总仓位权重计算"""
        portfolio["positions"] = {"600519": 100}

        equity = 1000000 + 100 * 100  # 1020000
        weight = manager._calculate_total_position_weight(portfolio, prices, equity)

        # 10000 / 1020000 ≈ 0.0098
        assert 0 < weight < 0.02


class TestPositionManagerSector:
    """仓位管理器行业测试"""

    @pytest.fixture
    def manager(self):
        from core.position_manager import PositionManager, SectorInfo
        manager = PositionManager()
        manager.sector_info = {
            "600519": SectorInfo(symbol="600519", sector="消费", market="A股"),
            "601318": SectorInfo(symbol="601318", sector="金融", market="A股")
        }
        manager.set_sector_limit("消费", 0.2)
        return manager

    @pytest.fixture
    def portfolio(self):
        return {
            "cash": 1000000,
            "positions": {},
            "initial_capital": 1000000
        }

    @pytest.fixture
    def prices(self):
        return {"600519": 100.0, "601318": 50.0}

    def test_sector_weight_calculation(self, manager, portfolio, prices):
        """验证行业权重计算"""
        portfolio["positions"] = {"600519": 100}

        equity = 1000000 + 100 * 100  # 1020000

        weight = manager._calculate_sector_weight("消费", portfolio, prices, equity)

        # 10000 / 1020000 ≈ 0.0098
        assert 0 < weight < 0.02

    def test_check_position_limit_sector(self, manager, portfolio, prices):
        """验证仓位限制检查 - 行业限制"""
        passed, msg = manager.check_position_limit(
            symbol="601318",
            quantity=100,
            portfolio=portfolio,
            current_prices=prices
        )

        assert passed is True


class TestRiskEvent:
    """风险事件测试"""

    def test_risk_event_creation(self):
        """验证风险事件创建"""
        from core.risk_types import RiskEvent, AlertSeverity
        from datetime import datetime

        event = RiskEvent(
            event_id="test_123",
            timestamp=datetime.now(),
            event_type="order_check",
            severity=AlertSeverity.WARNING,
            message="测试事件",
            symbol="600519"
        )

        assert event.event_id == "test_123"
        assert event.severity == AlertSeverity.WARNING
        assert event.symbol == "600519"

    def test_risk_event_default_details(self):
        """验证风险事件默认details"""
        from core.risk_types import RiskEvent, AlertSeverity

        event = RiskEvent(
            event_id="test_123",
            timestamp=datetime.now(),
            event_type="order_check",
            severity=AlertSeverity.INFO,
            message="测试"
        )

        assert event.details == {}


class TestRiskCheckResult:
    """风险检查结果测试"""

    def test_risk_check_result_default_violations(self):
        """验证风险检查结果默认violations"""
        from core.risk_types import RiskCheckResult, RiskAction, RiskLevel

        result = RiskCheckResult(
            action=RiskAction.ALLOW,
            risk_level=RiskLevel.LOW,
            message="通过"
        )

        assert result.violations == []

    def test_risk_check_result_with_violations(self):
        """验证风险检查结果带violations"""
        from core.risk_types import RiskCheckResult, RiskAction, RiskLevel

        result = RiskCheckResult(
            action=RiskAction.REJECT,
            risk_level=RiskLevel.HIGH,
            message="失败",
            violations=["仓位超限", "流动性不足"]
        )

        assert len(result.violations) == 2


class TestTradeSimulation:
    """交易模拟测试"""

    def test_trade_creation(self):
        """验证交易创建"""
        trade = Trade(
            ticker="600519",
            side="BUY",
            shares=100,
            price=100.0
        )

        assert trade.ticker == "600519"
        assert trade.side == "BUY"
        assert trade.shares == 100

    def test_trade_to_log_item(self):
        """验证交易日志项转换 - 使用中文键"""
        from datetime import datetime

        trade = Trade(
            ticker="600519",
            side="BUY",
            shares=100,
            price=100.0
        )

        log_item = trade.to_log_item(datetime.now())

        # 实现中使用中文键
        assert "代码" in log_item
        assert "方向" in log_item
        assert "数量" in log_item

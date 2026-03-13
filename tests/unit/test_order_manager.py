"""订单管理器单元测试"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.order_types import Order, OrderSide, OrderType, OrderStatus, TimeInForce, Fill
from core.order_manager import OrderManager
from core.database import get_database


@pytest.fixture(scope="module")
def db():
    """获取测试数据库"""
    return get_database(":memory:")


@pytest.fixture
def order_manager(db):
    """获取订单管理器"""
    return OrderManager(db)


class TestOrderManager:
    """订单管理器测试类"""

    def test_create_order_market(self, order_manager):
        """测试创建市价单"""
        order = order_manager.create_order(
            account_id=1,
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )

        assert order.order_id is not None
        assert order.symbol == "600000"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.quantity == 100
        assert order.status == OrderStatus.PENDING

    def test_create_order_limit(self, order_manager):
        """测试创建限价单"""
        order = order_manager.create_order(
            account_id=1,
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=10.50
        )

        assert order.order_id is not None
        assert order.price == 10.50

    def test_create_order_stop(self, order_manager):
        """测试创建止损单"""
        order = order_manager.create_order(
            account_id=1,
            symbol="600000",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=100,
            stop_price=9.50
        )

        assert order.order_id is not None
        assert order.stop_price == 9.50

    def test_create_order_stop_limit(self, order_manager):
        """测试创建止损限价单"""
        order = order_manager.create_order(
            account_id=1,
            symbol="600000",
            side=OrderSide.SELL,
            order_type=OrderType.STOP_LIMIT,
            quantity=100,
            stop_price=9.50,
            price=9.60
        )

        assert order.order_id is not None
        assert order.stop_price == 9.50
        assert order.price == 9.60

    def test_submit_order(self, order_manager):
        """测试提交订单"""
        order = order_manager.create_order(
            account_id=1,
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )

        result = order_manager.submit_order(order.order_id)
        assert result is True

        loaded_order = order_manager.get_order(order.order_id)
        assert loaded_order.status == OrderStatus.SUBMITTED

    def test_cancel_order(self, order_manager):
        """测试取消订单"""
        order = order_manager.create_order(
            account_id=1,
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )

        # 取消待提交订单
        result = order_manager.cancel_order(order.order_id, reason="用户取消")
        assert result is True

        loaded_order = order_manager.get_order(order.order_id)
        assert loaded_order.status == OrderStatus.CANCELLED

    def test_modify_order(self, order_manager):
        """测试修改订单"""
        order = order_manager.create_order(
            account_id=1,
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=10.50
        )

        result = order_manager.modify_order(order.order_id, quantity=200, price=10.80)
        assert result is True

        loaded_order = order_manager.get_order(order.order_id)
        assert loaded_order.quantity == 200
        assert loaded_order.price == 10.80

    def test_add_fill(self, order_manager):
        """测试添加成交记录"""
        order = order_manager.create_order(
            account_id=1,
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )

        order_manager.submit_order(order.order_id)

        fill = Fill(
            fill_id=f"FILL_{datetime.now().timestamp()}",
            order_id=order.order_id,
            symbol="600000",
            side=OrderSide.BUY,
            quantity=100,
            price=10.50,
            timestamp=datetime.now(),
            commission=0.003 * 100 * 10.50
        )

        result = order_manager.add_fill(order.order_id, fill)
        assert result is True

        loaded_order = order_manager.get_order(order.order_id)
        assert loaded_order.status == OrderStatus.FILLED
        assert loaded_order.filled_quantity == 100

    def test_get_orders_by_account(self, order_manager):
        """测试按账户查询订单"""
        # 创建多个订单
        for i in range(3):
            order = order_manager.create_order(
                account_id=1,
                symbol=f"60000{i}",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=100
            )
            order_manager.submit_order(order.order_id)

        orders = order_manager.get_orders_by_account(1)
        assert len(orders) >= 3

    def test_get_active_orders(self, order_manager):
        """测试获取活跃订单"""
        # 创建并提交订单
        for i in range(3):
            order = order_manager.create_order(
                account_id=1,
                symbol=f"60000{i}",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=100
            )
            order_manager.submit_order(order.order_id)

        # 创建已 cancel 的订单
        order = order_manager.create_order(
            account_id=1,
            symbol="600099",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )
        order_manager.cancel_order(order.order_id, reason="取消")

        active_orders = order_manager.get_active_orders(1)
        assert len(active_orders) >= 3


class TestOrderTypes:
    """订单类型测试"""

    def test_order_to_dict(self):
        """测试订单转字典"""
        order = Order(
            order_id="TEST001",
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )

        order_dict = order.to_dict()
        assert order_dict["order_id"] == "TEST001"
        assert order_dict["symbol"] == "600000"
        assert order_dict["side"] == "BUY"

    def test_order_add_fill(self):
        """测试订单添加成交"""
        order = Order(
            order_id="TEST001",
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )

        fill = Fill(
            fill_id="FILL001",
            order_id="TEST001",
            symbol="600000",
            side=OrderSide.BUY,
            quantity=50,
            price=10.50,
            timestamp=datetime.now(),
            commission=0.0
        )

        order.add_fill(fill)
        assert order.filled_quantity == 50
        assert order.remaining_quantity == 50
        assert order.avg_fill_price == 10.50

    def test_fill_notional(self):
        """测试成交金额计算"""
        fill = Fill(
            fill_id="FILL001",
            order_id="TEST001",
            symbol="600000",
            side=OrderSide.BUY,
            quantity=100,
            price=10.50,
            timestamp=datetime.now()
        )

        assert fill.notional == 1050.0


class TestStopLossRules:
    """止损止盈规则测试"""

    def test_set_stop_loss(self, order_manager):
        """测试设置止损规则"""
        order_manager.set_stop_loss(
            account_id=1,
            symbol="600000",
            entry_price=10.00,
            stop_type="percentage",
            stop_percentage=0.05
        )

        rules = order_manager.get_active_stop_rules(1)
        assert len(rules) >= 1

    def test_remove_stop_loss(self, order_manager):
        """测试移除止损规则"""
        order_manager.set_stop_loss(
            account_id=1,
            symbol="600000",
            entry_price=10.00,
            stop_type="percentage",
            stop_percentage=0.05
        )

        order_manager.remove_stop_loss(1, "600000")

        rules = order_manager.get_active_stop_rules(1)
        assert len([r for r in rules if r["symbol"] == "600000"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

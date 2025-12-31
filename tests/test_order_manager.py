"""订单管理器测试"""

import pytest
from datetime import datetime
from core.order_manager import OrderManager
from core.order_types import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    Fill,
)


class TestOrderManager:
    """测试订单管理器"""
    
    @pytest.fixture
    def order_manager(self):
        """创建订单管理器实例"""
        return OrderManager()
    
    def test_create_order(self, order_manager):
        """测试创建订单"""
        order = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        assert order.status == OrderStatus.PENDING
        assert order.order_id in order_manager.orders
    
    def test_create_limit_order(self, order_manager):
        """测试创建限价单"""
        order = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            price=150.0,
        )
        
        assert order.order_type == OrderType.LIMIT
        assert order.price == 150.0
    
    def test_create_order_without_price_fails(self, order_manager):
        """测试创建限价单不提供价格应该失败"""
        with pytest.raises(ValueError):
            order_manager.create_order(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=100,
                order_type=OrderType.LIMIT,
            )
    
    def test_submit_order(self, order_manager):
        """测试提交订单"""
        order = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
        )
        
        success = order_manager.submit_order(order.order_id)
        assert success is True
        assert order.status == OrderStatus.SUBMITTED
    
    def test_cancel_order(self, order_manager):
        """测试撤销订单"""
        order = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
        )
        
        success = order_manager.cancel_order(order.order_id, reason="测试撤销")
        assert success is True
        assert order.status == OrderStatus.CANCELLED
    
    def test_modify_order(self, order_manager):
        """测试修改订单"""
        order = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            price=150.0,
        )
        
        success = order_manager.modify_order(
            order.order_id,
            quantity=200,
            price=155.0,
        )
        assert success is True
        assert order.quantity == 200
        assert order.price == 155.0
    
    def test_add_fill(self, order_manager):
        """测试添加成交记录"""
        order = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
        )
        order_manager.submit_order(order.order_id)
        
        fill = Fill(
            fill_id="FILL_001",
            order_id=order.order_id,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            price=150.0,
            timestamp=datetime.now(),
        )
        
        success = order_manager.add_fill(order.order_id, fill)
        assert success is True
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 100
        assert len(order.fills) == 1
    
    def test_partial_fill(self, order_manager):
        """测试部分成交"""
        order = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
        )
        order_manager.submit_order(order.order_id)
        
        # 第一次成交50股
        fill1 = Fill(
            fill_id="FILL_001",
            order_id=order.order_id,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=50,
            price=150.0,
            timestamp=datetime.now(),
        )
        order_manager.add_fill(order.order_id, fill1)
        
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.filled_quantity == 50
        assert order.remaining_quantity == 50
        
        # 第二次成交剩余50股
        fill2 = Fill(
            fill_id="FILL_002",
            order_id=order.order_id,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=50,
            price=150.5,
            timestamp=datetime.now(),
        )
        order_manager.add_fill(order.order_id, fill2)
        
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 100
        assert order.remaining_quantity == 0
        assert abs(order.avg_fill_price - 150.25) < 0.01  # 平均价格
    
    def test_get_orders_by_symbol(self, order_manager):
        """测试按标的获取订单"""
        order1 = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
        )
        order2 = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=50,
        )
        order3 = order_manager.create_order(
            symbol="TSLA",
            side=OrderSide.BUY,
            quantity=200,
        )
        
        aapl_orders = order_manager.get_orders_by_symbol("AAPL")
        assert len(aapl_orders) == 2
        assert all(o.symbol == "AAPL" for o in aapl_orders)
    
    def test_get_orders_by_status(self, order_manager):
        """测试按状态获取订单"""
        order1 = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
        )
        order2 = order_manager.create_order(
            symbol="TSLA",
            side=OrderSide.BUY,
            quantity=200,
        )
        order_manager.submit_order(order1.order_id)
        
        pending_orders = order_manager.get_orders_by_status(OrderStatus.PENDING)
        submitted_orders = order_manager.get_orders_by_status(OrderStatus.SUBMITTED)
        
        assert len(pending_orders) == 1
        assert len(submitted_orders) == 1
    
    def test_get_order_statistics(self, order_manager):
        """测试获取订单统计"""
        order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
        )
        order_manager.create_order(
            symbol="TSLA",
            side=OrderSide.BUY,
            quantity=200,
        )
        
        stats = order_manager.get_order_statistics()
        
        assert stats["total_orders"] >= 2
        assert stats["active_orders"] == 2
        assert "by_status" in stats


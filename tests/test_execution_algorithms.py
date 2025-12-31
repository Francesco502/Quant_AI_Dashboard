"""订单执行算法测试"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from core.execution_algorithms import (
    MarketOrderAlgorithm,
    TWAPAlgorithm,
    VWAPAlgorithm,
    AdaptiveAlgorithm,
    get_execution_algorithm,
)
from core.order_types import Order, OrderType, OrderSide
from core.order_manager import OrderManager


class TestExecutionAlgorithms:
    """测试订单执行算法"""
    
    @pytest.fixture
    def order(self):
        """创建测试订单"""
        return Order(
            order_id="TEST_001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
        )
    
    @pytest.fixture
    def market_data(self):
        """创建测试市场数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="H")
        return pd.DataFrame({
            "volume": np.random.randint(100000, 500000, 100),
            "AAPL": np.random.uniform(140, 160, 100),
        }, index=dates)
    
    def test_market_order_algorithm(self, order):
        """测试市价单算法"""
        algorithm = MarketOrderAlgorithm()
        current_price = 150.0
        
        fills = algorithm.execute(order, current_price)
        
        assert len(fills) == 1
        assert fills[0].quantity == 1000
        assert fills[0].price == 150.0
    
    def test_twap_algorithm(self, order):
        """测试TWAP算法"""
        algorithm = TWAPAlgorithm(duration_minutes=30, num_slices=10)
        current_price = 150.0
        
        fills = algorithm.execute(order, current_price)
        
        assert len(fills) == 10
        total_quantity = sum(f.quantity for f in fills)
        assert total_quantity == 1000
        
        # 检查时间分布
        timestamps = [f.timestamp for f in fills]
        assert timestamps == sorted(timestamps)
    
    def test_vwap_algorithm(self, order, market_data):
        """测试VWAP算法"""
        algorithm = VWAPAlgorithm(lookback_days=5, num_slices=10)
        current_price = 150.0
        
        fills = algorithm.execute(order, current_price, market_data)
        
        assert len(fills) > 0
        total_quantity = sum(f.quantity for f in fills)
        assert total_quantity == 1000
    
    def test_vwap_fallback_to_twap(self, order):
        """测试VWAP在没有市场数据时回退到TWAP"""
        algorithm = VWAPAlgorithm()
        current_price = 150.0
        
        # 不提供市场数据
        fills = algorithm.execute(order, current_price, None)
        
        # 应该回退到TWAP，仍然有成交
        assert len(fills) > 0
    
    def test_adaptive_algorithm_small_order(self, order, market_data):
        """测试自适应算法（小单）"""
        # 创建小单
        small_order = Order(
            order_id="TEST_SMALL",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,  # 小单
        )
        
        algorithm = AdaptiveAlgorithm(large_order_threshold=0.1)
        current_price = 150.0
        
        fills = algorithm.execute(small_order, current_price, market_data)
        
        # 小单应该立即执行（市价单）
        assert len(fills) == 1
    
    def test_adaptive_algorithm_large_order(self, order, market_data):
        """测试自适应算法（大单）"""
        # 创建大单
        large_order = Order(
            order_id="TEST_LARGE",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100000,  # 大单
        )
        
        algorithm = AdaptiveAlgorithm(large_order_threshold=0.1)
        current_price = 150.0
        
        fills = algorithm.execute(large_order, current_price, market_data)
        
        # 大单应该使用VWAP，分成多笔
        assert len(fills) > 1
    
    def test_get_execution_algorithm(self):
        """测试获取执行算法工厂函数"""
        # 测试各种算法类型
        market = get_execution_algorithm("market")
        assert isinstance(market, MarketOrderAlgorithm)
        
        twap = get_execution_algorithm("twap", duration_minutes=60, num_slices=20)
        assert isinstance(twap, TWAPAlgorithm)
        assert twap.duration_minutes == 60
        assert twap.num_slices == 20
        
        vwap = get_execution_algorithm("vwap", lookback_days=10, num_slices=15)
        assert isinstance(vwap, VWAPAlgorithm)
        assert vwap.lookback_days == 10
        assert vwap.num_slices == 15
        
        adaptive = get_execution_algorithm("adaptive", large_order_threshold=0.2)
        assert isinstance(adaptive, AdaptiveAlgorithm)
        assert adaptive.large_order_threshold == 0.2
    
    def test_get_execution_algorithm_unknown(self):
        """测试未知算法类型回退"""
        algorithm = get_execution_algorithm("unknown")
        assert isinstance(algorithm, MarketOrderAlgorithm)


"""滑点模型测试"""

import pytest
import pandas as pd
import numpy as np
from core.slippage_model import SlippageModel, SlippageConfig
from core.order_types import Order, OrderType, OrderSide


class TestSlippageModel:
    """测试滑点模型"""
    
    @pytest.fixture
    def fixed_slippage_model(self):
        """创建固定滑点模型"""
        config = SlippageConfig(model_type="fixed", fixed_rate=0.001)
        return SlippageModel(config)
    
    @pytest.fixture
    def volume_slippage_model(self):
        """创建基于成交量的滑点模型"""
        config = SlippageConfig(model_type="volume", fixed_rate=0.001)
        return SlippageModel(config)
    
    @pytest.fixture
    def order(self):
        """创建测试订单"""
        return Order(
            order_id="TEST_001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
        )
    
    @pytest.fixture
    def market_data(self):
        """创建测试市场数据"""
        dates = pd.date_range(start="2025-01-01", periods=20, freq="D")
        return pd.DataFrame({
            "volume": np.random.randint(1000000, 5000000, 20),
            "AAPL": np.random.uniform(140, 160, 20),
        }, index=dates)
    
    def test_fixed_slippage(self, fixed_slippage_model, order):
        """测试固定滑点"""
        current_price = 150.0
        slippage = fixed_slippage_model.calculate_slippage(order, current_price)
        
        # 滑点应该是订单金额的0.1%
        expected_slippage = 100 * 150.0 * 0.001
        assert abs(slippage - expected_slippage) < 0.01
    
    def test_volume_based_slippage(self, volume_slippage_model, order, market_data):
        """测试基于成交量的滑点"""
        current_price = 150.0
        slippage = volume_slippage_model.calculate_slippage(
            order, current_price, market_data
        )
        
        # 滑点应该大于0
        assert slippage >= 0
    
    def test_apply_slippage_buy(self, fixed_slippage_model, order):
        """测试应用滑点（买入）"""
        current_price = 150.0
        adjusted_price = fixed_slippage_model.apply_slippage(order, current_price)
        
        # 买入时价格应该上涨（不利滑点）
        assert adjusted_price > current_price
    
    def test_apply_slippage_sell(self, fixed_slippage_model):
        """测试应用滑点（卖出）"""
        sell_order = Order(
            order_id="TEST_002",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=100,
        )
        current_price = 150.0
        adjusted_price = fixed_slippage_model.apply_slippage(sell_order, current_price)
        
        # 卖出时价格应该下跌（不利滑点）
        assert adjusted_price < current_price
    
    def test_estimate_execution_price_limit(self, fixed_slippage_model):
        """测试估算执行价格（限价单）"""
        limit_order = Order(
            order_id="TEST_003",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=145.0,
        )
        current_price = 150.0
        
        execution_price = fixed_slippage_model.estimate_execution_price(
            limit_order, current_price
        )
        
        # 限价单应该基于限价计算
        assert execution_price > 145.0  # 考虑滑点后价格
    
    def test_slippage_limits(self, fixed_slippage_model, order):
        """测试滑点限制"""
        config = SlippageConfig(
            model_type="fixed",
            fixed_rate=0.05,  # 5%滑点
            max_slippage=0.01,  # 但最大限制1%
        )
        model = SlippageModel(config)
        
        current_price = 150.0
        slippage = model.calculate_slippage(order, current_price)
        
        # 滑点应该被限制在1%以内
        max_slippage_amount = 100 * 150.0 * 0.01
        assert slippage <= max_slippage_amount


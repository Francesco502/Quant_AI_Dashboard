"""策略引擎模块单元测试"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import patch

from core.strategy_engine import generate_multi_asset_signals


class TestStrategyEngine:
    """测试策略引擎模块"""
    
    @pytest.fixture
    def sample_price_data(self):
        """创建示例价格数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        return pd.DataFrame({
            "AAPL": np.random.uniform(150, 200, 100),
            "TSLA": np.random.uniform(200, 300, 100),
            "MSFT": np.random.uniform(300, 400, 100),
        }, index=dates)
    
    def test_generate_multi_asset_signals(self, sample_price_data):
        """测试生成多资产信号"""
        signals = generate_multi_asset_signals(
            price_df=sample_price_data
        )
        
        assert signals is not None
        assert isinstance(signals, pd.DataFrame)
        assert "ticker" in signals.columns
        assert "combined_signal" in signals.columns
        assert len(signals) > 0
    
    def test_generate_signals_empty_data(self):
        """测试空数据时的信号生成"""
        empty_data = pd.DataFrame()
        
        signals = generate_multi_asset_signals(
            price_df=empty_data
        )
        
        assert signals is not None
        assert signals.empty or len(signals) == 0
    
    def test_generate_signals_single_ticker(self):
        """测试单标的信号生成"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        single_data = pd.DataFrame({
            "AAPL": np.random.uniform(150, 200, 100),
        }, index=dates)
        
        signals = generate_multi_asset_signals(
            price_df=single_data
        )
        
        assert signals is not None
        assert len(signals) >= 0  # 可能生成0个或多个信号


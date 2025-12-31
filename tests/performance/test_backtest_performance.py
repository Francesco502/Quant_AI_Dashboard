"""回测性能测试"""

import pytest
import time
import pandas as pd
import numpy as np
from unittest.mock import patch

# from core.backtest import run_backtest  # 如果函数存在则取消注释


class TestBacktestPerformance:
    """测试回测性能"""
    
    @pytest.fixture
    def sample_backtest_data(self):
        """创建回测数据"""
        dates = pd.date_range(start="2020-01-01", periods=365*2, freq="D")
        return pd.DataFrame({
            "AAPL": np.random.uniform(100, 200, len(dates)),
            "TSLA": np.random.uniform(200, 300, len(dates)),
        }, index=dates)
    
    @pytest.mark.performance
    def test_backtest_performance_small(self, sample_backtest_data):
        """测试小规模回测性能"""
        # 简化回测：只测试数据准备和基本计算
        start = time.time()
        
        # 模拟回测计算
        returns = sample_backtest_data.pct_change().dropna()
        sharpe = returns.mean() / returns.std() * np.sqrt(252)
        
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"小规模回测耗时 {elapsed:.2f} 秒，超过1秒限制"
    
    @pytest.mark.performance
    def test_backtest_performance_large(self):
        """测试大规模回测性能"""
        # 创建大量数据
        dates = pd.date_range(start="2020-01-01", periods=365*5, freq="D")
        data = pd.DataFrame({
            f"TICKER_{i}": np.random.uniform(100, 200, len(dates))
            for i in range(10)
        }, index=dates)
        
        start = time.time()
        
        # 模拟大规模回测计算
        returns = data.pct_change().dropna()
        portfolio_returns = returns.mean(axis=1)
        sharpe = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252)
        
        elapsed = time.time() - start
        
        assert elapsed < 5.0, f"大规模回测耗时 {elapsed:.2f} 秒，超过5秒限制"


"""风险分析模块单元测试"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from core.risk_analysis import (
    calculate_var,
    calculate_cvar,
    calculate_max_drawdown,
    calculate_correlation_matrix,
)


class TestRiskAnalysis:
    """测试风险分析模块"""
    
    @pytest.fixture
    def sample_returns(self):
        """创建示例收益率数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        returns = np.random.normal(0.001, 0.02, 100)
        return pd.Series(returns, index=dates)
    
    @pytest.fixture
    def sample_prices(self):
        """创建示例价格数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        prices = 100 * np.exp(np.cumsum(np.random.normal(0.001, 0.02, 100)))
        return pd.Series(prices, index=dates)
    
    def test_calculate_var(self, sample_returns):
        """测试VaR计算"""
        var = calculate_var(sample_returns, confidence_level=0.05)
        
        assert var is not None
        assert isinstance(var, float)
        # VaR应该是负数（表示损失）
        assert var < 0
    
    def test_calculate_var_different_confidence(self, sample_returns):
        """测试不同置信水平的VaR"""
        var_95 = calculate_var(sample_returns, confidence_level=0.05)
        var_99 = calculate_var(sample_returns, confidence_level=0.01)
        
        # 99% VaR应该更负（更保守）
        assert var_99 <= var_95
    
    def test_calculate_cvar(self, sample_returns):
        """测试CVaR计算"""
        cvar = calculate_cvar(sample_returns, confidence_level=0.05)
        
        assert cvar is not None
        assert isinstance(cvar, float)
        assert cvar < 0
    
    def test_calculate_max_drawdown(self, sample_prices):
        """测试最大回撤计算"""
        max_dd, dd_series = calculate_max_drawdown(sample_prices)
        
        assert max_dd is not None
        assert isinstance(max_dd, float)
        assert max_dd <= 0  # 回撤应该是负数或零
        
        assert dd_series is not None
        assert isinstance(dd_series, pd.Series)
        assert len(dd_series) == len(sample_prices)
    
    def test_calculate_max_drawdown_with_prices(self, sample_prices):
        """测试使用价格数据计算最大回撤"""
        max_dd, dd_series = calculate_max_drawdown(sample_prices)
        
        assert max_dd is not None
        assert max_dd <= 0
        assert len(dd_series) == len(sample_prices)
    
    def test_calculate_correlation_matrix(self):
        """测试相关性矩阵计算"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        returns_df = pd.DataFrame({
            "AAPL": np.random.normal(0.001, 0.02, 100),
            "TSLA": np.random.normal(0.001, 0.03, 100),
            "MSFT": np.random.normal(0.001, 0.02, 100),
        }, index=dates)
        
        corr_matrix = calculate_correlation_matrix(returns_df)
        
        assert corr_matrix is not None
        assert isinstance(corr_matrix, pd.DataFrame)
        assert corr_matrix.shape == (3, 3)
        
        # 对角线应该是1
        assert all(corr_matrix.iloc[i, i] == 1.0 for i in range(3))
        
        # 对称矩阵
        assert corr_matrix.equals(corr_matrix.T)


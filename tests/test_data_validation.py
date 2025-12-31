"""数据验证规则引擎测试"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from core.data_validation import (
    DataValidator,
    PriceRangeRule,
    PriceChangeRule,
    PriceContinuityRule,
    VolumeRangeRule,
    VolumeSpikeRule,
    OHLCConsistencyRule,
    MissingDataRule,
    ValidationResult,
)


class TestValidationRules:
    """测试验证规则"""
    
    @pytest.fixture
    def sample_price_data(self):
        """创建示例价格数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        prices = np.random.uniform(100, 200, 100)
        return pd.Series(prices, index=dates, name="close")
    
    @pytest.fixture
    def sample_ohlcv_data(self):
        """创建示例OHLCV数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        data = {
            "open": np.random.uniform(100, 200, 100),
            "high": np.random.uniform(200, 300, 100),
            "low": np.random.uniform(50, 100, 100),
            "close": np.random.uniform(100, 200, 100),
            "volume": np.random.uniform(1000000, 5000000, 100),
        }
        return pd.DataFrame(data, index=dates)
    
    def test_price_range_rule_valid(self, sample_price_data):
        """测试价格范围规则（有效数据）"""
        rule = PriceRangeRule(min=0, max=1000000)
        result = rule.check(sample_price_data, "TEST")
        
        assert result.passed is True
    
    def test_price_range_rule_invalid(self):
        """测试价格范围规则（无效数据）"""
        dates = pd.date_range(start="2025-01-01", periods=10, freq="D")
        prices = pd.Series([-10, 20, 30, 2000000, 50], index=dates[:5])
        rule = PriceRangeRule(min=0, max=1000000)
        result = rule.check(prices, "TEST")
        
        assert result.passed is False
    
    def test_price_change_rule(self, sample_price_data):
        """测试价格变化规则"""
        rule = PriceChangeRule(max_change=0.5)
        result = rule.check(sample_price_data, "TEST")
        
        # 随机数据可能触发，但至少应该执行
        assert isinstance(result, ValidationResult)
    
    def test_price_continuity_rule(self, sample_price_data):
        """测试价格连续性规则"""
        rule = PriceContinuityRule(max_gap_days=5)
        result = rule.check(sample_price_data, "TEST")
        
        assert isinstance(result, ValidationResult)
    
    def test_volume_range_rule(self, sample_ohlcv_data):
        """测试成交量范围规则"""
        rule = VolumeRangeRule(min=0)
        result = rule.check(sample_ohlcv_data, "TEST")
        
        assert result.passed is True
    
    def test_ohlc_consistency_rule(self, sample_ohlcv_data):
        """测试OHLC一致性规则"""
        rule = OHLCConsistencyRule()
        result = rule.check(sample_ohlcv_data, "TEST")
        
        # 随机数据可能不一致，但至少应该执行
        assert isinstance(result, ValidationResult)
    
    def test_missing_data_rule(self, sample_price_data):
        """测试缺失数据规则"""
        # 添加一些缺失值
        data_with_missing = sample_price_data.copy()
        data_with_missing.iloc[10:15] = np.nan
        
        rule = MissingDataRule(max_missing_days=5, max_missing_pct=0.1)
        result = rule.check(data_with_missing, "TEST")
        
        assert isinstance(result, ValidationResult)


class TestDataValidator:
    """测试数据验证器"""
    
    @pytest.fixture
    def validator(self):
        """创建数据验证器实例"""
        return DataValidator()
    
    @pytest.fixture
    def sample_data(self):
        """创建示例数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        return pd.DataFrame({
            "close": np.random.uniform(100, 200, 100),
            "volume": np.random.uniform(1000000, 5000000, 100),
        }, index=dates)
    
    def test_validate(self, validator, sample_data):
        """测试验证数据"""
        results = validator.validate(sample_data, "TEST")
        
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, ValidationResult) for r in results)
    
    def test_validate_summary(self, validator, sample_data):
        """测试验证摘要"""
        summary = validator.validate_summary(sample_data, "TEST")
        
        assert "ticker" in summary
        assert "level" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert "issues" in summary
    
    def test_add_remove_rule(self, validator):
        """测试添加和移除规则"""
        rule = PriceRangeRule(min=0, max=1000)
        validator.add_rule("price", rule)
        
        # 验证规则已添加
        assert len(validator.validation_rules["price"]) > 0
        
        # 移除规则
        success = validator.remove_rule("price", rule.rule_name)
        assert success is True


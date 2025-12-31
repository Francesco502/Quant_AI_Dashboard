"""数据修复测试"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from core.data_repair import (
    DataRepair,
    MissingDataRepair,
    OutlierRepair,
    InconsistentRepair,
    RepairResult,
)
from core.data_validation import ValidationResult


class TestRepairStrategies:
    """测试修复策略"""
    
    @pytest.fixture
    def sample_data_with_missing(self):
        """创建包含缺失值的数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        data = pd.Series(np.random.uniform(100, 200, 100), index=dates)
        data.iloc[10:15] = np.nan
        return data
    
    @pytest.fixture
    def sample_data_with_outliers(self):
        """创建包含异常值的数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        data = pd.Series(np.random.uniform(100, 200, 100), index=dates)
        data.iloc[0] = 10000  # 异常值
        data.iloc[1] = -100   # 异常值
        return data
    
    @pytest.fixture
    def sample_ohlcv_inconsistent(self):
        """创建不一致的OHLCV数据"""
        dates = pd.date_range(start="2025-01-01", periods=10, freq="D")
        data = pd.DataFrame({
            "open": [100, 110, 120],
            "high": [90, 100, 110],  # high < open (错误)
            "low": [95, 105, 115],
            "close": [105, 115, 125],
        }, index=dates[:3])
        return data
    
    def test_missing_data_repair_forward_fill(self, sample_data_with_missing):
        """测试缺失数据修复（前向填充）"""
        strategy = MissingDataRepair(method="forward_fill")
        issue = ValidationResult(False, "缺失数据检查", "存在缺失值", "missing_data")
        
        repaired_data, result = strategy.repair(sample_data_with_missing, issue)
        
        assert result.success is True
        assert repaired_data.isna().sum() < sample_data_with_missing.isna().sum()
    
    def test_outlier_repair_clip(self, sample_data_with_outliers):
        """测试异常值修复（裁剪）"""
        strategy = OutlierRepair(method="clip")
        issue = ValidationResult(False, "异常值检查", "存在异常值", "outlier")
        
        repaired_data, result = strategy.repair(sample_data_with_outliers, issue)
        
        assert result.success is True
        assert repaired_data.max() < sample_data_with_outliers.max()
    
    def test_inconsistent_repair(self, sample_ohlcv_inconsistent):
        """测试不一致数据修复"""
        strategy = InconsistentRepair()
        issue = ValidationResult(False, "OHLC一致性检查", "OHLC逻辑错误", "ohlc_consistency")
        
        repaired_data, result = strategy.repair(sample_ohlcv_inconsistent, issue)
        
        assert result.success is True
        # 验证修复后的数据符合逻辑
        assert (repaired_data["high"] >= repaired_data["low"]).all()
        assert (repaired_data["high"] >= repaired_data["open"]).all()
        assert (repaired_data["high"] >= repaired_data["close"]).all()


class TestDataRepair:
    """测试数据修复器"""
    
    @pytest.fixture
    def data_repair(self):
        """创建数据修复器实例"""
        return DataRepair()
    
    @pytest.fixture
    def sample_data_with_issues(self):
        """创建包含多个问题的数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        data = pd.DataFrame({
            "close": np.random.uniform(100, 200, 100),
            "volume": np.random.uniform(1000000, 5000000, 100),
        }, index=dates)
        data.iloc[10:15, 0] = np.nan  # 缺失值
        return data
    
    def test_repair(self, data_repair, sample_data_with_issues):
        """测试修复数据"""
        issues = [
            ValidationResult(False, "缺失数据检查", "存在缺失值", "missing_data"),
        ]
        
        repaired_data, results = data_repair.repair(
            sample_data_with_issues,
            issues,
            "TEST"
        )
        
        assert len(results) > 0
        # 比较缺失值总数
        repaired_na_count = repaired_data.isna().sum().sum()
        original_na_count = sample_data_with_issues.isna().sum().sum()
        assert repaired_na_count < original_na_count
    
    def test_get_repair_history(self, data_repair):
        """测试获取修复历史"""
        history = data_repair.get_repair_history()
        
        assert isinstance(history, list)


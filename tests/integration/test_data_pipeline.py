"""数据管道集成测试

测试数据获取、验证、修复、存储的完整流程
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock

from core.data_service import load_price_data
from core.data_validation import DataValidator
from core.data_repair import DataRepair
from core.database import Database
import tempfile
import os


class TestDataPipeline:
    """测试数据管道"""
    
    @pytest.fixture
    def sample_data_with_issues(self):
        """创建包含问题的数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        data = pd.DataFrame({
            "close": np.random.uniform(100, 200, 100),
            "volume": np.random.uniform(1000000, 5000000, 100),
        }, index=dates)
        
        # 添加一些问题
        data.iloc[10:15, 0] = np.nan  # 缺失值
        data.iloc[20, 0] = -10  # 异常值（负数）
        
        return data
    
    def test_data_validation_pipeline(self, sample_data_with_issues):
        """测试数据验证流程"""
        validator = DataValidator()
        
        # 验证数据
        results = validator.validate(sample_data_with_issues, "TEST")
        
        assert len(results) > 0
        # 应该发现一些问题
        issues = [r for r in results if not r.passed]
        assert len(issues) > 0
    
    def test_data_repair_pipeline(self, sample_data_with_issues):
        """测试数据修复流程"""
        validator = DataValidator()
        repair = DataRepair()
        
        # 验证数据
        results = validator.validate(sample_data_with_issues, "TEST")
        issues = [r for r in results if not r.passed]
        
        # 修复数据
        if issues:
            repaired_data, repair_results = repair.repair(
                sample_data_with_issues,
                issues,
                "TEST"
            )
            
            assert repaired_data is not None
            assert len(repair_results) > 0
    
    def test_data_storage_pipeline(self):
        """测试数据存储流程"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = Database(db_path=db_path)
            
            # 创建测试数据
            dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
            data = pd.DataFrame({
                "close": np.random.uniform(100, 200, 100),
            }, index=dates)
            
            # 保存数据
            success = db.save_price_data("TEST", data)
            assert success is True
            
            # 查询数据（在关闭连接之前）
            retrieved = db.query_price_data("TEST")
            assert retrieved is not None
            assert not retrieved.empty
            assert len(retrieved) == 100
            
            # 关闭数据库连接
            if hasattr(db, 'conn') and db.conn:
                db.conn.close()


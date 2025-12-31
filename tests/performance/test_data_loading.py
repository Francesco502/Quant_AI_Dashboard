"""数据加载性能测试"""

import pytest
import time
import pandas as pd
import numpy as np
from unittest.mock import patch

from core.data_service import load_price_data
from core.database import Database
import tempfile
import os


class TestDataLoadingPerformance:
    """测试数据加载性能"""
    
    @pytest.fixture
    def sample_price_data(self):
        """创建大量价格数据"""
        dates = pd.date_range(start="2020-01-01", periods=365*5, freq="D")
        return pd.DataFrame({
            "AAPL": np.random.uniform(100, 200, len(dates)),
            "TSLA": np.random.uniform(200, 300, len(dates)),
            "MSFT": np.random.uniform(300, 400, len(dates)),
        }, index=dates)
    
    @pytest.mark.performance
    def test_data_loading_performance(self, sample_price_data):
        """测试数据加载性能（应该在5秒内完成）"""
        with patch('core.data_store.load_local_price_history') as mock_load:
            mock_load.return_value = sample_price_data["AAPL"]
            
            start = time.time()
            data = load_price_data(tickers=["AAPL"], days=365)
            elapsed = time.time() - start
            
            assert data is not None
            assert elapsed < 5.0, f"数据加载耗时 {elapsed:.2f} 秒，超过5秒限制"
    
    @pytest.mark.performance
    def test_multiple_tickers_loading_performance(self, sample_price_data):
        """测试多标的数据加载性能"""
        with patch('core.data_store.load_local_price_history') as mock_load:
            def side_effect(ticker):
                return sample_price_data[ticker] if ticker in sample_price_data.columns else None
            mock_load.side_effect = side_effect
            
            start = time.time()
            data = load_price_data(tickers=["AAPL", "TSLA", "MSFT"], days=365)
            elapsed = time.time() - start
            
            assert data is not None
            assert elapsed < 10.0, f"多标的数据加载耗时 {elapsed:.2f} 秒，超过10秒限制"
    
    @pytest.mark.performance
    def test_database_query_performance(self):
        """测试数据库查询性能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = Database(db_path=db_path)
            
            try:
                # 插入大量数据
                dates = pd.date_range(start="2020-01-01", periods=365*5, freq="D")
                data = pd.DataFrame({
                    "close": np.random.uniform(100, 200, len(dates)),
                }, index=dates)
                
                db.save_price_data("TEST", data)
                
                # 测试查询性能
                start = time.time()
                result = db.query_price_data("TEST")
                elapsed = time.time() - start
                
                assert result is not None
                assert elapsed < 1.0, f"数据库查询耗时 {elapsed:.2f} 秒，超过1秒限制"
            finally:
                # 确保关闭数据库连接
                if hasattr(db, 'conn') and db.conn:
                    db.conn.close()


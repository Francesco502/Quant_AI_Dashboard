"""数据库测试"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import os
from core.database import Database


class TestDatabase:
    """测试数据库"""
    
    @pytest.fixture
    def db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        db = Database(db_path=db_path)
        yield db
        
        # 清理
        db.close()
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def sample_data(self):
        """创建示例数据"""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        return pd.DataFrame({
            "open": np.random.uniform(100, 200, 100),
            "high": np.random.uniform(200, 300, 100),
            "low": np.random.uniform(50, 100, 100),
            "close": np.random.uniform(100, 200, 100),
            "volume": np.random.uniform(1000000, 5000000, 100),
        }, index=dates)
    
    def test_save_and_query_price_data(self, db, sample_data):
        """测试保存和查询价格数据"""
        ticker = "TEST"
        
        # 保存数据
        success = db.save_price_data(ticker, sample_data)
        assert success is True
        
        # 查询数据
        df = db.query_price_data(ticker)
        assert df is not None
        assert not df.empty
        assert len(df) == 100
        assert "close" in df.columns
    
    def test_query_price_series(self, db, sample_data):
        """测试查询价格序列"""
        ticker = "TEST"
        db.save_price_data(ticker, sample_data)
        
        series = db.query_price_series(ticker)
        assert series is not None
        assert not series.empty
        assert len(series) == 100
    
    def test_query_with_date_range(self, db, sample_data):
        """测试带日期范围的查询"""
        ticker = "TEST"
        db.save_price_data(ticker, sample_data)
        
        start_date = "2025-01-15"
        end_date = "2025-01-30"
        
        df = db.query_price_data(ticker, start_date, end_date)
        assert df is not None
        assert not df.empty
        assert len(df) <= 16  # 15到30日，最多16天
    
    def test_replace_data(self, db, sample_data):
        """测试替换数据"""
        ticker = "TEST"
        
        # 第一次保存
        db.save_price_data(ticker, sample_data, replace=True)
        df1 = db.query_price_data(ticker)
        assert len(df1) == 100
        
        # 第二次保存（替换）
        new_data = sample_data.iloc[:50]  # 只保存50条
        db.save_price_data(ticker, new_data, replace=True)
        df2 = db.query_price_data(ticker)
        assert len(df2) == 50
    
    def test_get_tickers(self, db, sample_data):
        """测试获取标的列表"""
        db.save_price_data("AAPL", sample_data)
        db.save_price_data("TSLA", sample_data)
        
        tickers = db.get_tickers()
        assert "AAPL" in tickers
        assert "TSLA" in tickers
    
    def test_get_date_range(self, db, sample_data):
        """测试获取日期范围"""
        ticker = "TEST"
        db.save_price_data(ticker, sample_data)
        
        date_range = db.get_date_range(ticker)
        assert date_range is not None
        assert "start_date" in date_range
        assert "end_date" in date_range
    
    def test_delete_ticker(self, db, sample_data):
        """测试删除标的"""
        ticker = "TEST"
        db.save_price_data(ticker, sample_data)
        
        # 确认数据存在
        df = db.query_price_data(ticker)
        assert df is not None
        
        # 删除
        success = db.delete_ticker(ticker)
        assert success is True
        
        # 确认数据已删除
        df = db.query_price_data(ticker)
        assert df is None or df.empty
    
    def test_get_statistics(self, db, sample_data):
        """测试获取统计信息"""
        db.save_price_data("AAPL", sample_data)
        db.save_price_data("TSLA", sample_data)
        
        stats = db.get_statistics()
        assert "ticker_count" in stats
        assert "record_count" in stats
        assert stats["ticker_count"] == 2


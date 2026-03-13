"""
AI 训练流水线集成测试
"""
import pytest
import pandas as pd
import numpy as np
import tempfile
import os
import shutil
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from core.training_pipeline import TrainingPipeline
from core.advanced_forecasting import get_available_models

# 模拟价格数据
@pytest.fixture
def mock_price_data():
    dates = pd.bdate_range(end=datetime.now(), periods=200)
    prices = np.linspace(100, 200, 200) + np.random.normal(0, 1, 200)
    return pd.Series(prices, index=dates, name="close")

class TestTrainingPipeline:
    
    @pytest.fixture
    def pipeline(self):
        # 创建临时目录用于存储模型
        tmp_dir = tempfile.mkdtemp()
        pipeline = TrainingPipeline(
            model_dir=tmp_dir,
            min_train_days=30,  # 降低要求以便测试
            retrain_interval_days=7
        )
        yield pipeline
        # 清理
        shutil.rmtree(tmp_dir)
    
    @patch("core.training_pipeline.load_local_price_history")
    def test_train_xgboost_flow(self, mock_load, pipeline, mock_price_data):
        """测试 XGBoost 训练流程"""
        available = get_available_models()
        if not available['XGBoost']:
            pytest.skip("XGBoost 未安装")
            
        mock_load.return_value = mock_price_data
        
        ticker = "TEST_XGB"
        
        # 1. 运行训练
        result = pipeline.train_and_evaluate(
            ticker=ticker,
            model_type="xgboost",
            auto_promote=True
        )
        
        assert result["success"] is True
        assert result["model_id"] is not None
        
        # 2. 验证模型文件是否创建
        model_info = pipeline.registry.get_model_info(result["model_id"])
        assert model_info is not None
        assert os.path.exists(model_info["model_path"])
        
        # 3. 验证是否提升为生产模型 (因为是第一个模型，应该自动提升)
        prod_id = pipeline.registry.get_production_model(ticker)
        assert prod_id == result["model_id"]
        
        # 4. 测试生成预测
        success = pipeline.generate_predictions(ticker)
        assert success is True
        
        # 验证信号是否生成 (mock signal store behavior needed ideally, but here we check return value)
    
    @patch("core.training_pipeline.load_local_price_history")
    def test_should_retrain(self, mock_load, pipeline, mock_price_data):
        """测试重训练判断逻辑"""
        ticker = "TEST_RETRAIN"
        mock_load.return_value = mock_price_data
        
        # 初始状态，无模型，应该重训练
        assert pipeline.should_retrain(ticker) is True
        
        # 注册一个"刚训练好"的生产模型
        pipeline.registry.production_models[ticker] = "mock_model_id"
        pipeline.registry.models.append({
            "model_id": "mock_model_id",
            "ticker": ticker,
            "train_date": datetime.now().strftime("%Y-%m-%d"),
            "status": "production"
        })
        
        # 现在应该不需要重训练
        assert pipeline.should_retrain(ticker) is False
        
        # 修改训练日期为很久以前
        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        pipeline.registry.models[-1]["train_date"] = old_date
        
        # 现在应该需要重训练 (因为间隔默认为7天)
        assert pipeline.should_retrain(ticker) is True
        
    @patch("core.training_pipeline.load_local_price_history")
    def test_run_training_job(self, mock_load, pipeline, mock_price_data):
        """测试批量训练任务"""
        available = get_available_models()
        if not available['XGBoost']:
            pytest.skip("XGBoost 未安装")
            
        mock_load.return_value = mock_price_data
        
        tickers = ["TEST_1", "TEST_2"]
        
        stats = pipeline.run_training_job(tickers, model_type="xgboost")
        
        assert stats["total"] == 2
        assert stats["trained"] + stats["skipped"] == 2
        assert stats["failed"] == 0

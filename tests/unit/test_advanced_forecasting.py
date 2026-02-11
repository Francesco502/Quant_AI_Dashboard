"""
AI 高级预测模块单元测试
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from core.advanced_forecasting import (
    FeatureEngineer,
    ModelEvaluator,
    XGBoostForecaster,
    ProphetForecaster,
    EnsembleForecaster,
    get_available_models
)

# 创建模拟价格数据
@pytest.fixture
def price_series():
    dates = pd.bdate_range(start="2023-01-01", periods=100)
    # 生成一个简单的上升趋势 + 正弦波 + 随机噪声
    prices = np.linspace(100, 200, 100) + \
             10 * np.sin(np.linspace(0, 10, 100)) + \
             np.random.normal(0, 1, 100)
    return pd.Series(prices, index=dates, name="close")

class TestFeatureEngineer:
    """测试特征工程模块"""
    
    def test_create_price_features(self, price_series):
        fe = FeatureEngineer()
        df = fe.create_price_features(price_series, lookback_windows=[5, 10])
        
        # 检查基本特征是否存在
        assert 'price' in df.columns
        assert 'return_1d' in df.columns
        assert 'sma_5' in df.columns
        assert 'rsi' in df.columns
        assert 'macd' in df.columns
        
        # 检查行数是否一致
        assert len(df) == len(price_series)
        
    def test_create_target(self, price_series):
        fe = FeatureEngineer()
        target = fe.create_target(price_series, horizon=5)
        
        # 检查目标是否移动了5天
        # target[t] 应该是 (price[t+5] - price[t]) / price[t]
        assert len(target) == len(price_series)
        # 最后5个应该是 NaN
        assert pd.isna(target.iloc[-1])
        
    def test_add_enhanced_features(self, price_series):
        fe = FeatureEngineer()
        df = pd.DataFrame({'price': price_series})
        df = fe.add_enhanced_features(df, price_series)
        
        assert 'atr_14' in df.columns
        assert 'realized_vol_20' in df.columns

class TestModelEvaluator:
    """测试模型评估工具"""
    
    def test_calculate_metrics(self):
        actual = pd.Series([100, 102, 104, 103, 105])
        predicted = pd.Series([101, 101, 105, 102, 106])
        
        metrics = ModelEvaluator.calculate_metrics(actual, predicted)
        
        assert 'MAE' in metrics
        assert 'RMSE' in metrics
        assert 'MAPE' in metrics
        assert 'Direction_Accuracy' in metrics
        
        # 简单验证值
        assert metrics['MAE'] > 0
        assert metrics['RMSE'] > 0

class TestXGBoostForecaster:
    """测试 XGBoost 预测器"""
    
    def test_init(self):
        available = get_available_models()
        if not available['XGBoost']:
            pytest.skip("XGBoost 未安装")
            
        model = XGBoostForecaster(n_estimators=10)
        assert model.n_estimators == 10
        
    def test_fit_predict(self, price_series):
        available = get_available_models()
        if not available['XGBoost']:
            pytest.skip("XGBoost 未安装")
            
        model = XGBoostForecaster(n_estimators=5, lookback=10)
        model.fit(price_series)
        
        assert model.model is not None
        assert model.feature_columns is not None
        
        # 预测
        horizon = 5
        pred = model.predict(horizon)
        
        assert isinstance(pred, pd.DataFrame)
        assert len(pred) == horizon
        assert 'prediction' in pred.columns
        
    def test_feature_importance(self, price_series):
        available = get_available_models()
        if not available['XGBoost']:
            pytest.skip("XGBoost 未安装")
            
        model = XGBoostForecaster(n_estimators=5, lookback=10)
        model.fit(price_series)
        
        importance = model.get_feature_importance()
        assert isinstance(importance, pd.Series)
        assert len(importance) > 0

class TestProphetForecaster:
    """测试 Prophet 预测器"""
    
    def test_init(self):
        available = get_available_models()
        if not available['Prophet']:
            pytest.skip("Prophet 未安装")
            
        model = ProphetForecaster()
        assert model.model is None
        
    def test_fit_predict(self, price_series):
        available = get_available_models()
        if not available['Prophet']:
            pytest.skip("Prophet 未安装")
            
        # Prophet 需要较多数据，且最好是真实的日期格式
        # 这里 price_series 已经使用了 bdate_range
        
        model = ProphetForecaster()
        model.fit(price_series)
        
        assert model.model is not None
        
        horizon = 5
        pred = model.predict(horizon)
        
        assert isinstance(pred, pd.DataFrame)
        assert len(pred) == horizon
        assert 'prediction' in pred.columns
        assert 'lower_bound' in pred.columns
        assert 'upper_bound' in pred.columns

class TestEnsembleForecaster:
    """测试集成预测器"""
    
    def test_ensemble_logic(self, price_series):
        # 使用 Mock 模型来避免依赖真实模型
        mock_model1 = MagicMock()
        mock_model1.predict.return_value = pd.DataFrame({'prediction': [101]*5})
        
        mock_model2 = MagicMock()
        mock_model2.predict.return_value = pd.DataFrame({'prediction': [102]*5})
        
        models = {
            'm1': mock_model1,
            'm2': mock_model2
        }
        weights = {'m1': 0.5, 'm2': 0.5}
        
        ensemble = EnsembleForecaster(models=models, weights=weights)
        
        # 模拟 fit
        ensemble.fit(price_series)
        mock_model1.fit.assert_called_once()
        mock_model2.fit.assert_called_once()
        
        # 预测
        pred = ensemble.predict(horizon=5)
        
        assert len(pred) == 5
        # (101 * 0.5) + (102 * 0.5) = 101.5
        assert np.isclose(pred['prediction'].iloc[0], 101.5)
        assert 'm1_pred' in pred.columns
        assert 'm2_pred' in pred.columns

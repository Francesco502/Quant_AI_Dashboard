"""
模型集成模块单元测试
测试加权集成模型和自适应权重调整
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# 测试导入
pytest.importorskip("core.models.ensemble", reason="ensemble 模块不可用")
from core.models.ensemble import (
    WeightedEnsemble,
    EnsembleForecaster as EnsembleForecasterBase,
    create_ensemble,
    ensemble_predict,
    DEFAULT_BASE_WEIGHTS,
    AVAILABLE_MODELS
)

pytest.importorskip("core.weights_optimizer", reason="weights_optimizer 模块不可用")
from core.weights_optimizer import (
    WeightsOptimizer,
    WeightScheduler,
    PredictionDrivenOptimizer,
    ComprehensiveWeightsOptimizer,
    adjust_weights as adjust_weights_fn
)


# ==================== 固定数据 ====================

@pytest.fixture
def price_series():
    """创建模拟价格数据"""
    dates = pd.bdate_range(start="2023-01-01", periods=100)
    # 生成一个简单的上升趋势 + 正弦波 + 随机噪声
    prices = np.linspace(100, 200, 100) + \
             10 * np.sin(np.linspace(0, 10, 100)) + \
             np.random.normal(0, 1, 100)
    return pd.Series(prices, index=dates, name="close")


@pytest.fixture
def mock_predictions():
    """创建模拟的模型预测结果"""
    dates = pd.bdate_range(start="2023-01-01", periods=5)
    return {
        'prophet': pd.DataFrame({
            'prediction': [101.0, 102.0, 103.0, 104.0, 105.0],
            'lower_bound': [100.0, 101.0, 102.0, 103.0, 104.0],
            'upper_bound': [102.0, 103.0, 104.0, 105.0, 106.0]
        }, index=dates),
        'xgboost': pd.DataFrame({
            'prediction': [101.5, 102.5, 103.5, 104.5, 105.5],
            'lower_bound': [100.5, 101.5, 102.5, 103.5, 104.5],
            'upper_bound': [102.5, 103.5, 104.5, 105.5, 106.5]
        }, index=dates),
        'lightgbm': pd.DataFrame({
            'prediction': [101.2, 102.2, 103.2, 104.2, 105.2],
            'lower_bound': [100.2, 101.2, 102.2, 103.2, 104.2],
            'upper_bound': [102.2, 103.2, 104.2, 105.2, 106.2]
        }, index=dates),
    }


# ==================== WeightedEnsemble 测试 ====================

class TestWeightedEnsemble:
    """测试 WeightedEnsemble 类"""

    def test_default_weights(self):
        """测试默认权重配置"""
        ensemble = WeightedEnsemble()
        assert ensemble.base_weights == DEFAULT_BASE_WEIGHTS

    def test_custom_weights(self):
        """测试自定义权重"""
        custom_weights = {'prophet': 2.0, 'xgboost': 1.0}
        ensemble = WeightedEnsemble(weights=custom_weights)
        # 检查权重被归一化
        assert abs(sum(ensemble.weights.values()) - 1.0) < 1e-10

    def test_normalize_weights(self):
        """测试权重归一化"""
        ensemble = WeightedEnsemble()
        ensemble.weights = {'prophet': 2.0, 'xgboost': 2.0}
        ensemble._normalize_weights()
        assert abs(ensemble.weights['prophet'] - 0.5) < 1e-10
        assert abs(ensemble.weights['xgboost'] - 0.5) < 1e-10

    def test_add_model(self):
        """测试添加模型"""
        ensemble = WeightedEnsemble()
        mock_model = MagicMock()
        ensemble.add_model('test_model', 1.0, mock_model)
        assert 'test_model' in ensemble.model_names

    def test_remove_model(self):
        """测试移除模型"""
        ensemble = WeightedEnsemble()
        ensemble.add_model('test_model', 1.0, MagicMock())
        assert 'test_model' in ensemble.model_names
        ensemble.remove_model('test_model')
        assert 'test_model' not in ensemble.model_names

    def test_get_weights(self):
        """测试获取权重"""
        ensemble = WeightedEnsemble(weights={'prophet': 0.6, 'xgboost': 0.4})
        weights = ensemble.get_weights()
        assert weights['prophet'] == 0.6
        assert weights['xgboost'] == 0.4

    def test_normalize_model_name(self):
        """测试模型名称规范化"""
        ensemble = WeightedEnsemble()
        assert ensemble._normalize_model_name('Prophet') == 'prophet'
        assert ensemble._normalize_model_name('XGBOOST') == 'xgboost'


class TestEnsemblePredict:
    """测试 ensemble_predict 函数"""

    def test_basic_ensemble(self, mock_predictions):
        """测试基本加权集成"""
        weights = {'prophet': 0.5, 'xgboost': 0.5}

        result = ensemble_predict(mock_predictions, weights)

        assert 'prediction' in result.columns
        assert len(result) == 5
        # 简单验证：前两个模型的加权平均
        expected = (101.0 * 0.5 + 101.5 * 0.5)
        assert np.isclose(result['prediction'].iloc[0], expected)

    def test_custom_weights(self, mock_predictions):
        """测试自定义权重"""
        weights = {'prophet': 0.8, 'xgboost': 0.2}
        result = ensemble_predict(mock_predictions, weights)

        expected = (101.0 * 0.8 + 101.5 * 0.2)
        assert np.isclose(result['prediction'].iloc[0], expected)

    def test_empty_predictions(self):
        """测试空预测"""
        with pytest.raises(ValueError, match="predictions 不能为空"):
            ensemble_predict({}, {'model': 1.0})

    def test_default_weights_for_empty_weights(self, mock_predictions):
        """测试空权重使用等权重"""
        result = ensemble_predict(mock_predictions, {})
        # 等权重下，三个模型各占 1/3
        expected = (101.0 + 101.5 + 101.2) / 3
        assert np.isclose(result['prediction'].iloc[0], expected)


# ==================== 权重优化器测试 ====================

class TestWeightsOptimizer:
    """测试WeightsOptimizer类"""

    def test_inverse_error_strategy(self, price_series):
        """测试误差倒数策略"""
        optimizer = WeightsOptimizer(strategy='inverse_error')

        # 更新一些性能数据
        actual = pd.Series([101, 102, 103, 104, 105])
        predicted = pd.Series([101.5, 102.5, 103.5, 104.5, 105.5])

        optimizer.update_performance('test_model', actual, predicted)

        performance = optimizer.get_model_performance('test_model')
        assert 'mape' in performance
        assert performance['record_count'] == 1

    def test_exponential_strategy(self, price_series):
        """测试指数衰减策略"""
        optimizer = WeightsOptimizer(
            strategy='exponential',
            decay_factor=0.9
        )

        actual = pd.Series([101, 102, 103, 104, 105])
        predicted = pd.Series([101.5, 102.5, 103.5, 104.5, 105.5])

        for i in range(10):
            optimizer.update_performance('test_model', actual, predicted)

        weights = optimizer.calculate_adaptive_weights()
        # 应该能计算出权重
        assert len(weights) > 0

    def test_rolling_strategy(self, price_series):
        """测试滑动窗口策略"""
        optimizer = WeightsOptimizer(
            strategy='rolling',
            window_size=20
        )

        actual = pd.Series([101, 102, 103, 104, 105])
        predicted = pd.Series([101.5, 102.5, 103.5, 104.5, 105.5])

        for i in range(30):
            optimizer.update_performance('test_model', actual, predicted)

        weights = optimizer.calculate_adaptive_weights()
        # 只使用最近20条数据
        assert len(weights) > 0

    def test_calculate_adaptive_weights_no_history(self):
        """测试无历史数据时的权重计算"""
        optimizer = WeightsOptimizer()
        weights = optimizer.calculate_adaptive_weights()
        # 应该返回基础权重
        assert len(weights) > 0

    def test_adjust_weights(self, price_series):
        """测试权重调整"""
        if not WeightedEnsemble:
            pytest.skip("WeightedEnsemble 不可用")

        optimizer = WeightsOptimizer()
        ensemble = WeightedEnsemble()

        # 确保有历史数据
        actual = pd.Series([101, 102, 103, 104, 105])
        predicted = pd.Series([101.5, 102.5, 103.5, 104.5, 105.5])
        optimizer.update_performance('prophet', actual, predicted)

        # 调整权重
        new_weights = optimizer.adjust_weights(ensemble)
        assert len(new_weights) > 0


class TestWeightScheduler:
    """测试WeightScheduler类"""

    def test_detect_market_state_trend(self, price_series):
        """测试趋势市场检测"""
        scheduler = WeightScheduler()

        # 创建有明显趋势的数据
        trend_prices = pd.Series(
            np.linspace(100, 200, 100),
            index=price_series.index
        )

        state = scheduler.detect_market_state(trend_prices)
        # 应该检测到趋势或范围
        assert state in ['trend', 'range']

    def test_get_adjusted_weights(self, price_series):
        """测试调整权重"""
        scheduler = WeightScheduler()

        # 趋势市场权重
        trend_weights = scheduler.get_adjusted_weights('trend')
        assert 'xgboost' in trend_weights

        # 震荡市场权重
        range_weights = scheduler.get_adjusted_weights('range')
        assert 'prophet' in range_weights


class TestAdjustWeightsFunction:
    """测试adjust_weights函数"""

    def test_basic_adjustment(self):
        """测试基本权重调整"""
        models = ['prophet', 'xgboost', 'lightgbm']
        historical_mape = {
            'prophet': 2.0,
            'xgboost': 3.0,
            'lightgbm': 2.5
        }

        weights = adjust_weights_fn(models, historical_mape)

        # Prophet 的 MAPE 最小，应该获得最高权重
        assert weights['prophet'] > weights['xgboost']

    def test_infinite_mape(self):
        """测试无穷大 MAPE 的处理"""
        models = ['prophet', 'xgboost']
        historical_mape = {
            'prophet': float('inf'),
            'xgboost': 2.5
        }

        weights = adjust_weights_fn(models, historical_mape)

        # 无穷大 MAPE 应使用基础权重
        assert 'xgboost' in weights

    def test_empty_models(self):
        """测试空模型列表"""
        weights = adjust_weights_fn([], {})
        assert len(weights) == 0


# ==================== 综合测试 ====================

class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, price_series):
        """测试完整工作流"""
        if not WeightedEnsemble:
            pytest.skip("WeightedEnsemble 不可用")

        # 1. 创建集成模型
        ensemble = WeightedEnsemble()
        assert ensemble is not None

        # 2. 训练模型
        # 这里不实际训练，只测试接口
        ensemble.model_names = ['prophet', 'xgboost']
        ensemble.weights = {'prophet': 0.5, 'xgboost': 0.5}

        # 3. 权重优化器
        optimizer = WeightsOptimizer()
        assert optimizer is not None

        # 4. 权重调度器
        scheduler = WeightScheduler()
        assert scheduler is not None

    def test_comprehensive_optimizer(self, price_series):
        """测试综合优化器"""
        if not (WeightedEnsemble and ComprehensiveWeightsOptimizer):
            pytest.skip("依赖模块不可用")

        ensemble = WeightedEnsemble()
        optimizer = ComprehensiveWeightsOptimizer(ensemble)

        # 执行优化
        weights = optimizer.optimize(price_series)

        # 应该返回有效的权重
        assert len(weights) > 0
        assert abs(sum(weights.values()) - 1.0) < 1e-10

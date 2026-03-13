"""
自适应权重优化器
基于历史预测准确率动态调整模型权重

作者: Claude
版本: 2.0.0
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

try:
    from core.models.ensemble import (
        WeightedEnsemble,
        DEFAULT_BASE_WEIGHTS,
        AVAILABLE_MODELS
    )
    ENSEMBLE_AVAILABLE = True
except ImportError:
    ENSEMBLE_AVAILABLE = False
    DEFAULT_BASE_WEIGHTS = {
        'prophet': 1.0,
        'xgboost': 2.0,
        'lightgbm': 1.5,
        'arima': 0.8
    }
    AVAILABLE_MODELS = ['prophet', 'xgboost', 'lightgbm', 'arima']


# ==================== 权重优化器 ====================

class WeightsOptimizer:
    """
    自适应权重优化器

    根据模型的历史预测准确率动态调整集成模型的权重。
    支持多种优化策略：

    1. 误差倒数法 (Inverse Error): weight = 1 / (MAPE + eps)
    2. 指数衰减法 (Exponential Decay): 基于最新表现的指数加权
    3. 窗口滑动法 (Rolling Window): 基于最近 N 次表现
    4. 线性优化法 (Linear Optimization): 基于最小化整体误差

    属性:
        strategy: 优化策略
        window_size: 滑动窗口大小
        decay_factor: 指数衰减因子
        min_weight: 最小权重限制
        max_weight: 最大权重限制
        performance_history: 性能历史记录
    """

    def __init__(
        self,
        strategy: str = 'inverse_error',
        window_size: int = 30,
        decay_factor: float = 0.95,
        min_weight: float = 0.01,
        max_weight: float = 0.99,
        base_weights: Optional[Dict[str, float]] = None
    ):
        """
        初始化权重优化器

        参数:
            strategy: 优化策略
                - 'inverse_error': 误差倒数法 (推荐)
                - 'exponential': 指数衰减法
                - 'rolling': 窗口滑动法
                - 'linear': 线性优化法
            window_size: 滑动窗口大小（用于 rolling 和 exponential 策略）
            decay_factor: 指数衰减因子（0-1之间，越接近1权重保留越多）
            min_weight: 最小权重限制
            max_weight: 最大权重限制
            base_weights: 基础权重配置
        """
        self.strategy = strategy
        self.window_size = window_size
        self.decay_factor = decay_factor
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.base_weights = base_weights or DEFAULT_BASE_WEIGHTS.copy()

        # 性能历史: {model_name: [{'date': ..., 'mape': ..., 'mae': ..., 'rmse': ...}]}
        self.performance_history: Dict[str, List[Dict[str, Any]]] = {
            model: [] for model in AVAILABLE_MODELS
        }

        # 优化器状态
        self.last_adjusted: Optional[datetime] = None
        self.adjustment_count = 0

    def update_performance(
        self,
        model_name: str,
        actual: pd.Series,
        predicted: pd.Series,
        date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        更新模型性能记录

        参数:
            model_name: 模型名称
            actual: 实际值
            predicted: 预测值
            date: 性能记录日期（默认为当前时间）

        返回:
            计算得到的性能指标
        """
        if date is None:
            date = datetime.now()

        # 确保数据对齐
        actual = actual.dropna()
        predicted = predicted.dropna()
        common_idx = actual.index.intersection(predicted.index)
        actual = actual.loc[common_idx]
        predicted = predicted.loc[common_idx]

        if len(actual) == 0:
            return {}

        # 计算性能指标
        mae = np.mean(np.abs(actual - predicted))
        rmse = np.sqrt(np.mean((actual - predicted) ** 2))
        mape = np.mean(np.abs((actual - predicted) / actual)) * 100 if np.any(actual != 0) else float('inf')
        mse = np.mean((actual - predicted) ** 2)

        # 方向准确率
        actual_diff = actual.diff().dropna()
        predicted_diff = pd.Series(predicted).diff().dropna()
        common_diff_idx = actual_diff.index.intersection(predicted_diff.index)
        if len(common_diff_idx) > 0:
            direction_correct = np.sign(actual_diff.loc[common_diff_idx]) == np.sign(predicted_diff.loc[common_diff_idx])
            direction_accuracy = np.mean(direction_correct) * 100
        else:
            direction_accuracy = 50.0  # 随机准确率

        performance = {
            'date': date,
            'mae': mae,
            'rmse': rmse,
            'mape': mape,
            'mse': mse,
            'direction_accuracy': direction_accuracy
        }


        # Update history (also support custom model names from tests/users)
        if model_name not in self.performance_history:
            self.performance_history[model_name] = []
        self.performance_history[model_name].append(performance)

        # Keep bounded history window
        if len(self.performance_history[model_name]) > self.window_size * 2:
            self.performance_history[model_name] = (
                self.performance_history[model_name][-self.window_size * 2:]
            )
        return performance

    def get_model_performance(self, model_name: str) -> Dict[str, float]:
        """
        获取模型的平均性能

        参数:
            model_name: 模型名称

        返回:
            平均性能指标
        """
        if model_name not in self.performance_history:
            return {}

        history = self.performance_history[model_name]
        if not history:
            return {}

        return {
            'mae': np.mean([h['mae'] for h in history]),
            'rmse': np.mean([h['rmse'] for h in history]),
            'mape': np.mean([h['mape'] for h in history]),
            'direction_accuracy': np.mean([h['direction_accuracy'] for h in history]),
            'record_count': len(history)
        }

    def calculate_adaptive_weights(self) -> Dict[str, float]:
        """
        根据历史性能计算自适应权重

        返回:
            归一化后的权重字典
        """
        if not any(self.performance_history.values()):
            # 没有历史数据，使用基础权重
            return self.base_weights.copy()

        weights = {}

        # 收集所有模型的性能
        for model_name in AVAILABLE_MODELS:
            history = self.performance_history[model_name]
            if not history:
                # 没有历史数据，使用中等权重
                weights[model_name] = self.base_weights.get(model_name, 1.0)
                continue

            # 计算加权平均性能（近期表现权重更高）
            if self.strategy == 'exponential':
                weights[model_name] = self._exponential_decay_weight(history)
            elif self.strategy == 'rolling':
                weights[model_name] = self._rolling_weight(history)
            elif self.strategy == 'linear':
                weights[model_name] = self._linear_optimized_weight(history)
            else:  # inverse_error (default)
                weights[model_name] = self._inverse_error_weight(history)

        # 归一化
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        # 应用最小/最大权重限制
        weights = {k: np.clip(v, self.min_weight, self.max_weight)
                   for k, v in weights.items()}

        # 重新归一化（应用限制后）
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        self.last_adjusted = datetime.now()
        self.adjustment_count += 1

        return weights

    def _inverse_error_weight(self, history: List[Dict[str, Any]]) -> float:
        """
        误差倒数法权重计算
        weight = 1 / (MAPE + eps)

        优点: 简单直观，对异常值敏感
        """
        eps = 1e-6
        mape_values = [h['mape'] for h in history if h['mape'] != float('inf')]
        mape_values = [m for m in mape_values if not np.isnan(m)]

        if not mape_values:
            return self.base_weights.get('default', 1.0)

        # 使用平均 MAPE
        avg_mape = np.mean(mape_values)
        return 1.0 / (avg_mape + eps)

    def _exponential_decay_weight(self, history: List[Dict[str, Any]]) -> float:
        """
        指数衰减法权重计算
        给近期表现更高的权重

        weight = sum(decay_factor^(n-i) * (1/(MAPE_i + eps)))
        """
        eps = 1e-6
        n = len(history)

        if n == 0:
            return self.base_weights.get('default', 1.0)

        weighted_sum = 0.0
        weight_sum = 0.0

        for i, h in enumerate(history):
            if h['mape'] == float('inf') or np.isnan(h['mape']):
                continue

            # 近期权重更高
            weight = (self.decay_factor ** (n - i - 1)) * (1.0 / (h['mape'] + eps))
            weighted_sum += weight
            weight_sum += self.decay_factor ** (n - i - 1)

        return weighted_sum / weight_sum if weight_sum > 0 else 1.0

    def _rolling_weight(self, history: List[Dict[str, Any]]) -> float:
        """
        窗口滑动法权重计算
        基于最近 window_size 次表现

        优点: 忽略久远的历史，关注近期表现
        """
        # 只使用最近 window_size 条记录
        recent_history = history[-self.window_size:]

        if not recent_history:
            return self.base_weights.get('default', 1.0)

        eps = 1e-6
        total_inverse_error = 0.0

        for h in recent_history:
            if h['mape'] != float('inf') and not np.isnan(h['mape']):
                total_inverse_error += 1.0 / (h['mape'] + eps)

        return total_inverse_error

    def _linear_optimized_weight(self, history: List[Dict[str, Any]]) -> float:
        """
        线性优化法权重计算
        基于最小化整体误差的优化思路

        使用简单的启发式方法：
        权重与 (1/MAPE) 和 (方向准确率) 的加权乘积成正比
        """
        eps = 1e-6
        n = len(history)

        if n == 0:
            return self.base_weights.get('default', 1.0)

        scores = []
        for h in history:
            if h['mape'] == float('inf') or np.isnan(h['mape']):
                continue

            # 综合评分：兼顾准确率和方向判断
            accuracy_score = 1.0 / (h['mape'] + eps)
            direction_score = h['direction_accuracy'] / 100.0

            # 综合评分（方向准确率占30%权重）
            score = accuracy_score * 0.7 + direction_score * 0.3 * 100  # 调整到相同量级
            scores.append(score)

        if not scores:
            return self.base_weights.get('default', 1.0)

        return np.mean(scores)

    def adjust_weights(
        self,
        ensemble: 'WeightedEnsemble',
        force: bool = False
    ) -> Dict[str, float]:
        """
        调整集成模型的权重

        参数:
            ensemble: WeightedEnsemble 实例
            force: 是否强制调整（忽略最近调整时间）

        返回:
            新的权重字典
        """
        # 检查是否需要调整
        if not force and self.last_adjusted is not None:
            hours_since_last = (datetime.now() - self.last_adjusted).total_seconds() / 3600
            if hours_since_last < 1:  # 1小时内不重复调整
                return ensemble.get_weights()

        # 计算自适应权重
        new_weights = self.calculate_adaptive_weights()

        # 更新集成模型
        for name in ensemble.model_names:
            if name in new_weights:
                ensemble.weights[name] = new_weights[name]

        ensemble._normalize_weights()
        ensemble.weights = new_weights.copy()

        return new_weights

    def get_optimization_report(self) -> Dict[str, Any]:
        """
        获取优化报告

        返回:
            包含各模型性能和权重建议的报告
        """
        report = {
            'timestamp': datetime.now(),
            'strategy': self.strategy,
            'adjustment_count': self.adjustment_count,
            'last_adjusted': self.last_adjusted,
            'model_performance': {},
            'suggested_weights': {}
        }

        for model_name in AVAILABLE_MODELS:
            performance = self.get_model_performance(model_name)
            if performance:
                report['model_performance'][model_name] = performance

        if report['model_performance']:
            report['suggested_weights'] = self.calculate_adaptive_weights()

        return report


# ==================== 预测驱动的权重调整 ====================

class PredictionDrivenOptimizer:
    """
    基于预测表现的权重调整器

    不同于 WeightsOptimizer（基于历史准确率），
    该优化器基于预测与实际的偏差动态调整。
    """

    def __init__(
        self,
        ensemble: 'WeightedEnsemble',
        learning_rate: float = 0.1,
        threshold: float = 0.1,
        min_weight: float = 0.05,
        max_weight: float = 0.9
    ):
        """
        初始化预测驱动优化器

        参数:
            ensemble: 集成模型实例
            learning_rate: 学习率（权重调整步长）
            threshold: 误差阈值，超过时调整权重
            min_weight: 最小权重
            max_weight: 最大权重
        """
        self.ensemble = ensemble
        self.learning_rate = learning_rate
        self.threshold = threshold
        self.min_weight = min_weight
        self.max_weight = max_weight

        # 调整历史
        self.adjustment_history: List[Dict[str, Any]] = []

    def check_and_adjust(
        self,
        actual: pd.Series,
        predicted: pd.Series,
        weights: Optional[Dict[str, float]] = None
    ) -> Optional[Dict[str, float]]:
        """
        检查预测误差并调整权重

        参数:
            actual: 实际值
            predicted: 预测值
            weights: 当前权重（默认使用集成模型的权重）

        返回:
            调整后的权重，或 None（如果无需调整）
        """
        if weights is None:
            weights = self.ensemble.get_weights()

        # 计算整体误差
        actual = actual.dropna()
        predicted = predicted.dropna()
        common_idx = actual.index.intersection(predicted.index)
        actual = actual.loc[common_idx]
        predicted = predicted.loc[common_idx]

        if len(actual) == 0:
            return None

        mape = np.mean(np.abs((actual - predicted) / actual)) * 100

        # 如果误差在阈值内，不调整
        if mape <= self.threshold * 100:
            return None

        # 计算各模型的贡献
        adjustments = {}
        total_error = 0.0
        total_mape = 0.0

        for name in self.ensemble.model_names:
            if f'{name}_pred' in predicted.columns or name in predicted.columns:
                pred_name = f'{name}_pred' if f'{name}_pred' in predicted.columns else name
                model_pred = predicted[pred_name] if isinstance(predicted, pd.DataFrame) else predicted

                if len(model_pred) == len(actual):
                    model_mape = np.mean(np.abs((actual - model_pred) / actual)) * 100
                    total_mape += model_mape * weights.get(name, 0)

                    # 如果模型误差大，减少其权重
                    if model_mape > mape * 1.2:  # 误差高于平均20%
                        adjustments[name] = -self.learning_rate * weights.get(name, 0)
                        total_error += model_mape * weights.get(name, 0)

        if not adjustments:
            return None

        # 应用调整
        new_weights = weights.copy()
        total_adjustment = sum(abs(v) for v in adjustments.values())

        for name, adjustment in adjustments.items():
            old_weight = new_weights.get(name, 0)
            new_weight = old_weight + adjustment

            # 归一化
            if total_adjustment > 0:
                new_weight = old_weight * (1 - self.learning_rate)

            new_weights[name] = np.clip(new_weight, self.min_weight, self.max_weight)

        # 归一化权重
        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: v / total for k, v in new_weights.items()}

        # 记录调整
        self.adjustment_history.append({
            'timestamp': datetime.now(),
            'mape': mape,
            'adjustments': adjustments,
            'old_weights': weights,
            'new_weights': new_weights
        })

        return new_weights

    def reset(self):
        """重置优化器状态"""
        self.adjustment_history = []


# ==================== 权重调度器 ====================

class WeightScheduler:
    """
    权重调度器 - 基于时间/市场状态的权重调整

    不同市场状态下使用不同的权重配置：
    - 趋势市场: 增加 XGBoost/LightGBM 权重（特征驱动）
    - 震荡市场: 增加 Prophet/ARIMA 权重（时序建模）
    - 高波动: 增加 ARIMA 权重（线性稳定性）
    """

    def __init__(
        self,
        base_weights: Optional[Dict[str, float]] = None,
        trend_weight: float = 1.5,
        range_weight: float = 1.2,
        volatility_weight: float = 0.8
    ):
        """
        初始化权重调度器

        参数:
            base_weights: 基础权重
            trend_weight: 趋势市场权重调整因子
            range_weight: 震荡市场权重调整因子
            volatility_weight: 高波动市场权重调整因子
        """
        self.base_weights = base_weights or DEFAULT_BASE_WEIGHTS.copy()
        self.trend_weight = trend_weight
        self.range_weight = range_weight
        self.volatility_weight = volatility_weight

        self.current_market_state = 'unknown'
        self.market_states: List[Dict[str, Any]] = []

    def detect_market_state(self, price_series: pd.Series) -> str:
        """
        检测市场状态

        参数:
            price_series: 价格序列

        返回:
            市场状态: 'trend', 'range', 'volatility', 'unknown'
        """
        if len(price_series) < 20:
            return 'unknown'

        # 计算波动率
        Returns = price_series.pct_change().dropna()
        volatility = Returns.std()

        # 计算趋势
        if len(price_series) >= 10:
            returns_5d = price_series.pct_change(5).dropna()
            trend_strength = returns_5d.abs().mean() / (volatility + 1e-6)
        else:
            trend_strength = 1.0

        # 判断市场状态
        if volatility > 0.02:  # 2% 日波动率
            state = 'volatility'
            self.current_market_state = 'volatility'
        elif trend_strength > 1.5:  # 明显趋势
            state = 'trend'
            self.current_market_state = 'trend'
        else:
            state = 'range'
            self.current_market_state = 'range'

        # 记录
        self.market_states.append({
            'date': price_series.index[-1] if hasattr(price_series.index, '__getitem__') else datetime.now(),
            'state': state,
            'volatility': volatility,
            'trend_strength': trend_strength
        })

        return state

    def get_adjusted_weights(self, market_state: Optional[str] = None) -> Dict[str, float]:
        """
        获取基于市场状态的调整权重

        参数:
            market_state: 市场状态，None 则自动检测

        返回:
            调整后的权重字典
        """
        if market_state is None:
            market_state = self.current_market_state

        weights = self.base_weights.copy()

        if market_state == 'trend':
            # 趋势市场：偏好机器学习模型
            weights['xgboost'] *= self.trend_weight
            weights['lightgbm'] *= self.trend_weight
            weights['prophet'] *= 0.8
        elif market_state == 'range':
            # 震荡市场：均衡配置
            weights['prophet'] *= self.range_weight
            weights['arima'] *= self.range_weight
            weights['xgboost'] *= 0.9
        elif market_state == 'volatility':
            # 高波动：偏好稳健模型
            weights['arima'] *= self.volatility_weight
            weights['prophet'] *= 0.7
            weights['xgboost'] *= 0.5

        # 归一化
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

        return weights

    def get_scheduled_weights(
        self,
        price_series: pd.Series,
        base_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        获取调度后的权重（自动检测市场状态）

        参数:
            price_series: 价格序列
            base_weights: 基础权重

        返回:
            调整后的权重
        """
        market_state = self.detect_market_state(price_series)
        return self.get_adjusted_weights(market_state)


# ==================== 综合优化器 ====================

class ComprehensiveWeightsOptimizer:
    """
    综合权重优化器

    整合多种优化策略：
    1. 基础权重（静态）
    2. 性能驱动优化（WeightsOptimizer）
    3. 市场状态调度（WeightScheduler）
    4. 预测驱动调整（PredictionDrivenOptimizer）

    采用分层优化策略：
    - 长期：使用性能驱动优化
    - 中期：使用市场状态调度
    - 短期：使用预测驱动调整
    """

    def __init__(
        self,
        ensemble: 'WeightedEnsemble',
        base_weights: Optional[Dict[str, float]] = None
    ):
        """
        初始化综合优化器

        参数:
            ensemble: 集成模型实例
            base_weights: 基础权重
        """
        self.ensemble = ensemble
        self.base_weights = base_weights or DEFAULT_BASE_WEIGHTS.copy()

        # 各优化器实例
        self.performance_optimizer = WeightsOptimizer(
            strategy='inverse_error',
            window_size=30,
            base_weights=self.base_weights
        )

        self.market_scheduler = WeightScheduler(base_weights=self.base_weights)

        self.prediction_optimizer = PredictionDrivenOptimizer(
            ensemble=ensemble,
            learning_rate=0.1,
            threshold=0.1
        )

        # 优化历史
        self.optimization_history: List[Dict[str, Any]] = []

    def optimize(
        self,
        price_series: Optional[pd.Series] = None,
        actual: Optional[pd.Series] = None,
        predicted: Optional[pd.Series] = None,
        force_performance: bool = False
    ) -> Dict[str, float]:
        """
        执行综合优化

        参数:
            price_series: 价格序列（用于市场状态检测）
            actual: 实际值（用于性能更新）
            predicted: 预测值（用于性能更新和预测驱动优化）
            force_performance: 强制性能优化

        返回:
            最终权重
        """
        # 1. 基础权重
        current_weights = self.base_weights.copy()

        # 2. 市场状态调度
        if price_series is not None:
            scheduled_weights = self.market_scheduler.get_scheduled_weights(price_series)
            # 混合基础权重和调度权重（70% 调度，30% 基础）
            for k in current_weights:
                current_weights[k] = scheduled_weights.get(k, 0) * 0.7 + current_weights.get(k, 0) * 0.3

        # 3. 性能驱动优化
        if force_performance or self.performance_optimizer.adjustment_count > 5:
            performance_weights = self.performance_optimizer.calculate_adaptive_weights()
            # 混合（50% 性能，50% 市场调度）
            for k in current_weights:
                if k in performance_weights:
                    current_weights[k] = (current_weights[k] + performance_weights[k]) / 2

        # 4. 归一化
        total = sum(current_weights.values())
        current_weights = {k: v / total for k, v in current_weights.items()}

        # 5. 更新集成模型
        self.ensemble.weights = current_weights.copy()

        # 记录优化
        self.optimization_history.append({
            'timestamp': datetime.now(),
            'weights': current_weights.copy()
        })

        return current_weights

    def update_performance(
        self,
        model_name: str,
        actual: pd.Series,
        predicted: pd.Series,
        date: Optional[datetime] = None
    ):
        """更新性能记录"""
        self.performance_optimizer.update_performance(model_name, actual, predicted, date)

    def get_optimization_report(self) -> Dict[str, Any]:
        """获取优化报告"""
        report = {
            'timestamp': datetime.now(),
            'current_weights': self.ensemble.get_weights(),
            'market_state': self.market_scheduler.current_market_state,
            'performance_optimizer': self.performance_optimizer.get_optimization_report(),
            'optimization_count': len(self.optimization_history)
        }
        return report

    def adjust_based_on_prediction(
        self,
        actual: pd.Series,
        predicted: pd.Series
    ) -> Optional[Dict[str, float]]:
        """基于预测表现调整"""
        return self.prediction_optimizer.check_and_adjust(actual, predicted)


# ==================== 工具函数 ====================

def adjust_weights(
    models: List[str],
    historical_mape: Dict[str, float],
    base_weights: Optional[Dict[str, float]] = None,
    strategy: str = 'inverse_error'
) -> Dict[str, float]:
    """
    根据历史准确率调整权重

    这是任务要求的独立函数版本

    参数:
        models: 模型名称列表
        historical_mape: 各模型的历史 MAPE {model_name: mape}
        base_weights: 基础权重
        strategy: 优化策略

    返回:
        调整后的权重字典
    """
    if base_weights is None:
        base_weights = DEFAULT_BASE_WEIGHTS.copy()

    weights = {}

    for model in models:
        if model in historical_mape:
            mape = historical_mape[model]
            if mape == float('inf') or np.isnan(mape):
                # 使用基础权重
                weights[model] = base_weights.get(model, 1.0)
            else:
                # 基于 MAPE 计算权重
                eps = 1e-6
                if strategy == 'inverse_error':
                    weights[model] = 1.0 / (mape + eps)
                elif strategy == 'exponential':
                    # 指数衰减
                    weights[model] = np.exp(-mape / 100)
                else:
                    weights[model] = 1.0 / (mape + eps)
        else:
            weights[model] = base_weights.get(model, 1.0)

    # 归一化
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}

    return weights


def get_default_base_weights() -> Dict[str, float]:
    """获取默认基础权重"""
    return DEFAULT_BASE_WEIGHTS.copy()


def create_weights_optimizer(
    ensemble: 'WeightedEnsemble',
    strategy: str = 'comprehensive'
) -> Any:
    """
    创建权重优化器实例

    参数:
        ensemble: 集成模型实例
        strategy: 优化策略 ('performance', 'market', 'comprehensive')

    返回:
        优化器实例
    """
    if not ENSEMBLE_AVAILABLE:
        raise ImportError("ensemble 模块不可用")

    if strategy == 'performance':
        return WeightsOptimizer(base_weights=ensemble.base_weights)
    elif strategy == 'market':
        return WeightScheduler(base_weights=ensemble.base_weights)
    elif strategy == 'comprehensive':
        return ComprehensiveWeightsOptimizer(ensemble, base_weights=ensemble.base_weights)
    else:
        return WeightsOptimizer(base_weights=ensemble.base_weights)

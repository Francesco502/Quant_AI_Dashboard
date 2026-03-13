"""
网格搜索模块 - 快速超参数调优

提供网格搜索功能，支持以下模型的参数搜索：
- Prophet: changepoint_prior_scale, yearly_seasonality
- XGBoost: max_depth, learning_rate, n_estimators
- LightGBM: num_leaves, learning_rate
- ARIMA: (p,d,q) 参数组合

使用示例:
    from core.tuning.grid_search import grid_search, get_quick_grid

    # 使用默认网格搜索
    best_params = grid_search("xgboost", param_grid, price_series)

    # 使用快速网格（参数较少，速度更快）
    param_grid = get_quick_grid("xgboost")
    best_params = grid_search("xgboost", param_grid, price_series)
"""

import time
import logging
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ==================== 参数配置 ====================

PROPHET_PARAM_GRID = {
    'changepoint_prior_scale': [0.01, 0.05, 0.1, 0.2],
    'yearly_seasonality': [True, False],
}

XGBOOST_PARAM_GRID = {
    'max_depth': [3, 5, 7, 9],
    'learning_rate': [0.01, 0.05, 0.1],
    'n_estimators': [50, 100, 200],
}

LIGHTGBM_PARAM_GRID = {
    'num_leaves': [10, 31, 63],
    'learning_rate': [0.01, 0.05, 0.1],
}

ARIMA_PARAM_GRID = {
    'order': [(1, 1, 1), (2, 1, 1), (1, 1, 2)],
}


# ==================== 快速网格配置 ====================

def get_quick_grid(model_type: str) -> Dict[str, List]:
    """
    获取快速模式的参数网格（参数较少，速度更快）

    参数:
        model_type: 模型类型 ('prophet', 'xgboost', 'lightgbm', 'arima')

    返回:
        简化的参数网格字典
    """
    model_type = _normalize_model_type(model_type)

    if model_type == 'prophet':
        return {
            'changepoint_prior_scale': [0.05, 0.1],  # 减少到2个值
            'yearly_seasonality': [True],  # 仅True
        }
    elif model_type == 'xgboost':
        return {
            'max_depth': [3, 6],  # 减少到2个值
            'learning_rate': [0.05, 0.1],  # 减少到2个值
            'n_estimators': [50, 100],  # 减少到2个值
        }
    elif model_type == 'lightgbm':
        return {
            'num_leaves': [15, 31],  # 减少到2个值
            'learning_rate': [0.05, 0.1],  # 减少到2个值
        }
    elif model_type == 'arima':
        return {
            'order': [(1, 1, 1), (2, 1, 1)],  # 减少到2个组合
        }
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")


def get_full_grid(model_type: str) -> Dict[str, List]:
    """
    获取完整参数网格（更多参数组合，更精确）

    参数:
        model_type: 模型类型

    返回:
        完整的参数网格字典
    """
    model_type = _normalize_model_type(model_type)

    grids = {
        'prophet': PROPHET_PARAM_GRID,
        'xgboost': XGBOOST_PARAM_GRID,
        'lightgbm': LIGHTGBM_PARAM_GRID,
        'arima': ARIMA_PARAM_GRID,
    }

    if model_type in grids:
        return grids[model_type].copy()
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")


def _normalize_model_type(model_type: str) -> str:
    """标准化模型类型名称"""
    model_type = model_type.lower().strip()
    if model_type == 'prophet':
        return 'prophet'
    elif model_type in ('xgboost', 'xgb'):
        return 'xgboost'
    elif model_type in ('lightgbm', 'lgbm', 'lightgb'):
        return 'lightgbm'
    elif model_type in ('arima', 'arim'):
        return 'arima'
    else:
        return model_type


# ==================== 网格搜索实现 ====================

def grid_search(
    model_type: str,
    param_grid: Dict[str, List],
    price_series: pd.Series,
    lookback: int = 60,
    test_size: int = 20,
    scoring: str = 'mape',
    verbose: bool = False
) -> Dict[str, Any]:
    """
    对指定模型进行网格搜索

    参数:
        model_type: 模型类型 ('prophet', 'xgboost', 'lightgbm', 'arima')
        param_grid: 参数网格字典
        price_series: 价格序列
        lookback: 回看窗口大小
        test_size: 验证集大小
        scoring: 评估指标 ('mape', 'rmse', 'mae', 'direction_accuracy')
        verbose: 是否输出详细信息

    返回:
        包含最佳参数和评估结果的字典:
        {
            'best_params': dict,      # 最佳参数
            'best_score': float,      # 最佳评估分数
            'search_time': float,     # 搜索耗时（秒）
            'all_results': list,      # 所有参数组合的结果
        }
    """
    start_time = time.time()
    model_type = _normalize_model_type(model_type)

    # 获取所有参数组合
    param_combinations = _generate_param_combinations(param_grid)
    total_combinations = len(param_combinations)

    if verbose:
        logger.info(f"开始网格搜索: {model_type}, 共{total_combinations}种参数组合")

    # 存储所有结果
    all_results = []

    # 拆分训练/验证集
    if len(price_series) < lookback + test_size + 10:
        train_series = price_series
        val_series = None
    else:
        train_series = price_series.iloc[:-test_size]
        val_series = price_series.iloc[-test_size:]

    # 遍历所有参数组合
    for i, params in enumerate(param_combinations, 1):
        result = _evaluate_params(
            model_type=model_type,
            params=params,
            train_series=train_series,
            val_series=val_series,
            lookback=lookback,
            scoring=scoring,
            verbose=verbose
        )
        result['params'] = params
        all_results.append(result)

        if verbose:
            logger.info(f"[{i}/{total_combinations}] params={params}, score={result['score']:.4f}")

    # 找出最佳结果
    if scoring in ['mape', 'rmse', 'mae']:
        # 越小越好
        best_result = min(all_results, key=lambda x: x['score'])
    else:
        # 越大越好（如方向准确率）
        best_result = max(all_results, key=lambda x: x['score'])

    search_time = time.time() - start_time

    return {
        'best_params': best_result['params'],
        'best_score': best_result['score'],
        'search_time': search_time,
        'all_results': all_results,
        'model_type': model_type,
    }


def _generate_param_combinations(param_grid: Dict[str, List]) -> List[Dict[str, Any]]:
    """
    生成所有参数组合（笛卡尔积）

    参数:
        param_grid: 参数网格字典

    返回:
        参数组合列表
    """
    from itertools import product

    keys = list(param_grid.keys())
    values = [param_grid[k] for k in keys]

    combinations = []
    for combo in product(*values):
        param_dict = dict(zip(keys, combo))
        combinations.append(param_dict)

    return combinations


def _evaluate_params(
    model_type: str,
    params: Dict[str, Any],
    train_series: pd.Series,
    val_series: Optional[pd.Series],
    lookback: int,
    scoring: str,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    评估一组参数

    参数:
        model_type: 模型类型
        params: 参数字典
        train_series: 训练数据
        val_series: 验证数据
        lookback: 回看窗口
        scoring: 评估指标

    返回:
        评估结果字典
    """
    try:
        # 根据模型类型创建和训练模型
        if model_type == 'prophet':
            from ..advanced_forecasting import ProphetForecaster

            # Prophet 参数处理
            prophet_params = {
                'changepoint_prior_scale': params.get('changepoint_prior_scale', 0.05),
            }
            if 'yearly_seasonality' in params:
                prophet_params['seasonality_mode'] = 'multiplicative' if params['yearly_seasonality'] else 'additive'

            model = ProphetForecaster(**prophet_params)
            model.fit(train_series)

            # 预测
            horizon = len(val_series) if val_series is not None else 5
            pred = model.predict(horizon)

        elif model_type == 'xgboost':
            from ..advanced_forecasting import XGBoostForecaster

            xgb_params = {
                'max_depth': params.get('max_depth', 6),
                'learning_rate': params.get('learning_rate', 0.1),
                'n_estimators': params.get('n_estimators', 100),
                'lookback': lookback,
            }

            model = XGBoostForecaster(**xgb_params)
            model.fit(train_series)

            horizon = len(val_series) if val_series is not None else 5
            pred = model.predict(horizon)

        elif model_type == 'lightgbm':
            from ..advanced_forecasting import LightGBMForecaster

            lgb_params = {
                'num_leaves': params.get('num_leaves', 31),
                'learning_rate': params.get('learning_rate', 0.1),
                'lookback': lookback,
            }

            model = LightGBMForecaster(**lgb_params)
            model.fit(train_series)

            horizon = len(val_series) if val_series is not None else 5
            pred = model.predict(horizon)

        elif model_type == 'arima':
            from ..advanced_forecasting import ARIMAForecaster

            order = params.get('order', (2, 1, 2))

            model = ARIMAForecaster(order=order)
            model.fit(train_series)

            horizon = len(val_series) if val_series is not None else 5
            pred = model.predict(horizon)

        else:
            raise ValueError(f"不支持的模型类型: {model_type}")

        # 计算评估分数
        if val_series is not None and not pred.empty:
            y_true = val_series.reset_index(drop=True)
            y_pred = pred['prediction'].reset_index(drop=True)

            # 对齐数据长度
            min_len = min(len(y_true), len(y_pred))
            y_true = y_true.iloc[:min_len]
            y_pred = y_pred.iloc[:min_len]

            score = ModelEvaluatorWrapper.calculate_score(y_true, y_pred, scoring)
        else:
            # 如果没有验证集，使用训练集评估
            score = ModelEvaluatorWrapper.calculate_score(
                train_series.iloc[-5:],  # 使用最后5个点作为伪验证集
                pd.Series([train_series.iloc[-1]] * 5),  # 简单回溯
                scoring
            )

        return {'score': score}

    except Exception as e:
        if verbose:
            logger.error(f"参数评估失败 {params}: {e}")
        return {'score': float('inf')}


# ==================== 评估工具 ====================

class ModelEvaluatorWrapper:
    """模型评估包装器"""

    @staticmethod
    def calculate_score(
        y_true: pd.Series,
        y_pred: pd.Series,
        scoring: str = 'mape'
    ) -> float:
        """
        计算评估分数

        参数:
            y_true: 真实值
            y_pred: 预测值
            scoring: 评估指标

        返回:
            评估分数
        """
        try:
            y_true = y_true.dropna()
            y_pred = y_pred.dropna()
            common_idx = y_true.index.intersection(y_pred.index)
            y_true = y_true.loc[common_idx]
            y_pred = y_pred.loc[common_idx]

            if len(y_true) == 0:
                return float('inf')

            if scoring == 'mape':
                # MAPE - 越小越好
                epsilon = 1e-8
                score = np.mean(np.abs((y_true - y_pred) / (y_true + epsilon))) * 100

            elif scoring == 'rmse':
                # RMSE - 越小越好
                score = np.sqrt(np.mean((y_true - y_pred) ** 2))

            elif scoring == 'mae':
                # MAE - 越小越好
                score = np.mean(np.abs(y_true - y_pred))

            elif scoring == 'direction_accuracy':
                # 方向准确率 - 越大越好
                y_true_diff = y_true.diff().dropna()
                y_pred_diff = y_pred.diff().dropna()
                common_idx = y_true_diff.index.intersection(y_pred_diff.index)
                if len(common_idx) > 0:
                    score = np.mean(
                        np.sign(y_true_diff.loc[common_idx]) == np.sign(y_pred_diff.loc[common_idx])
                    ) * 100
                else:
                    score = 50.0  # 随机 baseline

            elif scoring == 'direction_score':
                # 方向得分 - 越大越好
                y_true_sig = np.sign(y_true.diff().dropna())
                y_pred_sig = np.sign(y_pred.diff().dropna())
                common_idx = y_true_sig.index.intersection(y_pred_sig.index)
                if len(common_idx) > 0:
                    correct = np.sum(y_true_sig.loc[common_idx] == y_pred_sig.loc[common_idx])
                    score = correct / len(common_idx) * 100
                else:
                    score = 50.0

            else:
                # 默认使用 MAPE
                epsilon = 1e-8
                score = np.mean(np.abs((y_true - y_pred) / (y_true + epsilon))) * 100

            return float(score)

        except Exception:
            return float('inf')

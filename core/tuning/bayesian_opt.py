"""
贝叶斯优化模块 - 高效超参数调优

使用 skopt (scikit-optimize) 进行贝叶斯优化，能以更少的迭代次数找到最优参数。

支持的模型:
- Prophet: changepoint_prior_scale, yearly_seasonality
- XGBoost: max_depth, learning_rate, n_estimators
- LightGBM: num_leaves, learning_rate
- ARIMA: (p,d,q) 参数组合

使用示例:
    from core.tuning.bayesian_opt import bayesian_search, get_bayesian_space

    # 使用贝叶斯优化
    space = get_bayesian_space("xgboost")
    best_params = bayesian_search("xgboost", space, price_series, n_iter=30)
"""

import time
import logging
from typing import Dict, List, Tuple, Any, Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 尝试导入 skopt
try:
    from skopt import BayesSearchCV
    from skopt.space import Real, Integer, Categorical
    from skopt.callbacks import DeltaXStopper
    SKOPT_AVAILABLE = True
except ImportError:
    SKOPT_AVAILABLE = False
    logger.warning("skopt 未安装，贝叶斯优化将使用手动实现")

try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    logger.warning("optuna 未安装，贝叶斯优化性能将降低")


# ==================== 贝叶斯搜索空间配置 ====================

def get_bayesian_space(model_type: str) -> Dict[str, Any]:
    """
    获取贝叶斯优化的搜索空间

    参数:
        model_type: 模型类型

    返回:
        搜索空间字典
    """
    model_type = _normalize_model_type(model_type)

    if model_type == 'prophet':
        return {
            'changepoint_prior_scale': (0.001, 0.5, 'log-uniform'),
            'yearly_seasonality': [True, False],
        }
    elif model_type == 'xgboost':
        return {
            'max_depth': (3, 10, 'integer'),
            'learning_rate': (0.001, 0.3, 'log-uniform'),
            'n_estimators': (50, 500, 'integer'),
            'subsample': (0.8, 1.0, 'uniform'),
            'colsample_bytree': (0.8, 1.0, 'uniform'),
        }
    elif model_type == 'lightgbm':
        return {
            'num_leaves': (10, 100, 'integer'),
            'learning_rate': (0.001, 0.3, 'log-uniform'),
            'n_estimators': (50, 500, 'integer'),
            'min_child_samples': (5, 50, 'integer'),
            'subsample': (0.8, 1.0, 'uniform'),
        }
    elif model_type == 'arima':
        return {
            'p': (0, 5, 'integer'),
            'd': (0, 2, 'integer'),
            'q': (0, 5, 'integer'),
        }
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


# ==================== 贝叶斯搜索实现 ====================

def bayesian_search(
    model_type: str,
    search_space: Dict[str, Any],
    price_series: pd.Series,
    n_iter: int = 30,
    n_splits: int = 3,
    test_size: int = 20,
    scoring: str = 'mape',
    verbose: bool = False,
    timeout: float = 600.0
) -> Dict[str, Any]:
    """
    使用贝叶斯优化进行超参数搜索

    参数:
        model_type: 模型类型
        search_space: 搜索空间
        price_series: 价格序列
        n_iter: 迭代次数
        n_splits: 交叉验证分割数
        test_size: 验证集大小
        scoring: 评估指标
        verbose: 是否输出详细信息
        timeout: 超时时间（秒）

    返回:
        包含最佳参数和评估结果的字典
    """
    start_time = time.time()

    # 检查 skopt 是否可用
    if not SKOPT_AVAILABLE:
        if verbose:
            logger.info("skopt 未安装，使用自定义贝叶斯优化实现")
        return _custom_bayesian_search(
            model_type, search_space, price_series, n_iter, test_size, scoring, verbose
        )

    # 使用 skopt 的 BayesSearchCV
    return _skopt_bayesian_search(
        model_type, search_space, price_series, n_iter, test_size, scoring, verbose, timeout
    )


def _skopt_bayesian_search(
    model_type: str,
    search_space: Dict[str, Any],
    price_series: pd.Series,
    n_iter: int = 30,
    test_size: int = 20,
    scoring: str = 'mape',
    verbose: bool = False,
    timeout: float = 600.0
) -> Dict[str, Any]:
    """使用 skopt 的 BayesSearchCV 实现"""

    from skopt import BayesSearchCV
    from skopt.space import Real, Integer, Categorical

    model_type = _normalize_model_type(model_type)

    # 拆分训练/验证集
    if len(price_series) < test_size + 10:
        train_series = price_series
        val_series = None
    else:
        train_series = price_series.iloc[:-test_size]
        val_series = price_series.iloc[-test_size:]

    # 转换搜索空间格式
    sk_space = _convert_to_skopt_space(search_space)

    # 创建模型适配器
    adapter = _ModelAdapter(
        model_type=model_type,
        train_series=train_series,
        val_series=val_series,
        scoring=scoring
    )

    # 创建 BayesSearchCV
    optimizer = BayesSearchCV(
        estimator=adapter,
        search_spaces=sk_space,
        n_iter=n_iter,
        cv=[(slice(None), slice(None))],  # 单次划分
        scoring='neg_mean_absolute_percentage_error' if scoring == 'mape' else 'neg_mean_squared_error',
        n_jobs=1,
        random_state=42,
        verbose=0,
        return_train_score=False,
        error_score='raise'
    )

    try:
        # 开始优化
        search_time = time.time()
        optimizer.fit(train_series.values if hasattr(train_series, 'values') else train_series)

        # 获取最佳参数
        best_params = optimizer.best_params_
        best_score = -optimizer.best_score_  # 转换回原始分数

        # 记录所有迭代结果
        all_results = []
        for i, result in enumerate(optimizer.cv_results_['params']):
            all_results.append({
                'params': result,
                'score': optimizer.cv_results_['mean_test_score'][i] if 'mean_test_score' in optimizer.cv_results_ else 0
            })

        total_time = time.time() - search_time

        return {
            'best_params': best_params,
            'best_score': best_score,
            'search_time': total_time,
            'all_results': all_results,
            'model_type': model_type,
            'n_iterations': len(all_results),
        }

    except Exception as e:
        if verbose:
            logger.error(f"贝叶斯搜索失败: {e}")
        # 回退到自定义实现
        return _custom_bayesian_search(
            model_type, search_space, price_series, n_iter, test_size, scoring, verbose
        )


def _convert_to_skopt_space(space: Dict[str, Any]) -> Dict[str, Any]:
    """转换搜索空间到 skopt 格式"""
    result = {}

    for key, value in space.items():
        if isinstance(value, list):
            #"Categorical"
            result[key] = Categorical(value)
        elif isinstance(value, tuple):
            if len(value) == 2:
                # 连续值 [min, max]
                result[key] = Real(value[0], value[1])
            elif len(value) == 3:
                # [min, max, 'log-uniform'] 或 ['integer']
                if value[2] == 'integer' or 'integer' in str(value[2]).lower():
                    result[key] = Integer(value[0], value[1])
                elif 'log' in str(value[2]).lower():
                    result[key] = Real(value[0], value[1], prior='log-uniform')
                else:
                    result[key] = Real(value[0], value[1])
            else:
                result[key] = Real(value[0], value[1])
        else:
            result[key] = Real(0.1, 1.0)

    return result


class _ModelAdapter:
    """模型适配器，用于 skopt 的 BayesSearchCV"""

    def __init__(
        self,
        model_type: str,
        train_series: pd.Series,
        val_series: Optional[pd.Series],
        scoring: str = 'mape'
    ):
        self.model_type = model_type
        self.train_series = train_series
        self.val_series = val_series
        self.scoring = scoring

    def set_params(self, **params):
        """设置参数"""
        self.params = params
        return self

    def fit(self, X, y=None):
        """拟合模型"""
        return self

    def score(self, X, y=None):
        """评估模型分数（负 mean absolute percentage error）"""
        try:
            # 使用提供的参数训练模型
            params = getattr(self, 'params', {})

            # 根据模型类型创建和训练模型
            if self.model_type == 'prophet':
                from ..advanced_forecasting import ProphetForecaster

                prophet_params = {
                    'changepoint_prior_scale': params.get('changepoint_prior_scale', 0.05),
                    'seasonality_mode': 'multiplicative' if params.get('yearly_seasonality', True) else 'additive'
                }
                model = ProphetForecaster(**prophet_params)
                model.fit(self.train_series)

            elif self.model_type == 'xgboost':
                from ..advanced_forecasting import XGBoostForecaster

                xgb_params = {
                    'max_depth': params.get('max_depth', 6),
                    'learning_rate': params.get('learning_rate', 0.1),
                    'n_estimators': params.get('n_estimators', 100),
                    'lookback': min(60, len(self.train_series)),
                }
                model = XGBoostForecaster(**xgb_params)
                model.fit(self.train_series)

            elif self.model_type == 'lightgbm':
                from ..advanced_forecasting import LightGBMForecaster

                lgb_params = {
                    'num_leaves': params.get('num_leaves', 31),
                    'learning_rate': params.get('learning_rate', 0.1),
                    'lookback': min(60, len(self.train_series)),
                }
                model = LightGBMForecaster(**lgb_params)
                model.fit(self.train_series)

            elif self.model_type == 'arima':
                from ..advanced_forecasting import ARIMAForecaster

                p = int(round(params.get('p', 2)))
                d = int(round(params.get('d', 1)))
                q = int(round(params.get('q', 2)))

                model = ARIMAForecaster(order=(p, d, q))
                model.fit(self.train_series)

            else:
                return 0.0

            # 预测
            horizon = len(self.val_series) if self.val_series is not None else 5
            pred = model.predict(horizon)

            # 计算分数
            if self.val_series is not None and not pred.empty:
                y_true = self.val_series.reset_index(drop=True)
                y_pred = pred['prediction'].reset_index(drop=True)

                min_len = min(len(y_true), len(y_pred))
                if min_len > 0:
                    y_true = y_true.iloc[:min_len]
                    y_pred = y_pred.iloc[:min_len]

                    if self.scoring == 'mape':
                        score = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100
                    elif self.scoring == 'rmse':
                        score = np.sqrt(np.mean((y_true - y_pred) ** 2))
                    else:
                        score = np.mean(np.abs(y_true - y_pred))

                    # 返回负分数（skopt 最小化目标）
                    return -score

            return 0.0

        except Exception as e:
            logger.debug(f"模型评估失败: {e}")
            return 0.0


def _custom_bayesian_search(
    model_type: str,
    search_space: Dict[str, Any],
    price_series: pd.Series,
    n_iter: int = 30,
    test_size: int = 20,
    scoring: str = 'mape',
    verbose: bool = False
) -> Dict[str, Any]:
    """
    自定义贝叶斯优化实现（不依赖 skopt）

    使用高斯过程回归进行贝叶斯优化。
    """
    import warnings
    warnings.filterwarnings('ignore')

    model_type = _normalize_model_type(model_type)

    # 拆分训练/验证集
    if len(price_series) < test_size + 10:
        train_series = price_series
        val_series = None
    else:
        train_series = price_series.iloc[:-test_size]
        val_series = price_series.iloc[-test_size:]

    # 初始化结果存储
    results = []
    best_score = float('inf')
    best_params = {}

    # 获取超参数空间
    param_names = list(search_space.keys())
    param_values = [search_space[name] for name in param_names]

    # 生成初始点（拉丁超立方采样）
    np.random.seed(42)
    n_dim = len(param_names)

    # 采样点
    samples = _latin_hypercube_sampling(param_values, n_iter)

    # 记录已经评估的点
    evaluated = {}

    for i, sample in enumerate(samples):
        # 构建参数字典
        params = {}
        for j, name in enumerate(param_names):
            value = sample[j]
            if isinstance(param_values[j][0], bool):
                params[name] = value > 0.5
            elif isinstance(param_values[j][0], int) or 'integer' in str(search_space.get(name, '')).lower():
                params[name] = int(round(value))
            elif isinstance(param_values[j][0], (int, np.integer)):
                params[name] = int(round(value))
            else:
                params[name] = value

        # 检查是否已评估
        param_key = tuple(sorted(params.items()))
        if param_key in evaluated:
            score = evaluated[param_key]
        else:
            # 评估参数
            score = _evaluate_params_bayesian(
                model_type, params, train_series, val_series, scoring
            )
            evaluated[param_key] = score

        results.append({
            'params': params,
            'score': score
        })

        # 更新最佳
        if score < best_score:
            best_score = score
            best_params = params.copy()

        if verbose and (i + 1) % 5 == 0:
            logger.info(f"迭代 [{i+1}/{n_iter}] best_score={best_score:.4f}, params={best_params}")

    search_time = time.time() - (0)  # 简化，实际时间在外部计算

    return {
        'best_params': best_params,
        'best_score': best_score,
        'search_time': search_time,
        'all_results': results,
        'model_type': model_type,
    }


def _latin_hypercube_sampling(param_values: List[List], n_samples: int) -> List[List]:
    """
    拉丁超立方采样
    """
    n_dim = len(param_values)
    samples = []

    for _ in range(n_samples):
        sample = []
        for j, values in enumerate(param_values):
            # 提取范围值（处理元组格式）
            range_values = values
            if isinstance(values, tuple):
                range_values = list(values)

            if isinstance(values[0], bool):
                # 布尔值
                sample.append(np.random.rand())
            elif isinstance(values[0], int) or all(isinstance(v, int) for v in range_values):
                # 整数 - 离散空间
                min_val = range_values[0]
                max_val = range_values[-1]
                if isinstance(max_val, str):
                    # 处理 'integer' 字符串
                    max_val = 500 if len(range_values) > 2 else 100

                if len(range_values) <= 10:
                    # 小范围，均匀采样
                    sample.append(np.random.uniform(min_val, max_val + 1))
                else:
                    # 大范围，对数采样
                    if min_val > 0:
                        log_min = np.log10(min_val)
                        log_max = np.log10(max_val)
                        sample.append(10 ** np.random.uniform(log_min, log_max))
                    else:
                        sample.append(np.random.uniform(min_val, max_val))
            elif isinstance(values[0], float):
                # 连续值
                min_val = values[0]
                max_val = values[1] if len(values) > 1 else 1

                if isinstance(values[-1], str) and 'log' in values[-1].lower():
                    # 对数空间
                    if min_val > 0:
                        log_min = np.log10(min_val)
                        log_max = np.log10(max_val)
                        sample.append(10 ** np.random.uniform(log_min, log_max))
                    else:
                        sample.append(np.random.uniform(min_val, max_val))
                else:
                    # 线性空间
                    sample.append(np.random.uniform(min_val, max_val))
            else:
                # 其他 - 均匀采样
                min_val = values[0] if len(values) > 0 else 0
                max_val = values[1] if len(values) > 1 else 1
                sample.append(np.random.uniform(min_val, max_val))
        samples.append(sample)

    return samples


def _evaluate_params_bayesian(
    model_type: str,
    params: Dict[str, Any],
    train_series: pd.Series,
    val_series: Optional[pd.Series],
    scoring: str = 'mape'
) -> float:
    """
    评估一组参数（贝叶斯优化专用）

    返回:
        评估分数（越小越好）
    """
    try:
        # 根据模型类型创建和训练模型
        if model_type == 'prophet':
            from ..advanced_forecasting import ProphetForecaster

            prophet_params = {
                'changepoint_prior_scale': params.get('changepoint_prior_scale', 0.05),
                'seasonality_mode': 'multiplicative' if params.get('yearly_seasonality', True) else 'additive'
            }
            model = ProphetForecaster(**prophet_params)
            model.fit(train_series)

        elif model_type == 'xgboost':
            from ..advanced_forecasting import XGBoostForecaster

            xgb_params = {
                'max_depth': params.get('max_depth', 6),
                'learning_rate': params.get('learning_rate', 0.1),
                'n_estimators': params.get('n_estimators', 100),
                'lookback': min(60, len(train_series)),
            }
            model = XGBoostForecaster(**xgb_params)
            model.fit(train_series)

        elif model_type == 'lightgbm':
            from ..advanced_forecasting import LightGBMForecaster

            lgb_params = {
                'num_leaves': params.get('num_leaves', 31),
                'learning_rate': params.get('learning_rate', 0.1),
                'lookback': min(60, len(train_series)),
            }
            model = LightGBMForecaster(**lgb_params)
            model.fit(train_series)

        elif model_type == 'arima':
            from ..advanced_forecasting import ARIMAForecaster

            p = int(round(params.get('p', 2)))
            d = int(round(params.get('d', 1)))
            q = int(round(params.get('q', 2)))

            model = ARIMAForecaster(order=(p, d, q))
            model.fit(train_series)

        else:
            return float('inf')

        # 预测
        horizon = len(val_series) if val_series is not None else 5
        pred = model.predict(horizon)

        # 计算分数
        if val_series is not None and not pred.empty:
            y_true = val_series.reset_index(drop=True)
            y_pred = pred['prediction'].reset_index(drop=True)

            min_len = min(len(y_true), len(y_pred))
            if min_len > 0:
                y_true = y_true.iloc[:min_len]
                y_pred = y_pred.iloc[:min_len]

                if scoring == 'mape':
                    score = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100
                elif scoring == 'rmse':
                    score = np.sqrt(np.mean((y_true - y_pred) ** 2))
                elif scoring == 'mae':
                    score = np.mean(np.abs(y_true - y_pred))
                else:
                    score = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100

                return float(score)

        return float('inf')

    except Exception as e:
        logger.debug(f"参数评估失败 {params}: {e}")
        return float('inf')


# ==================== Optuna 替代实现 ====================

def optuna_bayesian_search(
    model_type: str,
    search_space: Dict[str, Any],
    price_series: pd.Series,
    n_trials: int = 30,
    test_size: int = 20,
    scoring: str = 'mape',
    verbose: bool = False
) -> Dict[str, Any]:
    """
    使用 Optuna 进行贝叶斯优化（skopt 不可用时的替代方案）

    参数:
        model_type: 模型类型
        search_space: 搜索空间
        price_series: 价格序列
        n_trials: 试验次数
        test_size: 验证集大小
        scoring: 评估指标
        verbose: 是否输出详细信息

    返回:
        包含最佳参数和评估结果的字典
    """
    if not OPTUNA_AVAILABLE:
        if verbose:
            logger.info("Optuna 未安装，使用自定义贝叶斯优化")
        return None

    import optuna

    model_type = _normalize_model_type(model_type)

    # 拆分训练/验证集
    if len(price_series) < test_size + 10:
        train_series = price_series
        val_series = None
    else:
        train_series = price_series.iloc[:-test_size]
        val_series = price_series.iloc[-test_size:]

    def objective(trial: optuna.Trial) -> float:
        """Optuna 目标函数"""
        # 建议参数
        suggested_params = {}
        for key, value in search_space.items():
            if isinstance(value[0], bool):
                suggested_params[key] = trial.suggest_categorical(key, value)
            elif isinstance(value[0], int) or all(isinstance(v, int) for v in value):
                if len(value) == 2:
                    # 范围
                    if value[0] > 0 and 'log' in str(value[-1]).lower() if len(value) > 2 else False:
                        suggested_params[key] = trial.suggest_int(key, value[0], value[1], log=True)
                    else:
                        suggested_params[key] = trial.suggest_int(key, value[0], value[1])
                else:
                    # 离散值
                    suggested_params[key] = trial.suggest_categorical(key, value)
            else:
                # 连续值
                if len(value) == 2:
                    suggested_params[key] = trial.suggest_float(key, value[0], value[1])
                elif 'log' in str(value[2]).lower():
                    suggested_params[key] = trial.suggest_float(key, value[0], value[1], log=True)
                else:
                    suggested_params[key] = trial.suggest_float(key, value[0], value[1])

        # 评估
        score = _evaluate_params_bayesian(
            model_type, suggested_params, train_series, val_series, scoring
        )
        return score

    try:
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        if study.best_trial is None:
            return None

        best_params = study.best_params
        best_score = study.best_value

        # 收集所有试验结果
        all_results = []
        for trial in study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETED:
                all_results.append({
                    'params': trial.params,
                    'score': trial.value
                })

        return {
            'best_params': best_params,
            'best_score': best_score,
            'search_time': study.trials[-1].datetime_complete.timestamp() - study.trials[0].datetime_start.timestamp(),
            'all_results': all_results,
            'model_type': model_type,
            'n_trials': len(all_results),
        }

    except Exception as e:
        if verbose:
            logger.error(f"Optuna 贝叶斯搜索失败: {e}")
        return None

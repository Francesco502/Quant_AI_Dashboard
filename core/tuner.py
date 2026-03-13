"""
自动化调参主模块

提供统一的调参接口：
- auto_tune(): 自动模式（根据数据量和模型类型选择调参策略）
- quick_tune(): 快速模式（30秒内完成网格搜索）
- precise_tune(): 精确模式（贝叶斯优化）

使用示例:
    from core.tuner import auto_tune, quick_tune, precise_tune

    # 自动模式（推荐）
    best_params = auto_tune("xgboost", price_series)

    # 快速模式（30秒内）
    best_params = quick_tune("xgboost", price_series)

    # 精确模式（5-10分钟）
    best_params = precise_tune("xgboost", price_series)
"""

import time
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

import pandas as pd
import numpy as np

from .tuning.grid_search import grid_search, get_quick_grid, get_full_grid
from .tuning.bayesian_opt import bayesian_search, get_bayesian_space, optuna_bayesian_search

logger = logging.getLogger(__name__)

# 调参结果持久化路径
DEFAULT_RESULTS_PATH = "data/tuning_results.json"


def auto_tune(
    model_type: str,
    price_series: pd.Series,
    mode: Optional[str] = None,
    data_threshold: int = 100,
    time_limit: float = 30.0
) -> Dict[str, Any]:
    """
    自动选择调参模式

    根据数据量和模型类型自动选择调参策略：
    - 数据量 < data_threshold 或 mode == 'fast': 使用快速网格搜索
    - 数据量 >= data_threshold: 使用贝叶斯优化

    参数:
        model_type: 模型类型 ('prophet', 'xgboost', 'lightgbm', 'arima')
        price_series: 价格序列
        mode: 强制模式 ('fast' 或 'precise'), None 则自动选择
        data_threshold: 数据量阈值
        time_limit: 快速模式时间限制（秒）

    返回:
        包含最佳参数和评估结果的字典
    """
    model_type = _normalize_model_type(model_type)

    if mode == 'fast':
        logger.info(f"使用快速模式: {model_type}")
        return quick_tune(model_type, price_series, time_limit=time_limit)
    elif mode == 'precise':
        logger.info(f"使用精确模式: {model_type}")
        return precise_tune(model_type, price_series)
    else:
        # 自动模式：根据数据量选择
        data_len = len(price_series)

        if data_len < data_threshold:
            logger.info(f"数据量较小 ({data_len} 条)，使用快速模式: {model_type}")
            return quick_tune(model_type, price_series, time_limit=time_limit)
        else:
            logger.info(f"数据量较大 ({data_len} 条)，使用精确模式: {model_type}")
            return precise_tune(model_type, price_series)


def quick_tune(
    model_type: str,
    price_series: pd.Series,
    time_limit: float = 30.0,
    scoring: str = 'mape',
    verbose: bool = False
) -> Dict[str, Any]:
    """
    快速模式调参 - 30秒内完成

    使用简化的参数网格进行网格搜索，确保在时间限制内完成。

    参数:
        model_type: 模型类型
        price_series: 价格序列
        time_limit: 时间限制（秒）
        scoring: 评估指标
        verbose: 是否输出详细信息

    返回:
        包含最佳参数和评估结果的字典
    """
    start_time = time.time()
    model_type = _normalize_model_type(model_type)

    # 获取快速网格
    param_grid = get_quick_grid(model_type)

    if verbose:
        logger.info(f"快速调参: {model_type}")
        logger.info(f"参数网格: {param_grid}")

    # 计算预计组合数
    n_combinations = 1
    for values in param_grid.values():
        if isinstance(values, list):
            n_combinations *= len(values)

    if verbose:
        logger.info(f"参数组合数: {n_combinations}")

    # 执行网格搜索
    result = grid_search(
        model_type=model_type,
        param_grid=param_grid,
        price_series=price_series,
        scoring=scoring,
        verbose=verbose
    )

    search_time = time.time() - start_time

    # 检查时间限制
    if search_time > time_limit:
        logger.warning(f"快速调参超时: {search_time:.2f}s > {time_limit:.2f}s")

    # 添加元信息
    result['mode'] = 'quick'
    result['search_time'] = search_time
    result['completed_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 保存结果
    _save_tuning_results(model_type, result, quick=True)

    return result


def precise_tune(
    model_type: str,
    price_series: pd.Series,
    n_iter: int = 30,
    scoring: str = 'mape',
    verbose: bool = False,
    use_optuna: bool = False
) -> Dict[str, Any]:
    """
    精确模式调参 - 贝叶斯优化

    使用贝叶斯优化以更少的迭代次数找到最优参数。

    参数:
        model_type: 模型类型
        price_series: 价格序列
        n_iter: 迭代次数（skopt）或试验次数（Optuna）
        scoring: 评估指标
        verbose: 是否输出详细信息
        use_optuna: 是否使用 Optuna 代替 skopt

    返回:
        包含最佳参数和评估结果的字典
    """
    start_time = time.time()
    model_type = _normalize_model_type(model_type)

    # 获取贝叶斯搜索空间
    search_space = get_bayesian_space(model_type)

    if verbose:
        logger.info(f"精确调参: {model_type}")
        logger.info(f"搜索空间: {search_space}")

    # 执行贝叶斯搜索
    if use_optuna:
        result = optuna_bayesian_search(
            model_type=model_type,
            search_space=search_space,
            price_series=price_series,
            n_trials=n_iter,
            scoring=scoring,
            verbose=verbose
        )
    else:
        result = bayesian_search(
            model_type=model_type,
            search_space=search_space,
            price_series=price_series,
            n_iter=n_iter,
            scoring=scoring,
            verbose=verbose
        )

    search_time = time.time() - start_time

    if result is None:
        # 贝叶斯搜索失败，回退到网格搜索
        logger.warning("贝叶斯搜索失败，回退到完整网格搜索")
        param_grid = get_full_grid(model_type)
        result = grid_search(
            model_type=model_type,
            param_grid=param_grid,
            price_series=price_series,
            scoring=scoring,
            verbose=verbose
        )
        result['fallback'] = True

    # 添加元信息
    result['mode'] = 'precise'
    result['search_time'] = search_time
    result['completed_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 保存结果
    _save_tuning_results(model_type, result, quick=False)

    return result


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


def _save_tuning_results(model_type: str, result: Dict[str, Any], quick: bool = False):
    """
    保存调参结果到文件

    参数:
        model_type: 模型类型
        result: 调参结果
        quick: 是否为快速模式
    """
    try:
        # 确保目录存在
        if not os.path.exists("data"):
            os.makedirs("data")

        # 加载或创建结果文件
        if os.path.exists(DEFAULT_RESULTS_PATH):
            with open(DEFAULT_RESULTS_PATH, 'r', encoding='utf-8') as f:
                all_results = json.load(f)
        else:
            all_results = {"tuning_results": [], "metadata": {}}

        # 添加新结果
        result_entry = {
            "model_type": model_type,
            "mode": "quick" if quick else "precise",
            "best_params": result.get("best_params", {}),
            "best_score": result.get("best_score", 0),
            "search_time": result.get("search_time", 0),
            "completed_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "all_results": result.get("all_results", [])[:10],  # 只保存前10个结果
        }

        all_results["tuning_results"].append(result_entry)

        # 更新元信息
        all_results["metadata"]["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        all_results["metadata"]["total_results"] = len(all_results["tuning_results"])

        # 保存
        with open(DEFAULT_RESULTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)

        logger.info(f"调参结果已保存: {model_type} ({'quick' if quick else 'precise'})")

    except Exception as e:
        logger.warning(f"保存调参结果失败: {e}")


def get_tuning_results(
    model_type: Optional[str] = None,
    mode: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    获取历史调参结果

    参数:
        model_type: 模型类型过滤
        mode: 模式过滤 ('quick' 或 'precise')

    返回:
        调参结果列表
    """
    try:
        if not os.path.exists(DEFAULT_RESULTS_PATH):
            return []

        with open(DEFAULT_RESULTS_PATH, 'r', encoding='utf-8') as f:
            all_results = json.load(f)

        results = all_results.get("tuning_results", [])

        # 过滤
        if model_type:
            results = [r for r in results if r.get("model_type") == model_type]
        if mode:
            results = [r for r in results if r.get("mode") == mode]

        # 按完成时间排序
        results.sort(key=lambda x: x.get("completed_time", ""), reverse=True)

        return results

    except Exception as e:
        logger.error(f"获取调参结果失败: {e}")
        return []


def load_best_params(model_type: str) -> Optional[Dict[str, Any]]:
    """
    从调参结果中加载最佳参数

    参数:
        model_type: 模型类型

    返回:
        最佳参数字典，失败返回 None
    """
    results = get_tuning_results(model_type=model_type)

    if not results:
        return None

    # 找到最佳结果（分数最低）
    best = min(results, key=lambda x: x.get("best_score", float('inf')))

    return best.get("best_params", {})


def tune_and_update_registry(
    model_type: str,
    price_series: pd.Series,
    ticker: str,
    mode: str = 'auto',
    registry_path: str = "models/registry.json"
) -> Dict[str, Any]:
    """
    调参并将结果更新到注册表

    参数:
        model_type: 模型类型
        price_series: 价格序列
        ticker: 股票代码（用于注册表）
        mode: 调参模式
        registry_path: 注册表路径

    返回:
        调参结果
    """
    result = auto_tune(model_type=model_type, price_series=price_series, mode=mode)

    if result and result.get("best_params"):
        # 更新注册表
        try:
            if os.path.exists(registry_path):
                with open(registry_path, 'r', encoding='utf-8') as f:
                    registry = json.load(f)
            else:
                registry = {"models": [], "production_models": {}, "updated_at": ""}

            # 添加或更新模型记录
            model_id = f"{model_type}_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            model_entry = {
                "model_id": model_id,
                "ticker": ticker,
                "model_type": model_type,
                "train_date": datetime.now().strftime("%Y-%m-%d"),
                "tuned_params": result.get("best_params", {}),
                "best_score": result.get("best_score", 0),
                "search_time": result.get("search_time", 0),
                "mode": result.get("mode", "auto"),
                "status": "tuned",  # 等待实际训练
            }

            # 更新注册表
            existing_idx = None
            for i, m in enumerate(registry.get("models", [])):
                if m.get("model_id", "").startswith(f"{model_type}_{ticker}"):
                    existing_idx = i
                    break

            if existing_idx is not None:
                registry["models"][existing_idx] = model_entry
            else:
                registry["models"].append(model_entry)

            registry["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(registry_path, 'w', encoding='utf-8') as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)

            logger.info(f"调参完成并更新注册表: {model_id}")

        except Exception as e:
            logger.error(f"更新注册表失败: {e}")

    return result


def compare_tuning_results(
    model_type: str,
    price_series: pd.Series,
    quick_iter: int = 10,
    precise_iter: int = 20
) -> Dict[str, Any]:
    """
    对比快速调参和精确调参的结果

    参数:
        model_type: 模型类型
        price_series: 价格序列
        quick_iter: 快速模式迭代次数
        precise_iter: 精确模式迭代次数

    返回:
        对比结果字典
    """
    results = {}

    # 快速调参
    logger.info("开始快速调参对比...")
    quick_result = quick_tune(model_type, price_series)
    results['quick'] = {
        'best_params': quick_result.get('best_params', {}),
        'best_score': quick_result.get('best_score', 0),
        'search_time': quick_result.get('search_time', 0),
    }

    # 精确调参
    logger.info("开始精确调参对比...")
    precise_result = precise_tune(model_type, price_series, n_iter=precise_iter)
    results['precise'] = {
        'best_params': precise_result.get('best_params', {}),
        'best_score': precise_result.get('best_score', 0),
        'search_time': precise_result.get('search_time', 0),
    }

    # 对比分析
    quick_score = results['quick']['best_score']
    precise_score = results['precise']['best_score']

    improvement = (quick_score - precise_score) / max(abs(quick_score), 1e-8) * 100

    results['comparison'] = {
        'improvement_percent': improvement,
        'quick_wins': quick_score < precise_score,
        'precise_wins': precise_score < quick_score,
        'time_tradeoff': results['precise']['search_time'] / max(results['quick']['search_time'], 1e-8),
    }

    return results

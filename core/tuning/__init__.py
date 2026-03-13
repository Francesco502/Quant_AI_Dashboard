"""
超参数调优模块

提供自动化调参功能：
- 网格搜索 (Grid Search) - 快速模式
- 贝叶斯优化 (Bayesian Optimization) - 精确模式
- 自动调参 (Auto Tuning) - 根据数据量和模型类型自动选择

模块:
    grid_search.py  - 网格搜索实现
    bayesian_opt.py - 贝叶斯优化实现

使用示例:
    from core.tuner import auto_tune, quick_tune, precise_tune

    # 自动模式（推荐）
    best_params = auto_tune("xgboost", price_series)

    # 快速模式（30秒内）
    best_params = quick_tune("xgboost", price_series)

    # 精确模式（5-10分钟）
    best_params = precise_tune("xgboost", price_series)
"""

from core.tuning.grid_search import grid_search, get_quick_grid, get_full_grid
from core.tuning.bayesian_opt import bayesian_search, get_bayesian_space

__all__ = [
    'grid_search',
    'get_quick_grid',
    'get_full_grid',
    'bayesian_search',
    'get_bayesian_space',
]

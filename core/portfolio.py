from typing import Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def _portfolio_statistics(
    weights: np.ndarray, log_returns: pd.DataFrame, risk_free_rate: float = 0.0
) -> Tuple[float, float, float]:
    """
    计算组合的 年化收益、年化波动率 和 夏普比率。

    参数
    ----
    weights : np.ndarray
        资产权重向量，长度等于资产数。
    log_returns : pd.DataFrame
        日对数收益率，列为资产代码。
    risk_free_rate : float
        年化无风险利率，用于夏普比率计算。
    """
    weights = np.array(weights)
    mean_daily = log_returns.mean()
    cov_daily = log_returns.cov()

    # 年化因子：252 个交易日
    exp_return = float(np.dot(weights, mean_daily) * 252)
    exp_vol = float(np.sqrt(np.dot(weights.T, np.dot(cov_daily * 252, weights))))

    if exp_vol == 0:
        sharpe = 0.0
    else:
        sharpe = (exp_return - risk_free_rate) / exp_vol

    return exp_return, exp_vol, sharpe


def _negative_sharpe(
    weights: np.ndarray, log_returns: pd.DataFrame, risk_free_rate: float = 0.0
) -> float:
    _, _, sharpe = _portfolio_statistics(weights, log_returns, risk_free_rate)
    return -sharpe


def optimize_portfolio_markowitz(
    log_returns: pd.DataFrame, risk_free_rate: float = 0.0
) -> Tuple[np.ndarray, float, float, float]:
    """
    使用 Markowitz 均值-方差框架，最大化夏普比率，求解最优资产权重。

    这是量子金融中常见的“组合优化问题”的经典版：在量子场景中，往往会把它转化为 QUBO 形式，
    再用 QAOA / VQE 等算法求解。本函数提供可对照的经典基线。

    参数
    ----
    log_returns : pd.DataFrame
        日对数收益率。
    risk_free_rate : float
        年化无风险利率。

    返回
    ----
    weights : np.ndarray
        最优权重。
    exp_return : float
        最优组合预期年化收益。
    exp_vol : float
        最优组合预期年化波动率。
    sharpe : float
        最优组合夏普比率。
    """
    n_assets = log_returns.shape[1]
    if n_assets == 0:
        raise ValueError("log_returns 中没有任何资产，无法进行优化。")

    init_weights = np.ones(n_assets) / n_assets

    # 约束：权重之和为 1
    constraints = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
    # 边界：每个资产权重在 [0, 1] 之间（不允许做空，可视情况放宽）
    bounds = tuple((0.0, 1.0) for _ in range(n_assets))

    result = minimize(
        _negative_sharpe,
        init_weights,
        args=(log_returns, risk_free_rate),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"disp": False},
    )

    if not result.success:
        raise RuntimeError(f"组合优化失败: {result.message}")

    opt_weights = result.x
    exp_return, exp_vol, sharpe = _portfolio_statistics(
        opt_weights, log_returns, risk_free_rate
    )
    return opt_weights, exp_return, exp_vol, sharpe



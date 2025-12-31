"""风险分析模块"""
import pandas as pd
import numpy as np
from typing import Tuple, Dict
from scipy import stats


def calculate_var(returns: pd.Series, confidence_level: float = 0.05) -> float:
    """
    计算风险价值（VaR）
    
    参数:
        returns: 收益率序列
        confidence_level: 置信水平（默认5%，即95%置信度）
    
    返回:
        VaR值（负数表示损失）
    """
    return returns.quantile(confidence_level)


def calculate_cvar(returns: pd.Series, confidence_level: float = 0.05) -> float:
    """
    计算条件风险价值（CVaR/Expected Shortfall）
    
    参数:
        returns: 收益率序列
        confidence_level: 置信水平
    
    返回:
        CVaR值
    """
    var = calculate_var(returns, confidence_level)
    return returns[returns <= var].mean()


def calculate_max_drawdown(price_data: pd.Series) -> Tuple[float, pd.Series]:
    """
    计算最大回撤
    
    返回:
        (最大回撤值, 回撤序列)
    """
    cumulative = (1 + price_data.pct_change()).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    
    max_drawdown = drawdown.min()
    return max_drawdown, drawdown


def calculate_downside_deviation(returns: pd.Series, target_return: float = 0.0) -> float:
    """计算下行波动率（只考虑低于目标收益的部分）"""
    downside_returns = returns[returns < target_return]
    if len(downside_returns) == 0:
        return 0.0
    return np.sqrt(np.mean(downside_returns ** 2)) * np.sqrt(252)  # 年化


def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """计算索提诺比率（只考虑下行风险）"""
    excess_returns = returns.mean() * 252 - risk_free_rate
    downside_std = calculate_downside_deviation(returns)
    if downside_std == 0:
        return 0.0
    return excess_returns / downside_std


def calculate_correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """计算相关性矩阵"""
    return returns.corr()


def calculate_risk_contribution(weights: np.ndarray, returns: pd.DataFrame) -> pd.Series:
    """
    计算每个资产对组合风险的贡献度
    
    返回:
        每个资产的风险贡献度（百分比）
    """
    weights = np.array(weights)
    cov_matrix = returns.cov() * 252  # 年化协方差矩阵
    portfolio_variance = np.dot(weights, np.dot(cov_matrix, weights))
    portfolio_vol = np.sqrt(portfolio_variance)
    
    # 每个资产的边际风险贡献
    marginal_contrib = np.dot(cov_matrix, weights) / portfolio_vol
    
    # 风险贡献度
    risk_contrib = weights * marginal_contrib
    risk_contrib_pct = risk_contrib / portfolio_vol * 100
    
    return pd.Series(risk_contrib_pct, index=returns.columns)


def calculate_portfolio_risk_metrics(
    returns: pd.DataFrame, 
    weights: np.ndarray,
    risk_free_rate: float = 0.02
) -> Dict[str, float]:
    """
    计算组合的综合风险指标
    
    返回:
        包含各种风险指标的字典
    """
    portfolio_returns = (returns * weights).sum(axis=1)
    
    # 年化收益和波动率
    annual_return = portfolio_returns.mean() * 252
    annual_vol = portfolio_returns.std() * np.sqrt(252)
    
    # 夏普比率
    sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0
    
    # 索提诺比率
    sortino = calculate_sortino_ratio(portfolio_returns, risk_free_rate)
    
    # VaR和CVaR
    var_95 = calculate_var(portfolio_returns, 0.05)
    cvar_95 = calculate_cvar(portfolio_returns, 0.05)
    
    # 最大回撤
    price_series = (1 + portfolio_returns).cumprod()
    max_dd, _ = calculate_max_drawdown(price_series)
    
    return {
        'annual_return': annual_return,
        'annual_volatility': annual_vol,
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'var_95': var_95,
        'cvar_95': cvar_95,
        'max_drawdown': max_dd
    }


def find_highly_correlated_pairs(
    corr_matrix: pd.DataFrame, 
    threshold: float = 0.7
) -> pd.DataFrame:
    """
    找出高度相关的资产对
    
    参数:
        corr_matrix: 相关性矩阵（DataFrame）
        threshold: 相关系数阈值（绝对值），默认0.7
    
    返回:
        包含资产对和相关系数的DataFrame，列名为 ['资产1', '资产2', '相关系数']
    """
    pairs = []
    
    # 遍历上三角矩阵（避免重复和自身相关）
    for i in range(len(corr_matrix)):
        for j in range(i + 1, len(corr_matrix)):
            corr_value = corr_matrix.iloc[i, j]
            # 检查绝对值是否超过阈值
            if abs(corr_value) >= threshold:
                asset1 = corr_matrix.index[i]
                asset2 = corr_matrix.columns[j]
                pairs.append({
                    '资产1': asset1,
                    '资产2': asset2,
                    '相关系数': corr_value
                })
    
    if not pairs:
        return pd.DataFrame(columns=['资产1', '资产2', '相关系数'])
    
    result_df = pd.DataFrame(pairs)
    # 按相关系数绝对值降序排列
    result_df = result_df.reindex(
        result_df['相关系数'].abs().sort_values(ascending=False).index
    ).reset_index(drop=True)
    
    return result_df

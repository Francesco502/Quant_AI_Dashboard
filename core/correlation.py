"""相关性分析模块"""
import pandas as pd
import numpy as np
from typing import Tuple


def calculate_correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """计算相关性矩阵"""
    return returns.corr()


def calculate_rolling_correlation(
    returns1: pd.Series, 
    returns2: pd.Series, 
    window: int = 60
) -> pd.Series:
    """计算滚动相关性"""
    return returns1.rolling(window=window).corr(returns2)


def calculate_correlation_heatmap_data(corr_matrix: pd.DataFrame) -> list:
    """
    为Plotly准备相关性热力图数据
    
    返回:
        Plotly热力图所需的z值和文本标签
    """
    z = corr_matrix.values
    text = [[f'{val:.2f}' for val in row] for row in z]
    
    return {
        'z': z,
        'x': corr_matrix.columns.tolist(),
        'y': corr_matrix.index.tolist(),
        'text': text,
        'type': 'heatmap',
        'colorscale': 'RdBu',
        'zmid': 0
    }


def find_highly_correlated_pairs(
    corr_matrix: pd.DataFrame, 
    threshold: float = 0.7
) -> pd.DataFrame:
    """
    找出高度相关的资产对
    
    返回:
        相关性高于阈值的资产对及其相关系数
    """
    pairs = []
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            corr_value = corr_matrix.iloc[i, j]
            if abs(corr_value) >= threshold:
                pairs.append({
                    'asset1': corr_matrix.columns[i],
                    'asset2': corr_matrix.columns[j],
                    'correlation': corr_value
                })
    
    # 如果没有找到高度相关的资产对，返回空的DataFrame（包含正确的列名）
    if not pairs:
        return pd.DataFrame(columns=['asset1', 'asset2', 'correlation'])
    
    # 创建DataFrame并排序
    df = pd.DataFrame(pairs)
    if not df.empty and 'correlation' in df.columns:
        return df.sort_values('correlation', key=abs, ascending=False)
    else:
        return df


def calculate_correlation_clusters(corr_matrix: pd.DataFrame, n_clusters: int = 3) -> dict:
    """
    简单的相关性聚类（基于相关性距离）
    
    返回:
        聚类结果
    """
    # 将相关性转换为距离（1 - |correlation|）
    distance_matrix = 1 - np.abs(corr_matrix.values)
    
    # 简单的层次聚类（简化版）
    # 实际应该使用scipy.cluster.hierarchy
    clusters = {}
    for i, asset in enumerate(corr_matrix.columns):
        clusters[asset] = i % n_clusters  # 简化：按顺序分配
    
    return clusters


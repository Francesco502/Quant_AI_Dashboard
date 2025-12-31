"""
缓存工具模块
提供带缓存的计算函数，减少重复计算
"""
import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, Tuple
from core.technical_indicators import calculate_all_indicators, get_trading_signals


@st.cache_data(ttl=300, show_spinner="计算收益率...")
def calculate_returns_cached(data: pd.DataFrame) -> pd.DataFrame:
    """
    计算对数收益率（带缓存）
    
    Args:
        data: 价格数据DataFrame，index为日期，columns为资产代码
        
    Returns:
        对数收益率DataFrame
    """
    if data.empty:
        return pd.DataFrame()
    return np.log(data / data.shift(1)).dropna()


@st.cache_data(ttl=300, show_spinner="计算技术指标...")
def calculate_indicators_cached(price_series: pd.Series) -> Dict:
    """
    计算技术指标（带缓存）
    
    Args:
        price_series: 价格序列
        
    Returns:
        技术指标字典
    """
    if price_series.empty:
        return {}
    return calculate_all_indicators(price_series)


@st.cache_data(ttl=300, show_spinner="生成交易信号...")
def get_trading_signals_cached(price_series: pd.Series, indicators: Dict = None) -> Dict:
    """
    生成交易信号（带缓存）
    
    Args:
        price_series: 价格序列
        indicators: 技术指标字典（如果为None则自动计算）
        
    Returns:
        交易信号字典
    """
    if price_series.empty:
        return {}
    
    if indicators is None:
        indicators = calculate_all_indicators(price_series)
    
    return get_trading_signals(price_series, indicators)


@st.cache_data(ttl=60, show_spinner="计算相关性矩阵...")
def calculate_correlation_matrix_cached(returns: pd.DataFrame) -> pd.DataFrame:
    """
    计算相关性矩阵（带缓存）
    
    Args:
        returns: 收益率DataFrame
        
    Returns:
        相关性矩阵DataFrame
    """
    if returns.empty:
        return pd.DataFrame()
    return returns.corr()


@st.cache_data(ttl=60, show_spinner="计算协方差矩阵...")
def calculate_covariance_matrix_cached(returns: pd.DataFrame) -> pd.DataFrame:
    """
    计算协方差矩阵（带缓存）
    
    Args:
        returns: 收益率DataFrame
        
    Returns:
        协方差矩阵DataFrame
    """
    if returns.empty:
        return pd.DataFrame()
    return returns.cov()


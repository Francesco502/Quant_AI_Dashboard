"""技术指标计算模块"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple


def calculate_sma(data: pd.Series, window: int) -> pd.Series:
    """计算简单移动平均（SMA）"""
    return data.rolling(window=window).mean()


def calculate_ema(data: pd.Series, window: int) -> pd.Series:
    """计算指数移动平均（EMA）"""
    return data.ewm(span=window, adjust=False).mean()


def calculate_rsi(data: pd.Series, window: int = 14) -> pd.Series:
    """计算相对强弱指标（RSI）"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """计算MACD指标"""
    ema_fast = calculate_ema(data, fast)
    ema_slow = calculate_ema(data, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def calculate_bollinger_bands(data: pd.Series, window: int = 20, num_std: float = 2) -> Dict[str, pd.Series]:
    """计算布林带"""
    sma = calculate_sma(data, window)
    std = data.rolling(window=window).std()
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)
    
    return {
        'middle': sma,
        'upper': upper_band,
        'lower': lower_band
    }


def calculate_all_indicators(price_data: pd.Series) -> pd.DataFrame:
    """计算所有技术指标"""
    indicators = pd.DataFrame(index=price_data.index)
    indicators['price'] = price_data
    
    # 移动平均
    indicators['sma_20'] = calculate_sma(price_data, 20)
    indicators['sma_50'] = calculate_sma(price_data, 50)
    indicators['ema_12'] = calculate_ema(price_data, 12)
    indicators['ema_26'] = calculate_ema(price_data, 26)
    
    # RSI
    indicators['rsi'] = calculate_rsi(price_data)
    
    # MACD
    macd_data = calculate_macd(price_data)
    indicators['macd'] = macd_data['macd']
    indicators['macd_signal'] = macd_data['signal']
    indicators['macd_histogram'] = macd_data['histogram']
    
    # 布林带
    bb_data = calculate_bollinger_bands(price_data)
    indicators['bb_upper'] = bb_data['upper']
    indicators['bb_middle'] = bb_data['middle']
    indicators['bb_lower'] = bb_data['lower']
    
    return indicators


def get_trading_signals(price_data: pd.Series, indicators: pd.DataFrame = None) -> pd.DataFrame:
    """生成交易信号"""
    if indicators is None:
        indicators = calculate_all_indicators(price_data)
    
    signals = pd.DataFrame(index=price_data.index)
    signals['price'] = price_data
    
    # 移动平均交叉信号
    signals['ma_cross'] = 0
    signals.loc[indicators['sma_20'] > indicators['sma_50'], 'ma_cross'] = 1  # 金叉
    signals.loc[indicators['sma_20'] < indicators['sma_50'], 'ma_cross'] = -1  # 死叉
    
    # RSI信号
    signals['rsi_signal'] = 0
    signals.loc[indicators['rsi'] < 30, 'rsi_signal'] = 1  # 超卖，买入
    signals.loc[indicators['rsi'] > 70, 'rsi_signal'] = -1  # 超买，卖出
    
    # MACD信号
    signals['macd_signal'] = 0
    signals.loc[indicators['macd'] > indicators['macd_signal'], 'macd_signal'] = 1
    signals.loc[indicators['macd'] < indicators['macd_signal'], 'macd_signal'] = -1
    
    # 综合信号（简单投票机制）
    signals['combined_signal'] = (
        signals['ma_cross'] + 
        signals['rsi_signal'] + 
        signals['macd_signal']
    ) / 3
    
    return signals


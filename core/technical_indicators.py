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


def calculate_rsv(df: pd.DataFrame, n: int = 9) -> pd.Series:
    """
    计算 RSV (Raw Stochastic Value)
    RSV(N) = 100 * (C - LLV(L,N)) / (HHV(C,N) - LLV(L,N))
    """
    if df.empty:
        return pd.Series(dtype=float)
        
    low_n = df["low"].rolling(window=n, min_periods=1).min()
    high_n = df["high"].rolling(window=n, min_periods=1).max()
    rsv = (df["close"] - low_n) / (high_n - low_n + 1e-9) * 100.0
    return rsv


def calculate_kdj(df: pd.DataFrame, n: int = 9) -> pd.DataFrame:
    """计算KDJ指标"""
    if df.empty:
        return df.assign(K=np.nan, D=np.nan, J=np.nan)

    rsv = calculate_rsv(df, n)

    K = np.zeros_like(rsv, dtype=float)
    D = np.zeros_like(rsv, dtype=float)
    for i in range(len(df)):
        if i == 0:
            K[i] = D[i] = 50.0
        else:
            K[i] = 2 / 3 * K[i - 1] + 1 / 3 * rsv.iloc[i]
            D[i] = 2 / 3 * D[i - 1] + 1 / 3 * K[i]
    J = 3 * K - 2 * D
    return df.assign(K=K, D=D, J=J)


def calculate_bbi(df: pd.DataFrame) -> pd.Series:
    """计算BBI指标"""
    ma3 = df["close"].rolling(3).mean()
    ma6 = df["close"].rolling(6).mean()
    ma12 = df["close"].rolling(12).mean()
    ma24 = df["close"].rolling(24).mean()
    return (ma3 + ma6 + ma12 + ma24) / 4


def calculate_macd_dif(df: pd.DataFrame, fast: int = 12, slow: int = 26) -> pd.Series:
    """
    计算 MACD 指标中的 DIF (EMA fast - EMA slow)
    """
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    return ema_fast - ema_slow


def analyze_bbi_trend(
    bbi: pd.Series,
    *,
    min_window: int,
    max_window: int | None = None,
    q_threshold: float = 0.0,
) -> bool:
    """
    判断 BBI 是否“整体上升”。
    
    令最新交易日为 T，在区间 [T-w+1, T]（w 自适应，w ≥ min_window 且 ≤ max_window）
    内，先将 BBI 归一化：BBI_norm(t) = BBI(t) / BBI(T-w+1)。

    再计算一阶差分 Δ(t) = BBI_norm(t) - BBI_norm(t-1)。  
    若 Δ(t) 的前 q_threshold 分位数 ≥ 0，则认为该窗口通过；只要存在
    **最长** 满足条件的窗口即可返回 True。q_threshold=0 时退化为
    “全程单调不降”。
    """
    if not 0.0 <= q_threshold <= 1.0:
        raise ValueError("q_threshold 必须位于 [0, 1] 区间内")

    bbi = bbi.dropna()
    if len(bbi) < min_window:
        return False

    longest = min(len(bbi), max_window or len(bbi))

    # 自最长窗口向下搜索，找到任一满足条件的区间即通过
    for w in range(longest, min_window - 1, -1):
        seg = bbi.iloc[-w:]                # 区间 [T-w+1, T]
        norm = seg / seg.iloc[0]           # 归一化
        diffs = np.diff(norm.values)       # 一阶差分
        if np.quantile(diffs, q_threshold) >= 0:
            return True
    return False



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


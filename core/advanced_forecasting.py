"""
高级价格预测模块 - 实际部署版本
支持多种预测模型：Prophet、XGBoost、LSTM、集成模型

作者: Francesco
说明: 替换原有的 simple_price_forecast，提供生产级预测能力
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import os
import json
import warnings

try:
    import joblib  # type: ignore[import]
    JOBLIB_AVAILABLE = True
except ImportError:  # pragma: no cover - 运行时降级
    JOBLIB_AVAILABLE = False
warnings.filterwarnings('ignore')

# ==================== 模型导入（按需加载） ====================

# Prophet - 快速、稳定的时序预测
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

from typing import Any
from core.data_service import load_price_data

def prophet_forecast(
    df: pd.DataFrame, 
    horizon: int = 30,
    changepoint_prior_scale: float = 0.05
) -> pd.DataFrame:
    """
    使用 Prophet 进行时间序列预测
    
    Args:
        df: 必须包含 'ds' (datetime) 和 'y' (float) 列
        horizon: 预测天数
        
    Returns:
        forecast DataFrame (ds, yhat, yhat_lower, yhat_upper)
    """
    if not PROPHET_AVAILABLE:
        raise ImportError("Prophet未安装。请运行: pip install prophet")
        
    # 简单的模型配置
    m = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=changepoint_prior_scale
    )
    
    m.fit(df)
    
    future = m.make_future_dataframe(periods=horizon)
    forecast = m.predict(future)
    
    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(horizon)

def run_forecast(
    ticker: str, 
    horizon: int = 30,
    model_type: str = "prophet"
) -> Dict[str, Any]:
    """
    运行预测的主入口
    """
    # 1. 获取数据 (2年历史)
    price_df = load_price_data([ticker], days=365*2)
    if price_df.empty or ticker not in price_df.columns:
        raise ValueError(f"无法获取 {ticker} 的历史数据")
        
    # 2. 准备数据
    # Prophet 需要 ds, y 格式
    # 注意：price_df index 是 datetime
    df = price_df[[ticker]].reset_index()
    # 假设 load_price_data 返回的 index name 是 'date' 或 'trade_date'，或者是 None
    # 强行重命名
    df.columns = ['ds', 'y']
    
    # 3. 运行模型
    if model_type == "prophet":
        forecast = prophet_forecast(df, horizon)
        
        # 格式化输出
        predictions = []
        for _, row in forecast.iterrows():
            predictions.append({
                "date": row['ds'].strftime("%Y-%m-%d"),
                "price": round(row['yhat'], 2),
                "lower": round(row['yhat_lower'], 2),
                "upper": round(row['yhat_upper'], 2)
            })
            
        return {
            "ticker": ticker,
            "model": "Prophet",
            "horizon": horizon,
            "predictions": predictions
        }
    else:
        # TODO: Implement LSTM / XGBoost
        raise NotImplementedError(f"模型 {model_type} 暂未实现")

# XGBoost/LightGBM - 机器学习方法
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

# PyTorch - 深度学习模型
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# sklearn 用于特征预处理和模型
try:
    from sklearn.preprocessing import MinMaxScaler, StandardScaler
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.ensemble import RandomForestRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    RandomForestRegressor = None

# statsmodels 用于 ARIMA
try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    ARIMA = None
    SARIMAX = None


# ==================== 特征工程模块 ====================

class FeatureEngineer:
    """
    金融时序特征工程
    生成用于机器学习/深度学习模型的特征
    """
    
    @staticmethod
    def create_price_features(price_series: pd.Series, 
                               lookback_windows: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
        """
        创建价格相关特征
        
        参数:
            price_series: 价格序列
            lookback_windows: 回看窗口列表
        
        返回:
            特征DataFrame
        """
        df = pd.DataFrame(index=price_series.index)
        df['price'] = price_series
        
        # 收益率特征
        df['return_1d'] = price_series.pct_change(1)
        df['return_5d'] = price_series.pct_change(5)
        df['return_10d'] = price_series.pct_change(10)
        df['return_20d'] = price_series.pct_change(20)
        
        # 对数收益率
        df['log_return'] = np.log(price_series / price_series.shift(1))
        
        for window in lookback_windows:
            # 移动平均
            df[f'sma_{window}'] = price_series.rolling(window=window).mean()
            df[f'sma_ratio_{window}'] = price_series / df[f'sma_{window}']
            
            # 波动率
            df[f'volatility_{window}'] = df['log_return'].rolling(window=window).std() * np.sqrt(252)
            
            # 最高最低
            df[f'high_{window}'] = price_series.rolling(window=window).max()
            df[f'low_{window}'] = price_series.rolling(window=window).min()
            df[f'range_ratio_{window}'] = (df[f'high_{window}'] - df[f'low_{window}']) / price_series
            
            # 动量
            df[f'momentum_{window}'] = price_series / price_series.shift(window) - 1
        
        # RSI
        delta = price_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema_12 = price_series.ewm(span=12, adjust=False).mean()
        ema_26 = price_series.ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # 布林带位置
        bb_window = 20
        bb_std = 2
        df['bb_middle'] = price_series.rolling(window=bb_window).mean()
        bb_std_val = price_series.rolling(window=bb_window).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std_val * bb_std)
        df['bb_lower'] = df['bb_middle'] - (bb_std_val * bb_std)
        df['bb_position'] = (price_series - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 时间特征
        df['day_of_week'] = price_series.index.dayofweek
        df['month'] = price_series.index.month
        df['quarter'] = price_series.index.quarter
        
        return df
    
    @staticmethod
    def create_lag_features(df: pd.DataFrame, target_col: str, lags: List[int]) -> pd.DataFrame:
        """创建滞后特征"""
        for lag in lags:
            df[f'{target_col}_lag_{lag}'] = df[target_col].shift(lag)
        return df
    
    @staticmethod
    def create_target(price_series: pd.Series, horizon: int = 1) -> pd.Series:
        """创建预测目标（未来收益率）"""
        return price_series.pct_change(horizon).shift(-horizon)

    # ====== 扩展特征（第二阶段：特征工程优化） ======
    @staticmethod
    def add_enhanced_features(df: pd.DataFrame, price_series: pd.Series) -> pd.DataFrame:
        """
        增强版特征工程：
        - ATR 风格波动率（基于收盘价的简化版本）
        - 实现波动率 realized_vol_20

        说明：
        - 这里不依赖额外的高低价/成交量数据，保证对现有数据结构兼容；
        - 后续可在此基础上继续接入市场宽度、情绪、宏观等特征。
        """
        # 简化版 ATR：使用相邻收盘价变动的绝对值作为 true range 近似
        tr = price_series.diff().abs()
        df["atr_14"] = tr.rolling(window=14).mean()

        # 实现波动率：20 日年化波动率
        df["realized_vol_20"] = (
            price_series.pct_change().rolling(window=20).std() * np.sqrt(252)
        )

        return df


# ==================== Prophet 预测模型 ====================

class ProphetForecaster:
    """
    使用 Facebook Prophet 进行价格预测
    优点：自动处理节假日、季节性，开箱即用
    """
    
    def __init__(self, 
                 changepoint_prior_scale: float = 0.05,
                 seasonality_mode: str = 'multiplicative'):
        """
        初始化 Prophet 预测器
        
        参数:
            changepoint_prior_scale: 趋势变化点灵活度（越大越灵活）
            seasonality_mode: 季节性模式 ('additive' 或 'multiplicative')
        """
        if not PROPHET_AVAILABLE:
            raise ImportError("请安装 prophet: pip install prophet")
        
        self.changepoint_prior_scale = changepoint_prior_scale
        self.seasonality_mode = seasonality_mode
        self.model = None
    
    def fit(self, price_series: pd.Series):
        """训练 Prophet 模型"""
        # Prophet 需要 'ds' 和 'y' 两列
        df = pd.DataFrame({
            'ds': price_series.index,
            'y': price_series.values
        })
        
        self.model = Prophet(
            changepoint_prior_scale=self.changepoint_prior_scale,
            seasonality_mode=self.seasonality_mode,
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True
        )
        self.model.fit(df)
        return self
    
    def predict(self, horizon: int = 5) -> pd.DataFrame:
        """预测未来价格"""
        if self.model is None:
            raise ValueError("请先调用 fit() 方法训练模型")
        
        future = self.model.make_future_dataframe(periods=horizon, freq='B')  # 工作日
        forecast = self.model.predict(future)
        
        # 返回预测结果
        result = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(horizon)
        result = result.set_index('ds')
        result.columns = ['prediction', 'lower_bound', 'upper_bound']
        
        return result


# ==================== XGBoost 预测模型 ====================

class XGBoostForecaster:
    """
    使用 XGBoost 进行价格预测
    优点：特征工程驱动，可解释性强，训练快速
    """
    
    def __init__(self, 
                 n_estimators: int = 100,
                 max_depth: int = 6,
                 learning_rate: float = 0.1,
                 lookback: int = 60,
                 use_enhanced_features: bool = False):
        """
        初始化 XGBoost 预测器
        
        参数:
            n_estimators: 树的数量
            max_depth: 树的最大深度
            learning_rate: 学习率
            lookback: 特征窗口大小
            use_enhanced_features: 是否启用增强特征（ATR / 实现波动率等）
        """
        if not XGBOOST_AVAILABLE:
            raise ImportError("请安装 xgboost: pip install xgboost")
        
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.lookback = lookback
        self.use_enhanced_features = use_enhanced_features
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.feature_columns = None
        self.last_price = None
    
    def _prepare_features(self, price_series: pd.Series) -> pd.DataFrame:
        """准备特征"""
        # 动态调整特征窗口
        max_len = len(price_series)
        windows = [w for w in [5, 10, 20, 60] if w < max_len]
        if not windows:
            windows = [min(5, max_len // 2)] if max_len > 2 else [1]
            
        df = self.feature_engineer.create_price_features(price_series, lookback_windows=windows)
        
        # 动态调整 lag
        max_lag = min(10, max_len // 4)
        if max_lag > 0:
            lags = [l for l in [1, 2, 3, 5, 10] if l <= max_lag]
            df = self.feature_engineer.create_lag_features(df, 'return_1d', lags=lags)
            
        # 可选增强特征（波动率等）
        if self.use_enhanced_features and max_len > 20:
            df = self.feature_engineer.add_enhanced_features(df, price_series)
        return df
    
    def fit(self, price_series: pd.Series, target_horizon: int = 1):
        """训练 XGBoost 模型"""
        self.last_price = price_series.iloc[-1]
        
        # 准备特征
        df = self._prepare_features(price_series)
        
        # 创建目标变量（未来收益率）
        df['target'] = self.feature_engineer.create_target(price_series, target_horizon)
        
        # 删除缺失值
        df = df.dropna()
        
        # 分离特征和目标
        feature_cols = [c for c in df.columns if c not in ['price', 'target']]
        self.feature_columns = feature_cols
        
        X = df[feature_cols].values
        y = df['target'].values
        
        # 标准化
        if self.scaler:
            X = self.scaler.fit_transform(X)
        
        # 训练模型
        self.model = xgb.XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            objective='reg:squarederror',
            random_state=42
        )
        self.model.fit(X, y)
        
        # 保存最后的特征用于预测
        self._last_features = df[feature_cols].iloc[-1:].values
        if self.scaler:
            self._last_features = self.scaler.transform(self._last_features)
        
        return self
    
    def predict(self, horizon: int = 5) -> pd.DataFrame:
        """预测未来收益率并转换为价格"""
        if self.model is None:
            raise ValueError("请先调用 fit() 方法训练模型")
        
        predictions = []
        current_price = self.last_price
        current_features = self._last_features.copy()
        
        # 生成未来日期
        last_date = pd.Timestamp.now()
        future_dates = pd.bdate_range(start=last_date + timedelta(days=1), periods=horizon)
        
        for i in range(horizon):
            # 预测收益率
            pred_return = self.model.predict(current_features)[0]
            
            # 转换为价格
            pred_price = current_price * (1 + pred_return)
            predictions.append(pred_price)
            
            # 更新当前价格（用于下一步预测）
            current_price = pred_price
        
        result = pd.DataFrame({
            'prediction': predictions
        }, index=future_dates)
        
        return result
    
    def get_feature_importance(self) -> pd.Series:
        """获取特征重要性"""
        if self.model is None or self.feature_columns is None:
            raise ValueError("请先调用 fit() 方法训练模型")
        
        importance = pd.Series(
            self.model.feature_importances_,
            index=self.feature_columns
        ).sort_values(ascending=False)
        
        return importance


# ==================== LSTM 预测模型 ====================

class LSTMForecaster:
    """
    使用 LSTM 进行价格预测
    优点：序列记忆能力强，适合捕捉时序模式
    支持 early stopping 早停策略
    """

    def __init__(self,
                 hidden_size: int = 64,
                 num_layers: int = 2,
                 dropout: float = 0.2,
                 sequence_length: int = 30,
                 learning_rate: float = 0.001,
                 epochs: int = 100,
                 batch_size: int = 32,
                 early_stopping_rounds: int = 10,
                 early_stopping_delta: float = 1e-4):
        """
        初始化 LSTM 预测器
        
        参数:
            hidden_size: 隐藏层大小
            num_layers: LSTM 层数
            dropout: Dropout 比例
            sequence_length: 输入序列长度
            learning_rate: 学习率
            epochs: 训练轮数
            batch_size: 批次大小
            early_stopping_rounds: 早停容忍轮数（patience）
            early_stopping_delta: 最小时均损失改善阈值
        """
        if not TORCH_AVAILABLE:
            raise ImportError("请安装 PyTorch: pip install torch")
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.sequence_length = sequence_length
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.early_stopping_rounds = early_stopping_rounds
        self.early_stopping_delta = early_stopping_delta

        self.model = None
        self.scaler = MinMaxScaler() if SKLEARN_AVAILABLE else None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def _build_model(self, input_size: int):
        """构建 LSTM 模型"""

        class LSTMModel(nn.Module):
            def __init__(self, input_size, hidden_size, num_layers, dropout):
                super(LSTMModel, self).__init__()
                self.lstm = nn.LSTM(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    dropout=dropout if num_layers > 1 else 0,
                    batch_first=True
                )
                self.fc = nn.Linear(hidden_size, 1)

            def forward(self, x):
                out, _ = self.lstm(x)
                out = out[:, -1, :]
                out = self.fc(out)
                return out

        return LSTMModel(input_size, self.hidden_size, self.num_layers, self.dropout).to(self.device)

    # 训练方法中插入 Early Stopping 逻辑
    def fit(self, X: np.ndarray, y: np.ndarray, val_data: Optional[Tuple[np.ndarray, np.ndarray]] = None):
        """
        训练 LSTM 模型
        支持早停策略
        参数:
            X: 输入特征, shape=(n_samples, seq_len, n_feats)
            y: 标签, shape=(n_samples, 1)
            val_data: 验证集 (X_val, y_val)，用于 early stopping
        """
        # 预处理
        if self.scaler:
            n = X.shape[0]
            orig_shape = X.shape
            X = X.reshape(-1, X.shape[-1])
            X = self.scaler.fit_transform(X)
            X = X.reshape(orig_shape)
            if val_data is not None:
                X_val, y_val = val_data
                orig_shape_val = X_val.shape
                X_val = X_val.reshape(-1, X_val.shape[-1])
                X_val = self.scaler.transform(X_val)
                X_val = X_val.reshape(orig_shape_val)
                val_data = (X_val, y_val)

        input_size = X.shape[2]
        model = self._build_model(input_size)
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate)

        # 转换 tensor
        X_tensor = torch.tensor(X, dtype=torch.float32).to(self.device)
        y_tensor = torch.tensor(y, dtype=torch.float32).to(self.device)
        if val_data is not None:
            X_val_tensor = torch.tensor(val_data[0], dtype=torch.float32).to(self.device)
            y_val_tensor = torch.tensor(val_data[1], dtype=torch.float32).to(self.device)

        dataset = torch.utils.data.TensorDataset(X_tensor, y_tensor)
        loader = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        best_loss = float("inf")
        best_state = None
        patience_cnt = 0

        for epoch in range(self.epochs):
            model.train()
            epoch_loss = 0.0
            for batch_X, batch_y in loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item() * batch_X.size(0)
            epoch_loss /= len(loader.dataset)

            val_loss = None
            if val_data is not None:
                model.eval()
                with torch.no_grad():
                    val_outputs = model(X_val_tensor)
                    val_loss = criterion(val_outputs, y_val_tensor).item()

                monitor_loss = val_loss
            else:
                monitor_loss = epoch_loss

            if monitor_loss < best_loss - self.early_stopping_delta:
                best_loss = monitor_loss
                best_state = model.state_dict()
                patience_cnt = 0
            else:
                patience_cnt += 1

            # 可选: print(f"Epoch {epoch+1:03d}: train_loss={epoch_loss:.5f} val_loss={val_loss:.5f}" if val_loss else f"Epoch {epoch+1:03d}: train_loss={epoch_loss:.5f}")

            if patience_cnt >= self.early_stopping_rounds:
                # print("Early stopping triggered")
                break

        # 恢复最佳参数
        if best_state is not None:
            model.load_state_dict(best_state)

        self.model = model
        return self
    """
    使用 LSTM 进行价格预测
    优点：序列记忆能力强，适合捕捉时序模式
    """
    
    def __init__(self,
                 hidden_size: int = 64,
                 num_layers: int = 2,
                 dropout: float = 0.2,
                 sequence_length: int = 30,
                 learning_rate: float = 0.001,
                 epochs: int = 100,
                 batch_size: int = 32):
        """
        初始化 LSTM 预测器
        
        参数:
            hidden_size: 隐藏层大小
            num_layers: LSTM 层数
            dropout: Dropout 比例
            sequence_length: 输入序列长度
            learning_rate: 学习率
            epochs: 训练轮数
            batch_size: 批次大小
        """
        if not TORCH_AVAILABLE:
            raise ImportError("请安装 PyTorch: pip install torch")
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.sequence_length = sequence_length
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        
        self.model = None
        self.scaler = MinMaxScaler() if SKLEARN_AVAILABLE else None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    def _build_model(self, input_size: int):
        """构建 LSTM 模型"""
        
        class LSTMModel(nn.Module):
            def __init__(self, input_size, hidden_size, num_layers, dropout):
                super(LSTMModel, self).__init__()
                self.lstm = nn.LSTM(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    batch_first=True,
                    dropout=dropout if num_layers > 1 else 0
                )
                self.fc = nn.Linear(hidden_size, 1)
            
            def forward(self, x):
                lstm_out, _ = self.lstm(x)
                out = self.fc(lstm_out[:, -1, :])
                return out
        
        return LSTMModel(input_size, self.hidden_size, self.num_layers, self.dropout)
    
    def _create_sequences(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """创建序列数据"""
        X, y = [], []
        for i in range(len(data) - self.sequence_length):
            X.append(data[i:(i + self.sequence_length)])
            y.append(data[i + self.sequence_length])
        return np.array(X), np.array(y)
    
    def fit(self, price_series: pd.Series):
        """训练 LSTM 模型"""
        # 准备数据
        self.last_prices = price_series.tail(self.sequence_length).values
        
        prices = price_series.values.reshape(-1, 1)
        
        # 标准化
        if self.scaler:
            prices_scaled = self.scaler.fit_transform(prices)
        else:
            prices_scaled = prices
        
        # 创建序列
        X, y = self._create_sequences(prices_scaled)
        
        # 转换为 PyTorch 张量
        X = torch.FloatTensor(X).to(self.device)
        y = torch.FloatTensor(y).to(self.device)
        
        # 构建模型
        self.model = self._build_model(input_size=1).to(self.device)
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        
        # 训练
        self.model.train()
        for epoch in range(self.epochs):
            optimizer.zero_grad()
            outputs = self.model(X)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 20 == 0:
                print(f'Epoch [{epoch+1}/{self.epochs}], Loss: {loss.item():.6f}')
        
        return self
    
    def predict(self, horizon: int = 5) -> pd.DataFrame:
        """预测未来价格"""
        if self.model is None:
            raise ValueError("请先调用 fit() 方法训练模型")
        
        self.model.eval()
        predictions = []
        
        # 准备初始序列
        current_seq = self.last_prices.reshape(-1, 1)
        if self.scaler:
            current_seq = self.scaler.transform(current_seq)
        
        with torch.no_grad():
            for _ in range(horizon):
                # 转换为张量
                seq_tensor = torch.FloatTensor(current_seq).unsqueeze(0).to(self.device)
                
                # 预测
                pred = self.model(seq_tensor).cpu().numpy()[0, 0]
                
                # 反标准化
                if self.scaler:
                    pred_price = self.scaler.inverse_transform([[pred]])[0, 0]
                else:
                    pred_price = pred
                
                predictions.append(pred_price)
                
                # 更新序列
                current_seq = np.roll(current_seq, -1, axis=0)
                current_seq[-1] = pred
        
        # 生成未来日期
        last_date = pd.Timestamp.now()
        future_dates = pd.bdate_range(start=last_date + timedelta(days=1), periods=horizon)
        
        result = pd.DataFrame({
            'prediction': predictions
        }, index=future_dates)
        
        return result


# ==================== LightGBM 预测模型 ====================

class LightGBMForecaster:
    """
    使用 LightGBM 进行价格预测
    优点：训练速度快，内存占用小，准确率高，适合大规模数据
    """
    
    def __init__(self, 
                 n_estimators: int = 100,
                 max_depth: int = 6,
                 learning_rate: float = 0.1,
                 lookback: int = 60,
                 use_enhanced_features: bool = False):
        """
        初始化 LightGBM 预测器
        
        参数:
            n_estimators: 树的数量
            max_depth: 树的最大深度
            learning_rate: 学习率
            lookback: 特征窗口大小
            use_enhanced_features: 是否启用增强特征
        """
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("请安装 lightgbm: pip install lightgbm")
        
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.lookback = lookback
        self.use_enhanced_features = use_enhanced_features
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.feature_columns = None
        self.last_price = None
    
    def _prepare_features(self, price_series: pd.Series) -> pd.DataFrame:
        """准备特征"""
        # 动态调整特征窗口
        max_len = len(price_series)
        windows = [w for w in [5, 10, 20, 60] if w < max_len]
        if not windows:
            windows = [min(5, max_len // 2)] if max_len > 2 else [1]
            
        df = self.feature_engineer.create_price_features(price_series, lookback_windows=windows)
        
        # 动态调整 lag
        max_lag = min(10, max_len // 4)
        if max_lag > 0:
            lags = [l for l in [1, 2, 3, 5, 10] if l <= max_lag]
            df = self.feature_engineer.create_lag_features(df, 'return_1d', lags=lags)
            
        if self.use_enhanced_features and max_len > 20:
            df = self.feature_engineer.add_enhanced_features(df, price_series)
        return df
    
    def fit(self, price_series: pd.Series, target_horizon: int = 1):
        """训练 LightGBM 模型"""
        self.last_price = price_series.iloc[-1]
        
        df = self._prepare_features(price_series)
        df['target'] = self.feature_engineer.create_target(price_series, target_horizon)
        df = df.dropna()
        
        feature_cols = [c for c in df.columns if c not in ['price', 'target']]
        self.feature_columns = feature_cols
        
        X = df[feature_cols].values
        y = df['target'].values
        
        if self.scaler:
            X = self.scaler.fit_transform(X)
        
        # 训练 LightGBM 模型
        self.model = lgb.LGBMRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            objective='regression',
            random_state=42,
            verbose=-1
        )
        self.model.fit(X, y)
        
        self._last_features = df[feature_cols].iloc[-1:].values
        if self.scaler:
            self._last_features = self.scaler.transform(self._last_features)
        
        return self
    
    def predict(self, horizon: int = 5) -> pd.DataFrame:
        """预测未来收益率并转换为价格"""
        if self.model is None:
            raise ValueError("请先调用 fit() 方法训练模型")
        
        predictions = []
        current_price = self.last_price
        current_features = self._last_features.copy()
        
        last_date = pd.Timestamp.now()
        future_dates = pd.bdate_range(start=last_date + timedelta(days=1), periods=horizon)
        
        for i in range(horizon):
            pred_return = self.model.predict(current_features)[0]
            pred_price = current_price * (1 + pred_return)
            predictions.append(pred_price)
            current_price = pred_price
        
        result = pd.DataFrame({
            'prediction': predictions
        }, index=future_dates)
        
        return result
    
    def get_feature_importance(self) -> pd.Series:
        """获取特征重要性"""
        if self.model is None or self.feature_columns is None:
            raise ValueError("请先调用 fit() 方法训练模型")
        
        importance = pd.Series(
            self.model.feature_importances_,
            index=self.feature_columns
        ).sort_values(ascending=False)
        
        return importance


# ==================== ARIMA 预测模型 ====================

class ARIMAForecaster:
    """
    使用 ARIMA 进行价格预测
    优点：经典时序模型，理论基础扎实，适合平稳序列
    """
    
    def __init__(self, order: Tuple[int, int, int] = (2, 1, 2), seasonal_order: Optional[Tuple[int, int, int, int]] = None):
        """
        初始化 ARIMA 预测器
        
        参数:
            order: (p, d, q) ARIMA 参数
            seasonal_order: (P, D, Q, s) 季节性参数，None 则使用非季节性 ARIMA
        """
        if not STATSMODELS_AVAILABLE:
            raise ImportError("请安装 statsmodels: pip install statsmodels")
        
        self.order = order
        self.seasonal_order = seasonal_order
        self.model = None
        self.last_price = None
    
    def fit(self, price_series: pd.Series):
        """训练 ARIMA 模型"""
        self.last_price = price_series.iloc[-1]
        
        try:
            if self.seasonal_order:
                self.model = SARIMAX(
                    price_series.values,
                    order=self.order,
                    seasonal_order=self.seasonal_order,
                    enforce_stationarity=False,
                    enforce_invertibility=False
                )
            else:
                self.model = ARIMA(price_series.values, order=self.order)
            
            self.model = self.model.fit(disp=False)
        except Exception as e:
            # 如果拟合失败，使用简单参数
            try:
                self.model = ARIMA(price_series.values, order=(1, 1, 1))
                self.model = self.model.fit(disp=False)
            except:
                raise ValueError(f"ARIMA 模型拟合失败: {e}")
        
        return self
    
    def predict(self, horizon: int = 5) -> pd.DataFrame:
        """预测未来价格"""
        if self.model is None:
            raise ValueError("请先调用 fit() 方法训练模型")
        
        try:
            forecast = self.model.forecast(steps=horizon)
            conf_int = self.model.get_forecast(steps=horizon).conf_int()
        except Exception as e:
            # 如果预测失败，使用最后价格
            forecast = np.full(horizon, self.last_price)
            conf_int = pd.DataFrame({
                'lower': forecast * 0.95,
                'upper': forecast * 1.05
            })
        
        last_date = pd.Timestamp.now()
        future_dates = pd.bdate_range(start=last_date + timedelta(days=1), periods=horizon)
        
        result = pd.DataFrame({
            'prediction': forecast,
            'lower_bound': conf_int.iloc[:, 0] if isinstance(conf_int, pd.DataFrame) else forecast * 0.95,
            'upper_bound': conf_int.iloc[:, 1] if isinstance(conf_int, pd.DataFrame) else forecast * 1.05
        }, index=future_dates)
        
        return result


# ==================== Random Forest 预测模型 ====================

class RandomForestForecaster:
    """
    使用 Random Forest 进行价格预测
    优点：简单稳定，不易过拟合，可解释性强
    """
    
    def __init__(self, 
                 n_estimators: int = 100,
                 max_depth: int = 10,
                 lookback: int = 60,
                 use_enhanced_features: bool = False):
        """
        初始化 Random Forest 预测器
        
        参数:
            n_estimators: 树的数量
            max_depth: 树的最大深度
            lookback: 特征窗口大小
            use_enhanced_features: 是否启用增强特征
        """
        if not SKLEARN_AVAILABLE or RandomForestRegressor is None:
            raise ImportError("请安装 scikit-learn: pip install scikit-learn")
        
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.lookback = lookback
        self.use_enhanced_features = use_enhanced_features
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.scaler = StandardScaler()
        self.feature_columns = None
        self.last_price = None
    
    def _prepare_features(self, price_series: pd.Series) -> pd.DataFrame:
        """准备特征"""
        # 动态调整特征窗口
        max_len = len(price_series)
        windows = [w for w in [5, 10, 20, 60] if w < max_len]
        if not windows:
            windows = [min(5, max_len // 2)] if max_len > 2 else [1]
            
        df = self.feature_engineer.create_price_features(price_series, lookback_windows=windows)
        
        # 动态调整 lag
        max_lag = min(10, max_len // 4)
        if max_lag > 0:
            lags = [l for l in [1, 2, 3, 5, 10] if l <= max_lag]
            df = self.feature_engineer.create_lag_features(df, 'return_1d', lags=lags)
            
        if self.use_enhanced_features and max_len > 20:
            df = self.feature_engineer.add_enhanced_features(df, price_series)
        return df
    
    def fit(self, price_series: pd.Series, target_horizon: int = 1):
        """训练 Random Forest 模型"""
        self.last_price = price_series.iloc[-1]
        
        df = self._prepare_features(price_series)
        df['target'] = self.feature_engineer.create_target(price_series, target_horizon)
        df = df.dropna()
        
        feature_cols = [c for c in df.columns if c not in ['price', 'target']]
        self.feature_columns = feature_cols
        
        X = df[feature_cols].values
        y = df['target'].values
        
        X = self.scaler.fit_transform(X)
        
        self.model = RandomForestRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X, y)
        
        self._last_features = df[feature_cols].iloc[-1:].values
        self._last_features = self.scaler.transform(self._last_features)
        
        return self
    
    def predict(self, horizon: int = 5) -> pd.DataFrame:
        """预测未来收益率并转换为价格"""
        if self.model is None:
            raise ValueError("请先调用 fit() 方法训练模型")
        
        predictions = []
        current_price = self.last_price
        current_features = self._last_features.copy()
        
        last_date = pd.Timestamp.now()
        future_dates = pd.bdate_range(start=last_date + timedelta(days=1), periods=horizon)
        
        for i in range(horizon):
            pred_return = self.model.predict(current_features)[0]
            pred_price = current_price * (1 + pred_return)
            predictions.append(pred_price)
            current_price = pred_price
        
        result = pd.DataFrame({
            'prediction': predictions
        }, index=future_dates)
        
        return result
    
    def get_feature_importance(self) -> pd.Series:
        """获取特征重要性"""
        if self.model is None or self.feature_columns is None:
            raise ValueError("请先调用 fit() 方法训练模型")
        
        importance = pd.Series(
            self.model.feature_importances_,
            index=self.feature_columns
        ).sort_values(ascending=False)
        
        return importance


# ==================== GRU 预测模型 ====================

class GRUForecaster:
    """
    使用 GRU (Gated Recurrent Unit) 进行价格预测
    优点：比 LSTM 更轻量，训练更快，适合短期预测
    """
    
    def __init__(self,
                 hidden_size: int = 64,
                 num_layers: int = 2,
                 dropout: float = 0.2,
                 sequence_length: int = 30,
                 learning_rate: float = 0.001,
                 epochs: int = 100,
                 batch_size: int = 32):
        """
        初始化 GRU 预测器
        
        参数:
            hidden_size: 隐藏层大小
            num_layers: GRU 层数
            dropout: Dropout 比例
            sequence_length: 输入序列长度
            learning_rate: 学习率
            epochs: 训练轮数
            batch_size: 批次大小
        """
        if not TORCH_AVAILABLE:
            raise ImportError("请安装 PyTorch: pip install torch")
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.sequence_length = sequence_length
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.model = None
        self.scaler = MinMaxScaler() if SKLEARN_AVAILABLE else None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.last_prices = None
    
    def _build_model(self, input_size: int):
        """构建 GRU 模型"""
        class GRUModel(nn.Module):
            def __init__(self, input_size, hidden_size, num_layers, dropout):
                super(GRUModel, self).__init__()
                self.gru = nn.GRU(input_size, hidden_size, num_layers, 
                                 batch_first=True, dropout=dropout if num_layers > 1 else 0)
                self.fc = nn.Linear(hidden_size, 1)
            
            def forward(self, x):
                out, _ = self.gru(x)
                out = self.fc(out[:, -1, :])
                return out
        
        return GRUModel(input_size, self.hidden_size, self.num_layers, self.dropout)
    
    def _create_sequences(self, data):
        """创建序列数据"""
        X, y = [], []
        for i in range(len(data) - self.sequence_length):
            X.append(data[i:i+self.sequence_length])
            y.append(data[i+self.sequence_length])
        return np.array(X), np.array(y)
    
    def fit(self, price_series: pd.Series):
        """训练 GRU 模型"""
        self.last_prices = price_series.tail(self.sequence_length).values
        
        prices = price_series.values.reshape(-1, 1)
        
        if self.scaler:
            prices_scaled = self.scaler.fit_transform(prices)
        else:
            prices_scaled = prices
        
        X, y = self._create_sequences(prices_scaled)
        
        X = torch.FloatTensor(X).to(self.device)
        y = torch.FloatTensor(y).to(self.device)
        
        self.model = self._build_model(input_size=1).to(self.device)
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        
        self.model.train()
        for epoch in range(self.epochs):
            optimizer.zero_grad()
            outputs = self.model(X)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 20 == 0:
                print(f'GRU Epoch [{epoch+1}/{self.epochs}], Loss: {loss.item():.6f}')
        
        return self
    
    def predict(self, horizon: int = 5) -> pd.DataFrame:
        """预测未来价格"""
        if self.model is None:
            raise ValueError("请先调用 fit() 方法训练模型")
        
        self.model.eval()
        predictions = []
        
        current_seq = self.last_prices.reshape(-1, 1)
        if self.scaler:
            current_seq = self.scaler.transform(current_seq)
        
        with torch.no_grad():
            for _ in range(horizon):
                seq_tensor = torch.FloatTensor(current_seq).unsqueeze(0).to(self.device)
                pred = self.model(seq_tensor).cpu().numpy()[0, 0]
                
                if self.scaler:
                    pred_price = self.scaler.inverse_transform([[pred]])[0, 0]
                else:
                    pred_price = pred
                
                predictions.append(pred_price)
                
                current_seq = np.roll(current_seq, -1, axis=0)
                current_seq[-1] = pred
        
        last_date = pd.Timestamp.now()
        future_dates = pd.bdate_range(start=last_date + timedelta(days=1), periods=horizon)
        
        result = pd.DataFrame({
            'prediction': predictions
        }, index=future_dates)
        
        return result


# ==================== 集成预测器 ====================

class EnsembleForecaster:
    """
    集成多个预测模型
    通过加权平均或投票机制整合多模型预测结果
    """
    
    def __init__(self, 
                 models: Dict[str, object] = None,
                 weights: Dict[str, float] = None):
        """
        初始化集成预测器
        
        参数:
            models: 模型字典 {'model_name': model_instance}
            weights: 权重字典 {'model_name': weight}
        """
        self.models = models or {}
        self.weights = weights or {}
        self._normalize_weights()
    
    def _normalize_weights(self):
        """归一化权重"""
        if self.weights:
            total = sum(self.weights.values())
            self.weights = {k: v/total for k, v in self.weights.items()}
    
    def add_model(self, name: str, model: object, weight: float = 1.0):
        """添加模型"""
        self.models[name] = model
        self.weights[name] = weight
        self._normalize_weights()
    
    def fit(self, price_series: pd.Series):
        """训练所有模型"""
        for name, model in self.models.items():
            print(f"训练模型: {name}")
            model.fit(price_series)
        return self
    
    def predict(self, horizon: int = 5) -> pd.DataFrame:
        """集成预测"""
        predictions = {}
        
        for name, model in self.models.items():
            try:
                pred = model.predict(horizon)
                if 'prediction' in pred.columns:
                    predictions[name] = pred['prediction']
                elif 'yhat' in pred.columns:
                    predictions[name] = pred['yhat']
            except Exception as e:
                print(f"模型 {name} 预测失败: {e}")
        
        if not predictions:
            raise ValueError("所有模型预测失败")
        
        # 创建结果DataFrame
        result_df = pd.DataFrame(predictions)
        
        # 加权平均
        ensemble_pred = sum(
            result_df[name] * self.weights.get(name, 1.0/len(predictions))
            for name in result_df.columns
        )
        
        result = pd.DataFrame({
            'prediction': ensemble_pred,
            'std': result_df.std(axis=1)  # 预测不确定性
        })
        
        # 添加各模型的单独预测
        for name in predictions:
            result[f'{name}_pred'] = predictions[name]
        
        return result


# ==================== 简化接口函数 ====================

def advanced_price_forecast(price_df: pd.DataFrame, 
                            horizon: int = 5,
                            model_type: str = 'auto',
                            return_confidence: bool = False,
                            use_enhanced_features: bool = False) -> pd.DataFrame:
    """
    高级价格预测函数 - 替代 simple_price_forecast
    
    参数:
        price_df: 价格数据，列为资产代码
        horizon: 预测天数
        model_type: 模型类型 ('prophet', 'xgboost', 'lstm', 'ensemble', 'auto')
        return_confidence: 是否返回置信区间
        use_enhanced_features: 是否启用增强特征（当前主要作用于 XGBoost）
    
    返回:
        预测结果DataFrame
    """
    if price_df.empty:
        raise ValueError("price_df 为空，无法进行预测")
    
    # 自动选择可用的最佳模型
    if model_type == 'auto':
        if PROPHET_AVAILABLE:
            model_type = 'prophet'
        elif XGBOOST_AVAILABLE:
            model_type = 'xgboost'
        else:
            model_type = 'simple'  # 回退到简单方法
    
    results = {}
    confidence_lower = {}
    confidence_upper = {}
    
    for ticker in price_df.columns:
        price_series = price_df[ticker].dropna()
        
        if len(price_series) < 30:
            print(f"警告: {ticker} 数据不足30天，使用简单预测")
            # 使用简单方法
            window = min(20, len(price_series))
            base = price_series.tail(window).mean()
            forecasts = [base * (1 + np.random.normal(0, 0.01)) for _ in range(horizon)]
            results[ticker] = forecasts
            continue
        
        try:
            if model_type == 'prophet' and PROPHET_AVAILABLE:
                forecaster = ProphetForecaster()
                forecaster.fit(price_series)
                pred = forecaster.predict(horizon)
                results[ticker] = pred['prediction'].values
                if return_confidence:
                    confidence_lower[ticker] = pred['lower_bound'].values
                    confidence_upper[ticker] = pred['upper_bound'].values
            
            elif model_type == 'xgboost' and XGBOOST_AVAILABLE:
                forecaster = XGBoostForecaster(
                    lookback=min(60, len(price_series)),
                    use_enhanced_features=use_enhanced_features,
                )
                forecaster.fit(price_series)
                pred = forecaster.predict(horizon)
                results[ticker] = pred['prediction'].values
            
            elif model_type == 'lstm' and TORCH_AVAILABLE:
                forecaster = LSTMForecaster(
                    sequence_length=min(30, len(price_series) // 2),
                    epochs=50
                )
                forecaster.fit(price_series)
                pred = forecaster.predict(horizon)
                results[ticker] = pred['prediction'].values

            elif model_type == 'ensemble':
                # 集成模型：Prophet + XGBoost + LSTM 的加权组合
                base_models: Dict[str, object] = {}
                base_weights: Dict[str, float] = {}

                # 预设权重：Prophet / XGBoost / LSTM = 0.3 / 0.4 / 0.3
                if PROPHET_AVAILABLE:
                    base_models["Prophet"] = ProphetForecaster()
                    base_weights["Prophet"] = 0.3
                if XGBOOST_AVAILABLE:
                    base_models["XGBoost"] = XGBoostForecaster(
                        lookback=min(60, len(price_series)),
                        use_enhanced_features=use_enhanced_features,
                    )
                    base_weights["XGBoost"] = 0.4
                if TORCH_AVAILABLE:
                    base_models["LSTM"] = LSTMForecaster(
                        sequence_length=min(30, len(price_series) // 2),
                        epochs=50,
                    )
                    base_weights["LSTM"] = 0.3

                # 若所有高级模型均不可用，则退回简单方法
                if not base_models:
                    raise RuntimeError("无可用高级模型用于集成预测")

                ensemble = EnsembleForecaster(models=base_models, weights=base_weights)
                ensemble.fit(price_series)
                pred = ensemble.predict(horizon)
                results[ticker] = pred["prediction"].values
            
            else:
                # 回退到简单方法
                window = min(20, len(price_series))
                base = price_series.tail(window).mean()
                forecasts = [base * (1 + np.random.normal(0, 0.01)) for _ in range(horizon)]
                results[ticker] = forecasts
        
        except Exception as e:
            print(f"模型预测 {ticker} 失败: {e}，使用简单预测")
            window = min(20, len(price_series))
            base = price_series.tail(window).mean()
            forecasts = [base * (1 + np.random.normal(0, 0.01)) for _ in range(horizon)]
            results[ticker] = forecasts
    
    # 生成未来日期
    last_date = price_df.index[-1]
    future_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=horizon)
    
    result_df = pd.DataFrame(results, index=future_dates)
    
    if return_confidence and confidence_lower:
        return result_df, pd.DataFrame(confidence_lower, index=future_dates), pd.DataFrame(confidence_upper, index=future_dates)
    
    return result_df


# ==================== 模型评估工具 ====================

class ModelEvaluator:
    """模型评估工具"""
    
    @staticmethod
    def calculate_metrics(actual: pd.Series, predicted: pd.Series) -> Dict[str, float]:
        """
        计算预测评估指标
        
        返回:
            MAE, RMSE, MAPE, 方向准确率
        """
        # 确保数据对齐
        actual = actual.dropna()
        predicted = predicted.dropna()
        common_idx = actual.index.intersection(predicted.index)
        actual = actual.loc[common_idx]
        predicted = predicted.loc[common_idx]
        
        if len(actual) == 0:
            return {}
        
        # MAE
        mae = np.mean(np.abs(actual - predicted))
        
        # RMSE
        rmse = np.sqrt(np.mean((actual - predicted) ** 2))
        
        # MAPE
        mape = np.mean(np.abs((actual - predicted) / actual)) * 100
        
        # 方向准确率
        actual_direction = np.sign(actual.diff().dropna())
        predicted_direction = np.sign(predicted.diff().dropna())
        common_dir_idx = actual_direction.index.intersection(predicted_direction.index)
        if len(common_dir_idx) > 0:
            direction_accuracy = np.mean(
                actual_direction.loc[common_dir_idx] == predicted_direction.loc[common_dir_idx]
            ) * 100
        else:
            direction_accuracy = 0
        
        return {
            'MAE': mae,
            'RMSE': rmse,
            'MAPE': mape,
            'Direction_Accuracy': direction_accuracy
        }
    
    @staticmethod
    def walk_forward_validation(price_series: pd.Series,
                                 model_class,
                                 n_splits: int = 5,
                                 test_size: int = 20) -> pd.DataFrame:
        """
        滚动窗口验证
        
        参数:
            price_series: 价格序列
            model_class: 模型类
            n_splits: 分割数
            test_size: 测试集大小
        
        返回:
            各折评估结果（包含预测精度与简单交易指标）
        """
        results = []
        
        for i in range(n_splits):
            train_end = len(price_series) - (n_splits - i) * test_size
            test_start = train_end
            test_end = test_start + test_size
            
            if train_end < 60:  # 训练数据不足
                continue
            
            train_data = price_series.iloc[:train_end]
            test_data = price_series.iloc[test_start:test_end]
            
            try:
                model = model_class()
                model.fit(train_data)
                pred = model.predict(horizon=len(test_data))
                
                # 对齐数据
                y_true = test_data.reset_index(drop=True)
                y_pred = pred["prediction"].reset_index(drop=True)
                
                # 预测误差类指标
                metrics = ModelEvaluator.calculate_metrics(y_true, y_pred)
                
                # 简单方向策略的交易指标
                try:
                    pred_direction = np.sign(y_pred.diff())
                    actual_returns = y_true.pct_change()
                    strategy_returns = actual_returns * pred_direction.shift(1)
                    strategy_returns = strategy_returns.dropna()
                    
                    if not strategy_returns.empty:
                        cum_return = (1 + strategy_returns).cumprod().iloc[-1] - 1
                        sharpe = (
                            strategy_returns.mean() / strategy_returns.std() * np.sqrt(252)
                            if strategy_returns.std() > 0
                            else 0.0
                        )
                    else:
                        cum_return = 0.0
                        sharpe = 0.0
                    
                    metrics["Strategy_CumReturn"] = float(cum_return)
                    metrics["Strategy_Sharpe"] = float(sharpe)
                except Exception:
                    metrics["Strategy_CumReturn"] = 0.0
                    metrics["Strategy_Sharpe"] = 0.0
                
                metrics["fold"] = i + 1
                results.append(metrics)
            except Exception as e:
                print(f"Fold {i+1} 验证失败: {e}")
        
        return pd.DataFrame(results)


# ==================== 检查可用模型 ====================

def get_available_models() -> Dict[str, bool]:
    """返回可用的模型列表"""
    return {
        'Prophet': PROPHET_AVAILABLE,
        'XGBoost': XGBOOST_AVAILABLE,
        'LightGBM': LIGHTGBM_AVAILABLE,
        'ARIMA': STATSMODELS_AVAILABLE,
        'Random Forest': SKLEARN_AVAILABLE,
        'LSTM': TORCH_AVAILABLE,
        'GRU': TORCH_AVAILABLE,
        'Sklearn': SKLEARN_AVAILABLE
    }


# ==================== 快速预测接口（使用特征仓库和模型注册表） ====================

def quick_predict(
    ticker: str,
    horizon: int = 5,
    model_type: str = "xgboost",
    use_production_model: bool = True,
    save_signal: bool = False,
    lookback_days: Optional[int] = None,
) -> Optional[pd.DataFrame]:
    """
    快速预测接口（毫秒级响应）
    - 从注册表加载生产模型（优先从缓存）
    - 从特征仓库读取最新特征
    - 直接 predict，不做 fit
    
    参数:
        ticker: 标的代码
        horizon: 预测天数
        model_type: 模型类型
        use_production_model: 是否使用生产模型（False则允许即时训练）
        save_signal: 是否保存信号到信号仓库
        lookback_days: 如果即时训练，指定回看天数
        
    返回:
        预测结果DataFrame，失败返回None
    """
    try:
        from .feature_store import get_feature_store
        from .signal_store import get_signal_store
        from .data_store import load_local_price_history
        
        manager = ModelManager()
        registry = manager.registry
        cache = manager.cache
        
        # 1. 尝试从缓存加载生产模型
        model = None
        model_id = None
        
        # 如果指定了 lookback_days，强制不使用生产模型，以便重新训练
        if lookback_days is not None:
            use_production_model = False

        if use_production_model:
            model_id = registry.get_production_model(ticker)
            if model_id:
                model_info = registry.get_model_info(model_id)
                # 检查模型类型是否匹配
                if model_info and model_info.get("model_type") == model_type:
                    # 先尝试从缓存获取
                    model = cache.get(model_id)
                    
                    # 如果缓存没有，从磁盘加载
                    if model is None:
                        model_path = model_info.get("model_path")
                        if model_path and os.path.exists(model_path):
                            try:
                                if JOBLIB_AVAILABLE:
                                    model = joblib.load(model_path)
                                    # 放入缓存
                                    cache.put(model_id, model)
                            except Exception as e:
                                print(f"加载模型失败 ({model_id}): {e}")
                else:
                    # 模型类型不匹配，尝试查找匹配类型的生产模型
                    # 这里简化处理，如果类型不匹配则返回None，回退到实时训练
                    pass
        
        # 2. 如果没有生产模型，尝试从ModelManager缓存获取（仅XGBoost，其他模型需要从注册表）
        if model is None and model_type == "xgboost" and lookback_days is None:
            price_series = load_local_price_history(ticker)
            if price_series is not None:
                model = manager.get_xgboost_model(
                    ticker, price_series, max_age_hours=24
                )
                if model:
                    # 使用缓存的模型，但未注册，model_id设为空
                    model_id = "cached"
        
        # 3. 如果仍然没有模型且允许训练，则训练新模型（研究模式）
        if model is None and not use_production_model:
            price_series = load_local_price_history(ticker)
            
            # 如果指定了 lookback_days，截取数据
            if price_series is not None and lookback_days is not None:
                price_series = price_series.tail(lookback_days)

            # 放宽数据长度限制，至少需要 10 天（XGBoost/Simple）
            if price_series is not None and len(price_series) > 10:
                # 针对短数据，强制调整模型参数
                if len(price_series) < 60:
                    print(f"数据不足 60 天 ({len(price_series)}), 尝试使用短周期训练")
                    # 对于极短数据，XGBoost 可能表现不佳，可以考虑回退，或者调整参数
                    # 这里我们依赖 XGBoostForecaster 内部的动态特征调整
                
                try:
                    feature_store = get_feature_store()
                    model_id = manager.train_model(
                        ticker,
                        price_series,
                        model_type=model_type,
                        use_enhanced_features=True if model_type in ["xgboost", "lightgbm", "random_forest"] and len(price_series) > 30 else False,
                        register_model=True,
                        features_version=feature_store.get_feature_version(),
                        lookback=min(60, len(price_series) // 2) if len(price_series) < 120 else None
                    )
                    # 从ModelManager获取模型
                    key = manager._model_key(ticker, model_type)
                    model = manager.models.get(key)
                    if model and model_id:
                        cache.put(model_id, model)
                except Exception as e:
                    print(f"即时训练失败: {e}")
                    # 失败后，尝试回退到简单预测
                    pass
        
        if model is None:
            # 最后的兜底：使用简单预测
            if price_series is not None and len(price_series) > 5:
                from .advanced_forecasting import simple_price_forecast  # 防止循环引用，或者直接实现
                # 简单移动平均预测
                window = min(20, len(price_series))
                base = price_series.tail(window).mean()
                last_date = price_series.index[-1]
                future_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=horizon)
                forecasts = [base * (1 + np.random.normal(0, 0.01)) for _ in range(horizon)]
                return pd.DataFrame({'prediction': forecasts}, index=future_dates)
            return None
        
        # 4. 执行预测（模型已加载，直接预测）
        if isinstance(model, XGBoostForecaster):
            # XGBoost需要价格序列进行预测
            price_series = load_local_price_history(ticker)
            if price_series is None or price_series.empty:
                return None
            pred = model.predict(horizon)
        elif isinstance(model, LightGBMForecaster):
            price_series = load_local_price_history(ticker)
            if price_series is None or price_series.empty:
                return None
            pred = model.predict(horizon)
        elif isinstance(model, RandomForestForecaster):
            price_series = load_local_price_history(ticker)
            if price_series is None or price_series.empty:
                return None
            pred = model.predict(horizon)
        elif isinstance(model, ProphetForecaster):
            pred = model.predict(horizon)
        elif isinstance(model, LSTMForecaster):
            pred = model.predict(horizon)
        elif isinstance(model, GRUForecaster):
            pred = model.predict(horizon)
        else:
            return None
        
        # 5. 保存信号（如果启用）
        if save_signal and pred is not None and not pred.empty:
            signal_store = get_signal_store()
            price_series = load_local_price_history(ticker)
            if price_series is not None and not price_series.empty:
                last_price = float(price_series.iloc[-1])
                pred_price = float(pred["prediction"].iloc[0])
                prediction_return = (pred_price - last_price) / last_price
                
                direction = 1 if prediction_return > 0.01 else (-1 if prediction_return < -0.01 else 0)
                confidence = min(abs(prediction_return) * 10, 1.0)  # 简化的置信度计算
                signal = "buy" if direction > 0 else ("sell" if direction < 0 else "hold")
                
                signal_store.save_signal(
                    ticker=ticker,
                    prediction=prediction_return,
                    direction=direction,
                    confidence=confidence,
                    signal=signal,
                    model_id=model_id or "unknown",
                    status="pending",
                )
        
        return pred
        
    except Exception as e:
        print(f"快速预测失败 ({ticker}): {e}")
        return None


def generate_ai_signals_for_series(
    price_series: pd.Series,
    horizon: int = 1,
    model_type: str = "xgboost",
    use_enhanced_features: bool = True,
    min_train_size: int = 60,
) -> pd.Series:
    """
    基于滚动训练的方式，为单个资产生成 AI 预测交易信号序列。

    简化设计：
    - 目前仅针对 XGBoost / Prophet / LSTM 等前向预测器；
    - 每次以“过去 min_train_size~当前”的历史训练模型，预测未来 T+horizon；
    - 使用预测价与当前价的差值方向，生成 +1 / -1 / 0 的信号。
    """
    if price_series is None or price_series.empty:
        return pd.Series(dtype=float)

    series = price_series.dropna()
    if len(series) < min_train_size + horizon or horizon <= 0:
        return pd.Series(0, index=series.index, dtype=float)

    signals = pd.Series(0, index=series.index, dtype=float)

    for end_idx in range(min_train_size, len(series) - horizon):
        train_data = series.iloc[:end_idx]
        signal_date = series.index[end_idx + horizon - 1]

        try:
            if model_type == "xgboost" and XGBOOST_AVAILABLE:
                model = XGBoostForecaster(
                    lookback=min(60, len(train_data)),
                    use_enhanced_features=use_enhanced_features,
                )
                model.fit(train_data)
                pred_df = model.predict(horizon=horizon)
                pred_price = float(pred_df["prediction"].iloc[horizon - 1])
            elif model_type == "prophet" and PROPHET_AVAILABLE:
                model = ProphetForecaster()
                model.fit(train_data)
                pred_df = model.predict(horizon=horizon)
                pred_price = float(pred_df["prediction"].iloc[horizon - 1])
            elif model_type == "lstm" and TORCH_AVAILABLE:
                model = LSTMForecaster(
                    sequence_length=min(30, len(train_data) // 2),
                    epochs=50,
                )
                model.fit(train_data)
                pred_df = model.predict(horizon=horizon)
                pred_price = float(pred_df["prediction"].iloc[horizon - 1])
            else:
                continue

            last_price = float(train_data.iloc[-1])
            if last_price <= 0:
                continue
            ret = (pred_price - last_price) / last_price
            if ret > 0:
                signals.loc[signal_date] = 1.0
            elif ret < 0:
                signals.loc[signal_date] = -1.0
            # ret == 0 -> 信号保持为 0
        except Exception:
            # 单次失败不影响整体
            continue

    return signals


# ==================== 模型注册表 ====================

class ModelRegistry:
    """
    模型注册表管理器
    
    职责：
    - 管理模型版本和元数据
    - 维护生产模型映射
    - 支持模型历史查询
    """

    def __init__(self, registry_path: str = "models/registry.json") -> None:
        self.registry_path = registry_path
        self.registry_dir = os.path.dirname(registry_path)
        os.makedirs(self.registry_dir, exist_ok=True)
        self._load_registry()

    def _load_registry(self) -> None:
        """加载注册表"""
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.models = data.get("models", [])
                    self.production_models = data.get("production_models", {})
            except Exception:
                self.models = []
                self.production_models = {}
        else:
            self.models = []
            self.production_models = {}

    def _save_registry(self) -> None:
        """保存注册表"""
        data = {
            "models": self.models,
            "production_models": self.production_models,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def register_model(
        self,
        model_id: str,
        ticker: str,
        model_type: str,
        model_path: str,
        train_date: str,
        train_data_range: List[str],
        features_version: str,
        metrics: Dict[str, float],
        status: str = "staging",
    ) -> None:
        """
        注册新训练的模型
        
        参数:
            model_id: 模型唯一ID
            ticker: 标的代码
            model_type: 模型类型（xgboost/prophet/lstm等）
            model_path: 模型文件路径
            train_date: 训练日期
            train_data_range: 训练数据时间范围 [start, end]
            features_version: 特征版本
            metrics: 评估指标
            status: 状态（staging/production/archived）
        """
        model_entry = {
            "model_id": model_id,
            "ticker": ticker,
            "model_type": model_type,
            "train_date": train_date,
            "train_data_range": train_data_range,
            "features_version": features_version,
            "metrics": metrics,
            "status": status,
            "model_path": model_path,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 移除同ticker的旧staging模型（保留production和archived）
        self.models = [
            m
            for m in self.models
            if not (m["ticker"] == ticker and m["status"] == "staging")
        ]
        self.models.append(model_entry)
        self._save_registry()

    def set_production_model(self, ticker: str, model_id: str) -> bool:
        """
        将某模型设为生产模型
        
        参数:
            ticker: 标的代码
            model_id: 模型ID
            
        返回:
            是否成功
        """
        # 检查模型是否存在
        model = next((m for m in self.models if m["model_id"] == model_id), None)
        if not model:
            return False

        # 将旧的生产模型标记为archived
        old_prod_id = self.production_models.get(ticker)
        if old_prod_id:
            old_model = next(
                (m for m in self.models if m["model_id"] == old_prod_id), None
            )
            if old_model:
                old_model["status"] = "archived"
                old_model["archived_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 设置新生产模型
        model["status"] = "production"
        model["production_since"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.production_models[ticker] = model_id
        self._save_registry()
        return True

    def get_production_model(self, ticker: str) -> Optional[str]:
        """
        获取当前生产模型ID
        
        参数:
            ticker: 标的代码
            
        返回:
            模型ID，不存在则返回None
        """
        return self.production_models.get(ticker)

    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """获取模型详细信息"""
        return next((m for m in self.models if m["model_id"] == model_id), None)
    
    def update_model_metrics(self, model_id: str, metrics: Dict[str, float]) -> bool:
        """
        更新模型的评估指标
        
        参数:
            model_id: 模型ID
            metrics: 评估指标字典
            
        返回:
            是否成功
        """
        for model in self.models:
            if model["model_id"] == model_id:
                if "metrics" not in model:
                    model["metrics"] = {}
                model["metrics"].update(metrics)
                model["evaluated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_registry()
                return True
        return False

    def list_model_history(self, ticker: str) -> List[Dict]:
        """
        查看某资产的历史模型
        
        参数:
            ticker: 标的代码
            
        返回:
            模型列表（按创建时间倒序）
        """
        history = [m for m in self.models if m["ticker"] == ticker]
        history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return history

    def list_production_models(self) -> Dict[str, str]:
        """获取所有生产模型映射"""
        return self.production_models.copy()


# ==================== 模型缓存 ====================

class ModelCache:
    """
    模型内存缓存管理器
    
    职责：
    - 在内存中缓存已加载的模型
    - 避免重复从磁盘加载
    - 支持LRU淘汰策略
    """

    def __init__(self, max_size: int = 50):
        """
        初始化缓存

        参数:
            max_size: 最大缓存模型数量
        """
        self.cache: Dict[str, object] = {}
        self.access_time: Dict[str, datetime] = {}
        self.max_size = max_size

    def get(self, model_id: str) -> Optional[object]:
        """
        从缓存获取模型

        参数:
            model_id: 模型ID

        返回:
            模型对象，不存在返回None
        """
        if model_id in self.cache:
            self.access_time[model_id] = datetime.now()
            return self.cache[model_id]
        return None

    def put(self, model_id: str, model: object) -> None:
        """
        将模型放入缓存

        参数:
            model_id: 模型ID
            model: 模型对象
        """
        # 如果缓存已满，删除最久未使用的
        if len(self.cache) >= self.max_size and model_id not in self.cache:
            # 找到最久未使用的模型
            oldest_id = min(self.access_time.items(), key=lambda x: x[1])[0]
            del self.cache[oldest_id]
            del self.access_time[oldest_id]

        self.cache[model_id] = model
        self.access_time[model_id] = datetime.now()

    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
        self.access_time.clear()

    def remove(self, model_id: str) -> None:
        """
        从缓存移除模型

        参数:
            model_id: 模型ID
        """
        if model_id in self.cache:
            del self.cache[model_id]
            del self.access_time[model_id]


# 全局模型缓存单例
_model_cache = ModelCache()


# ==================== 模型管理器（中期：离线训练 + 在线加载） ====================

class ModelManager:
    """
    简单模型管理器
    
    设计目标：
    - 为指定 ticker 缓存训练好的模型；
    - 按更新时间决定是否需要重新训练；
    - 将模型持久化到本地 `models/` 目录，供 Dashboard / 守护进程复用。
    - 集成模型注册表功能
    """

    def __init__(self, model_dir: str = "models/") -> None:
        self.model_dir = model_dir
        self.models: Dict[str, object] = {}
        self.last_update: Dict[str, datetime] = {}
        os.makedirs(self.model_dir, exist_ok=True)
        self.registry = ModelRegistry(os.path.join(model_dir, "registry.json"))
        self.cache = _model_cache

    def _model_key(self, ticker: str, model_type: str) -> str:
        return f"{ticker}::{model_type}"

    def _model_path(self, ticker: str, model_type: str) -> str:
        safe_ticker = (
            ticker.replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
            .replace(" ", "_")
        )
        filename = f"{safe_ticker}_{model_type}.pkl"
        return os.path.join(self.model_dir, filename)

    def should_retrain(self, ticker: str, max_age_hours: float = 24.0) -> bool:
        """
        判断某个资产的模型是否需要重新训练
        
        max_age_hours: 模型允许的最长“失效时间”，默认 24 小时。
        """
        ts = self.last_update.get(ticker)
        if ts is None:
            return True
        age_hours = (datetime.now() - ts).total_seconds() / 3600.0
        return age_hours > max_age_hours

    def save_model(self, ticker: str, model_type: str = "xgboost") -> None:
        """将模型持久化到本地"""
        if not JOBLIB_AVAILABLE:
            return
        key = self._model_key(ticker, model_type)
        if key not in self.models:
            return
        path = self._model_path(ticker, model_type)
        try:
            joblib.dump(self.models[key], path)
        except Exception as exc:  # pragma: no cover - 仅日志用途
            print(f"保存模型失败 ({ticker}, {model_type}): {exc}")

    def load_model(self, ticker: str, model_type: str = "xgboost") -> bool:
        """尝试从磁盘加载模型到内存，成功返回 True"""
        if not JOBLIB_AVAILABLE:
            return False
        path = self._model_path(ticker, model_type)
        if not os.path.exists(path):
            return False
        try:
            model = joblib.load(path)
            key = self._model_key(ticker, model_type)
            self.models[key] = model
            # 注意：这里的 last_update 只表示“最近一次成功加载”，
            # 真正的训练时间可以在未来扩展为单独字段持久化。
            self.last_update[ticker] = datetime.now()
            return True
        except Exception as exc:  # pragma: no cover - 仅日志用途
            print(f"加载模型失败 ({ticker}, {model_type}): {exc}")
            return False

    # --- 针对 XGBoost 的快捷方法（当前主要管理对象） ---

    def train_xgboost(
        self,
        ticker: str,
        price_series: pd.Series,
        use_enhanced_features: bool = True,
        lookback: Optional[int] = None,
        register_model: bool = True,
        features_version: str = "v1.0",
    ) -> str:
        """
        为单个资产训练 XGBoost 模型并保存到磁盘
        
        参数:
            ticker: 标的代码
            price_series: 价格序列
            use_enhanced_features: 是否使用增强特征
            lookback: 回看窗口
            register_model: 是否注册到注册表
            features_version: 特征版本
            
        返回:
            模型ID
        """
        if not XGBOOST_AVAILABLE:
            raise RuntimeError("XGBoost 未安装，无法训练模型")

        lookback_val = lookback or min(60, len(price_series))
        model = XGBoostForecaster(
            lookback=lookback_val,
            use_enhanced_features=use_enhanced_features,
        )
        model.fit(price_series)

        key = self._model_key(ticker, "xgboost")
        self.models[key] = model
        self.last_update[ticker] = datetime.now()
        self.save_model(ticker, "xgboost")

        # 注册模型（如果启用）
        if register_model:
            model_id = f"xgb_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_path = self._model_path(ticker, "xgboost")
            train_date = datetime.now().strftime("%Y-%m-%d")
            train_data_range = [
                price_series.index.min().strftime("%Y-%m-%d"),
                price_series.index.max().strftime("%Y-%m-%d"),
            ]

            # 计算简单评估指标（可选，这里简化处理）
            metrics = {"model_type": "xgboost", "lookback": lookback_val}

            self.registry.register_model(
                model_id=model_id,
                ticker=ticker,
                model_type="xgboost",
                model_path=model_path,
                train_date=train_date,
                train_data_range=train_data_range,
                features_version=features_version,
                metrics=metrics,
                status="staging",
            )
            return model_id

        return ""

    def get_xgboost_model(
        self,
        ticker: str,
        price_series: Optional[pd.Series] = None,
        use_enhanced_features: bool = True,
        max_age_hours: float = 24.0,
    ) -> Optional[XGBoostForecaster]:
        """
        获取指定 ticker 的 XGBoost 模型：
        - 若内存中已有且不过期，直接返回；
        - 否则尝试从磁盘加载；
        - 若仍然没有且提供了 price_series，则视为需要重新训练。
        """
        key = self._model_key(ticker, "xgboost")

        # 1) 内存中已有且不过期
        if key in self.models and not self.should_retrain(ticker, max_age_hours):
            model = self.models[key]
            if isinstance(model, XGBoostForecaster):
                return model

        # 2) 尝试从磁盘加载
        if self.load_model(ticker, "xgboost"):
            model = self.models.get(key)
            if isinstance(model, XGBoostForecaster):
                return model

        # 3) 如果提供了价格序列，则重新训练
        if price_series is not None and len(price_series) > 30:
            self.train_xgboost(
                ticker,
                price_series,
                use_enhanced_features=use_enhanced_features,
            )
            model = self.models.get(key)
            if isinstance(model, XGBoostForecaster):
                return model

        return None

    # --- 针对 LightGBM 的快捷方法 ---

    def train_lightgbm(
        self,
        ticker: str,
        price_series: pd.Series,
        use_enhanced_features: bool = True,
        lookback: Optional[int] = None,
        register_model: bool = True,
        features_version: str = "v1.0",
    ) -> str:
        """训练 LightGBM 模型并保存到磁盘"""
        if not LIGHTGBM_AVAILABLE:
            raise RuntimeError("LightGBM 未安装，无法训练模型")

        lookback_val = lookback or min(60, len(price_series))
        model = LightGBMForecaster(
            lookback=lookback_val,
            use_enhanced_features=use_enhanced_features,
        )
        model.fit(price_series)

        key = self._model_key(ticker, "lightgbm")
        self.models[key] = model
        self.last_update[ticker] = datetime.now()
        self.save_model(ticker, "lightgbm")

        if register_model:
            model_id = f"lgb_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_path = self._model_path(ticker, "lightgbm")
            train_date = datetime.now().strftime("%Y-%m-%d")
            train_data_range = [
                price_series.index.min().strftime("%Y-%m-%d"),
                price_series.index.max().strftime("%Y-%m-%d"),
            ]

            metrics = {"model_type": "lightgbm", "lookback": lookback_val}

            self.registry.register_model(
                model_id=model_id,
                ticker=ticker,
                model_type="lightgbm",
                model_path=model_path,
                train_date=train_date,
                train_data_range=train_data_range,
                features_version=features_version,
                metrics=metrics,
                status="staging",
            )
            return model_id

        return ""

    # --- 针对 Random Forest 的快捷方法 ---

    def train_random_forest(
        self,
        ticker: str,
        price_series: pd.Series,
        use_enhanced_features: bool = True,
        lookback: Optional[int] = None,
        register_model: bool = True,
        features_version: str = "v1.0",
    ) -> str:
        """训练 Random Forest 模型并保存到磁盘"""
        if not SKLEARN_AVAILABLE or RandomForestRegressor is None:
            raise RuntimeError("scikit-learn 未安装，无法训练模型")

        lookback_val = lookback or min(60, len(price_series))
        model = RandomForestForecaster(
            lookback=lookback_val,
            use_enhanced_features=use_enhanced_features,
        )
        model.fit(price_series)

        key = self._model_key(ticker, "random_forest")
        self.models[key] = model
        self.last_update[ticker] = datetime.now()
        self.save_model(ticker, "random_forest")

        if register_model:
            model_id = f"rf_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_path = self._model_path(ticker, "random_forest")
            train_date = datetime.now().strftime("%Y-%m-%d")
            train_data_range = [
                price_series.index.min().strftime("%Y-%m-%d"),
                price_series.index.max().strftime("%Y-%m-%d"),
            ]

            metrics = {"model_type": "random_forest", "lookback": lookback_val}

            self.registry.register_model(
                model_id=model_id,
                ticker=ticker,
                model_type="random_forest",
                model_path=model_path,
                train_date=train_date,
                train_data_range=train_data_range,
                features_version=features_version,
                metrics=metrics,
                status="staging",
            )
            return model_id

        return ""

    # --- 针对 LSTM 的快捷方法 ---

    def train_lstm(
        self,
        ticker: str,
        price_series: pd.Series,
        sequence_length: Optional[int] = None,
        epochs: int = 50,
        register_model: bool = True,
        features_version: str = "v1.0",
    ) -> str:
        """训练 LSTM 模型并保存到磁盘"""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch 未安装，无法训练模型")

        seq_len = sequence_length or min(30, len(price_series) // 2)
        model = LSTMForecaster(
            sequence_length=seq_len,
            epochs=epochs,
        )
        model.fit(price_series)

        key = self._model_key(ticker, "lstm")
        self.models[key] = model
        self.last_update[ticker] = datetime.now()
        self.save_model(ticker, "lstm")

        if register_model:
            model_id = f"lstm_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_path = self._model_path(ticker, "lstm")
            train_date = datetime.now().strftime("%Y-%m-%d")
            train_data_range = [
                price_series.index.min().strftime("%Y-%m-%d"),
                price_series.index.max().strftime("%Y-%m-%d"),
            ]

            metrics = {"model_type": "lstm", "sequence_length": seq_len, "epochs": epochs}

            self.registry.register_model(
                model_id=model_id,
                ticker=ticker,
                model_type="lstm",
                model_path=model_path,
                train_date=train_date,
                train_data_range=train_data_range,
                features_version=features_version,
                metrics=metrics,
                status="staging",
            )
            return model_id

        return ""

    # --- 针对 GRU 的快捷方法 ---

    def train_gru(
        self,
        ticker: str,
        price_series: pd.Series,
        sequence_length: Optional[int] = None,
        epochs: int = 50,
        register_model: bool = True,
        features_version: str = "v1.0",
    ) -> str:
        """训练 GRU 模型并保存到磁盘"""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch 未安装，无法训练模型")

        seq_len = sequence_length or min(30, len(price_series) // 2)
        model = GRUForecaster(
            sequence_length=seq_len,
            epochs=epochs,
        )
        model.fit(price_series)

        key = self._model_key(ticker, "gru")
        self.models[key] = model
        self.last_update[ticker] = datetime.now()
        self.save_model(ticker, "gru")

        if register_model:
            model_id = f"gru_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_path = self._model_path(ticker, "gru")
            train_date = datetime.now().strftime("%Y-%m-%d")
            train_data_range = [
                price_series.index.min().strftime("%Y-%m-%d"),
                price_series.index.max().strftime("%Y-%m-%d"),
            ]

            metrics = {"model_type": "gru", "sequence_length": seq_len, "epochs": epochs}

            self.registry.register_model(
                model_id=model_id,
                ticker=ticker,
                model_type="gru",
                model_path=model_path,
                train_date=train_date,
                train_data_range=train_data_range,
                features_version=features_version,
                metrics=metrics,
                status="staging",
            )
            return model_id

        return ""

    # --- 针对 Prophet 的快捷方法 ---

    def train_prophet(
        self,
        ticker: str,
        price_series: pd.Series,
        register_model: bool = True,
        features_version: str = "v1.0",
    ) -> str:
        """训练 Prophet 模型（Prophet 不支持序列化到磁盘，仅注册元数据或内存缓存）"""
        if not PROPHET_AVAILABLE:
            raise RuntimeError("Prophet 未安装，无法训练模型")

        # Prophet 对短数据敏感，需要至少 2 个数据点
        if len(price_series) < 5:
             raise ValueError("数据过短，无法训练 Prophet 模型")

        model = ProphetForecaster()
        model.fit(price_series)

        key = self._model_key(ticker, "prophet")
        self.models[key] = model
        self.last_update[ticker] = datetime.now()
        # Prophet 暂不持久化到磁盘，因为 pickle 支持有限
        
        if register_model:
            model_id = f"prophet_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            # 伪造路径，因为没有实际保存
            model_path = ""
            train_date = datetime.now().strftime("%Y-%m-%d")
            train_data_range = [
                price_series.index.min().strftime("%Y-%m-%d"),
                price_series.index.max().strftime("%Y-%m-%d"),
            ]

            metrics = {"model_type": "prophet"}

            self.registry.register_model(
                model_id=model_id,
                ticker=ticker,
                model_type="prophet",
                model_path=model_path,
                train_date=train_date,
                train_data_range=train_data_range,
                features_version=features_version,
                metrics=metrics,
                status="staging",
            )
            return model_id

        return ""

    # --- 通用训练方法 ---

    def train_model(
        self,
        ticker: str,
        price_series: pd.Series,
        model_type: str = "xgboost",
        use_enhanced_features: bool = True,
        register_model: bool = True,
        features_version: str = "v1.0",
        **kwargs,
    ) -> Optional[str]:
        """
        通用模型训练方法，支持所有模型类型
        
        参数:
            ticker: 标的代码
            price_series: 价格序列
            model_type: 模型类型 ("xgboost", "lightgbm", "random_forest", "lstm", "gru")
            use_enhanced_features: 是否使用增强特征（仅适用于树模型）
            register_model: 是否注册到注册表
            features_version: 特征版本
            **kwargs: 其他模型特定参数
            
        返回:
            模型ID，失败返回None
        """
        try:
            if model_type == "xgboost":
                return self.train_xgboost(
                    ticker, price_series, use_enhanced_features, None, register_model, features_version
                )
            elif model_type == "lightgbm":
                return self.train_lightgbm(
                    ticker, price_series, use_enhanced_features, None, register_model, features_version
                )
            elif model_type == "random_forest":
                return self.train_random_forest(
                    ticker, price_series, use_enhanced_features, None, register_model, features_version
                )
            elif model_type == "lstm":
                epochs = kwargs.get("epochs", 50)
                sequence_length = kwargs.get("sequence_length", None)
                return self.train_lstm(
                    ticker, price_series, sequence_length, epochs, register_model, features_version
                )
            elif model_type == "gru":
                epochs = kwargs.get("epochs", 50)
                sequence_length = kwargs.get("sequence_length", None)
                return self.train_gru(
                    ticker, price_series, sequence_length, epochs, register_model, features_version
                )
            elif model_type == "prophet":
                return self.train_prophet(
                    ticker, price_series, register_model, features_version
                )
            else:
                raise ValueError(f"不支持的模型类型: {model_type}")
        except Exception as e:
            print(f"训练模型失败 ({ticker}, {model_type}): {e}")
            return None


if __name__ == "__main__":
    # 测试代码
    print("可用模型:", get_available_models())


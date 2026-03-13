from __future__ import annotations

from datetime import datetime
import json
import math
import os
import pickle
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

try:
    import joblib  # type: ignore[import]
    JOBLIB_AVAILABLE = True
except Exception:
    JOBLIB_AVAILABLE = False
    joblib = None

try:
    from prophet import Prophet  # type: ignore[import]
    PROPHET_AVAILABLE = True
except Exception:
    PROPHET_AVAILABLE = False
    Prophet = None

try:
    import xgboost as xgb  # type: ignore[import]
    XGBOOST_AVAILABLE = True
except Exception:
    XGBOOST_AVAILABLE = False
    xgb = None

try:
    import lightgbm as lgb  # type: ignore[import]
    LIGHTGBM_AVAILABLE = True
except Exception:
    LIGHTGBM_AVAILABLE = False
    lgb = None

try:
    import torch  # type: ignore[import]
    TORCH_AVAILABLE = True
except Exception:
    TORCH_AVAILABLE = False
    torch = None

try:
    from sklearn.ensemble import RandomForestRegressor
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False
    RandomForestRegressor = None

try:
    from statsmodels.tsa.arima.model import ARIMA
    STATSMODELS_AVAILABLE = True
except Exception:
    STATSMODELS_AVAILABLE = False
    ARIMA = None

DEFAULT_CONFIDENCE_Z = 1.96
DEFAULT_HOLD_CONFIDENCE_THRESHOLD = 0.55
DEFAULT_BASE_WEIGHTS: Dict[str, float] = {"prophet": 1.0, "xgboost": 2.0, "lightgbm": 1.5, "arima": 0.8}
AVAILABLE_MODELS = ["prophet", "xgboost", "lightgbm", "arima"]


def _normal_cdf(values: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
    arr = np.asarray(values, dtype=float)
    try:
        from scipy.stats import norm  # type: ignore[import]
        cdf = norm.cdf(arr)
    except Exception:
        cdf = 0.5 * (1.0 + np.vectorize(math.erf)(arr / np.sqrt(2.0)))
    if np.isscalar(values):
        return float(np.asarray(cdf).item())
    return cdf


def _confidence_and_signal(up_probability: float, hold_threshold: float = DEFAULT_HOLD_CONFIDENCE_THRESHOLD) -> Tuple[float, str]:
    prob = float(np.clip(up_probability, 0.0, 1.0))
    confidence = float(abs(prob - 0.5) * 2.0)
    if confidence < hold_threshold:
        return confidence, "hold"
    return confidence, "buy" if prob >= 0.5 else "sell"


def _as_series(values: Union[pd.Series, np.ndarray, List[float]]) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.astype(float)
    return pd.Series(np.asarray(values, dtype=float))


def _normalize_model_type(model_type: str) -> str:
    model_type = (model_type or "xgboost").strip().lower()
    if model_type not in {"lstm", "gru"}:
        return model_type
    if not TORCH_AVAILABLE:
        return "xgboost"
    if os.environ.get("DISABLE_HEAVY_MODELS", "").strip().lower() in ("1", "true", "yes"):
        return "xgboost"
    return model_type


def _add_distribution_columns(pred_df: pd.DataFrame, last_observed_price: float, return_sigma: float, use_log_return: bool = False) -> pd.DataFrame:
    if pred_df is None or pred_df.empty or "prediction" not in pred_df.columns:
        return pred_df
    sigma = float(max(abs(return_sigma), 1e-6))
    prev = float(max(last_observed_price, 1e-6))
    lows: List[float] = []
    highs: List[float] = []
    probs: List[float] = []
    confs: List[float] = []
    signals: List[str] = []
    for p in pred_df["prediction"].astype(float).tolist():
        if use_log_return:
            r = float(np.log(max(p, 1e-6) / prev))
        else:
            r = float(p / prev - 1.0)
        low_r = r - DEFAULT_CONFIDENCE_Z * sigma
        high_r = r + DEFAULT_CONFIDENCE_Z * sigma
        low = prev * (float(np.exp(low_r)) if use_log_return else 1.0 + low_r)
        high = prev * (float(np.exp(high_r)) if use_log_return else 1.0 + high_r)
        prob = float(_normal_cdf(r / sigma))
        conf, sig = _confidence_and_signal(prob)
        lows.append(float(low))
        highs.append(float(high))
        probs.append(prob)
        confs.append(conf)
        signals.append(sig)
        prev = float(max(p, 1e-6))
    out = pred_df.copy()
    out["lower_bound"] = lows
    out["upper_bound"] = highs
    out["up_probability"] = probs
    out["confidence"] = confs
    out["signal"] = signals
    return out


class FeatureEngineer:
    @staticmethod
    def create_price_features(price_series: pd.Series, lookback_windows: Optional[List[int]] = None) -> pd.DataFrame:
        windows = lookback_windows or [5, 10, 20, 60]
        s = _as_series(price_series)
        s.index = price_series.index
        df = pd.DataFrame(index=s.index)
        df["price"] = s
        df["return_1d"] = s.pct_change(1)
        df["return_5d"] = s.pct_change(5)
        df["return_10d"] = s.pct_change(10)
        df["return_20d"] = s.pct_change(20)
        df["log_return"] = np.log(s / s.shift(1))
        for w in windows:
            m, std = s.rolling(w).mean(), s.rolling(w).std()
            df[f"sma_{w}"] = m
            df[f"sma_ratio_{w}"] = s / m
            df[f"volatility_{w}"] = df["log_return"].rolling(w).std() * np.sqrt(252)
            df[f"high_{w}"] = s.rolling(w).max()
            df[f"low_{w}"] = s.rolling(w).min()
            df[f"range_ratio_{w}"] = (df[f"high_{w}"] - df[f"low_{w}"]) / s
            df[f"momentum_{w}"] = s / s.shift(w) - 1.0
            df[f"zscore_{w}"] = (s - m) / std.replace(0.0, np.nan)
        d = s.diff()
        gain = d.where(d > 0, 0.0).rolling(14).mean()
        loss = (-d.where(d < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0.0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))
        ema12 = s.ewm(span=12, adjust=False).mean()
        ema26 = s.ewm(span=26, adjust=False).mean()
        df["macd"] = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_histogram"] = df["macd"] - df["macd_signal"]
        bb_m = s.rolling(20).mean()
        bb_std = s.rolling(20).std()
        df["bb_middle"] = bb_m
        df["bb_upper"] = bb_m + 2.0 * bb_std
        df["bb_lower"] = bb_m - 2.0 * bb_std
        df["bb_position"] = (s - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
        if isinstance(s.index, pd.DatetimeIndex):
            df["day_of_week"] = s.index.dayofweek
            df["month"] = s.index.month
            df["quarter"] = s.index.quarter
        return df

    @staticmethod
    def add_enhanced_features(df: pd.DataFrame, price_series: pd.Series) -> pd.DataFrame:
        out = df.copy()
        s = _as_series(price_series)
        s.index = price_series.index
        high, low, prev = s.rolling(2).max(), s.rolling(2).min(), s.shift(1)
        tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
        out["atr_14"] = tr.rolling(14).mean()
        ret = s.pct_change()
        out["realized_vol_20"] = ret.rolling(20).std() * np.sqrt(252)
        out["skewness_20"] = ret.rolling(20).skew()
        out["kurtosis_20"] = ret.rolling(20).kurt()
        ema5, ema20 = s.ewm(span=5, adjust=False).mean(), s.ewm(span=20, adjust=False).mean()
        out["ema_cross_5_20"] = (ema5 - ema20) / s.replace(0.0, np.nan)
        out["ema_cross_signal"] = np.sign(out["ema_cross_5_20"]) - np.sign(out["ema_cross_5_20"].shift(1))
        return out

    @staticmethod
    def create_lag_features(df: pd.DataFrame, target_col: str, lags: List[int]) -> pd.DataFrame:
        out = df.copy()
        for lag in lags:
            out[f"{target_col}_lag_{lag}"] = out[target_col].shift(lag)
        return out

    @staticmethod
    def create_target(price_series: pd.Series, horizon: int = 1, use_log_return: bool = False) -> pd.Series:
        s = _as_series(price_series)
        s.index = price_series.index
        future = s.shift(-horizon)
        return np.log(future / s) if use_log_return else future / s - 1.0

class _TreeForecasterBase:
    def __init__(self, lookback: int = 60, use_log_return: bool = False):
        self.lookback = int(max(10, lookback))
        self.use_log_return = bool(use_log_return)
        self.model: Any = None
        self.feature_columns: Optional[List[str]] = None
        self.price_history: Optional[pd.Series] = None
        self.return_sigma: float = 0.01

    def _build_model(self) -> Any:
        raise NotImplementedError

    def fit(self, price_series: pd.Series):
        s = _as_series(price_series).dropna()
        s.index = price_series.dropna().index
        if len(s) < max(50, self.lookback + 5):
            raise ValueError("Insufficient history for training")
        feat = FeatureEngineer.add_enhanced_features(FeatureEngineer.create_price_features(s), s)
        tgt = FeatureEngineer.create_target(s, horizon=1, use_log_return=self.use_log_return)
        train_df = feat.join(tgt.rename("target")).dropna()
        X = train_df.drop(columns=["target"])
        y = train_df["target"]
        self.feature_columns = X.columns.tolist()
        self.model = self._build_model()
        self.model.fit(X, y)
        self.price_history = s.copy()
        self.return_sigma = max(float(s.pct_change().dropna().std()), 1e-4)
        return self

    def _predict_one_step_return(self, series: pd.Series) -> float:
        if self.model is None or not self.feature_columns:
            raise ValueError("Call fit() before predict()")
        feat = FeatureEngineer.add_enhanced_features(FeatureEngineer.create_price_features(series), series)
        row = feat.tail(1)[self.feature_columns].ffill().fillna(0.0)
        pred = float(np.asarray(self.model.predict(row)).ravel()[0])
        return float(np.clip(pred, -0.3, 0.3))

    def predict(self, horizon: int = 5) -> pd.DataFrame:
        if self.price_history is None:
            raise ValueError("Call fit() before predict()")
        horizon = int(max(1, horizon))
        work, prev = self.price_history.copy(), float(self.price_history.iloc[-1])
        preds: List[float] = []
        for _ in range(horizon):
            r = self._predict_one_step_return(work)
            next_price = prev * (float(np.exp(r)) if self.use_log_return else 1.0 + r)
            next_price = float(max(next_price, 1e-6))
            preds.append(next_price)
            next_idx = work.index[-1] + pd.tseries.offsets.BDay(1)
            work.loc[next_idx] = next_price
            prev = next_price
        idx = pd.bdate_range(start=self.price_history.index[-1] + pd.tseries.offsets.BDay(1), periods=horizon)
        out = pd.DataFrame({"prediction": preds}, index=idx)
        return _add_distribution_columns(out, float(self.price_history.iloc[-1]), self.return_sigma, self.use_log_return)

    def get_feature_importance(self) -> pd.Series:
        if self.model is None or not self.feature_columns:
            raise ValueError("Call fit() before get_feature_importance()")
        vals = np.asarray(self.model.feature_importances_, dtype=float) if hasattr(self.model, "feature_importances_") else np.zeros(len(self.feature_columns))
        return pd.Series(vals, index=self.feature_columns).sort_values(ascending=False)


class XGBoostForecaster(_TreeForecasterBase):
    def __init__(self, lookback: int = 60, n_estimators: int = 200, learning_rate: float = 0.05, max_depth: int = 4, random_state: int = 42, use_log_return: bool = False):
        super().__init__(lookback=lookback, use_log_return=use_log_return)
        self.n_estimators = int(n_estimators)
        self.learning_rate = float(learning_rate)
        self.max_depth = int(max_depth)
        self.random_state = int(random_state)

    def _build_model(self):
        if not XGBOOST_AVAILABLE:
            raise ImportError("xgboost is not installed")
        return xgb.XGBRegressor(objective="reg:squarederror", n_estimators=self.n_estimators, learning_rate=self.learning_rate, max_depth=self.max_depth, random_state=self.random_state, subsample=0.9, colsample_bytree=0.9)


class LightGBMForecaster(_TreeForecasterBase):
    def __init__(self, lookback: int = 60, n_estimators: int = 200, learning_rate: float = 0.05, num_leaves: int = 31, random_state: int = 42, use_log_return: bool = False):
        super().__init__(lookback=lookback, use_log_return=use_log_return)
        self.n_estimators = int(n_estimators)
        self.learning_rate = float(learning_rate)
        self.num_leaves = int(num_leaves)
        self.random_state = int(random_state)

    def _build_model(self):
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("lightgbm is not installed")
        return lgb.LGBMRegressor(n_estimators=self.n_estimators, learning_rate=self.learning_rate, num_leaves=self.num_leaves, random_state=self.random_state)


class RandomForestForecaster(_TreeForecasterBase):
    def __init__(self, lookback: int = 60, n_estimators: int = 300, max_depth: Optional[int] = None, random_state: int = 42, use_log_return: bool = False):
        super().__init__(lookback=lookback, use_log_return=use_log_return)
        self.n_estimators = int(n_estimators)
        self.max_depth = max_depth
        self.random_state = int(random_state)

    def _build_model(self):
        if not SKLEARN_AVAILABLE or RandomForestRegressor is None:
            raise ImportError("sklearn is not installed")
        return RandomForestRegressor(n_estimators=self.n_estimators, max_depth=self.max_depth, random_state=self.random_state, n_jobs=1)


class ProphetForecaster:
    def __init__(self):
        self.model: Any = None
        self.price_history: Optional[pd.Series] = None
        self.return_sigma: float = 0.01

    def fit(self, price_series: pd.Series):
        if not PROPHET_AVAILABLE:
            raise ImportError("prophet is not installed")
        s = _as_series(price_series).dropna()
        s.index = price_series.dropna().index
        if not isinstance(s.index, pd.DatetimeIndex):
            raise ValueError("Prophet requires DatetimeIndex")
        self.model = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=True)
        self.model.fit(pd.DataFrame({"ds": s.index, "y": s.values}))
        self.price_history = s
        self.return_sigma = max(float(s.pct_change().dropna().std()), 1e-4)
        return self

    def predict(self, horizon: int = 5) -> pd.DataFrame:
        if self.model is None or self.price_history is None:
            raise ValueError("Call fit() before predict()")
        future = self.model.make_future_dataframe(periods=int(max(1, horizon)), freq="B")
        fc = self.model.predict(future).tail(int(max(1, horizon)))
        out = fc[["ds", "yhat", "yhat_lower", "yhat_upper"]].rename(columns={"yhat": "prediction", "yhat_lower": "lower_bound", "yhat_upper": "upper_bound"}).set_index("ds")
        return _add_distribution_columns(out, float(self.price_history.iloc[-1]), self.return_sigma)


class ARIMAForecaster:
    def __init__(self, order: Tuple[int, int, int] = (1, 1, 1)):
        self.order = order
        self.fitted: Any = None
        self.price_history: Optional[pd.Series] = None
        self.return_sigma: float = 0.01

    def fit(self, price_series: pd.Series):
        if not STATSMODELS_AVAILABLE or ARIMA is None:
            raise ImportError("statsmodels is not installed")
        s = _as_series(price_series).dropna()
        s.index = price_series.dropna().index
        self.fitted = ARIMA(s.values, order=self.order).fit()
        self.price_history = s
        self.return_sigma = max(float(s.pct_change().dropna().std()), 1e-4)
        return self

    def predict(self, horizon: int = 5) -> pd.DataFrame:
        if self.fitted is None or self.price_history is None:
            raise ValueError("Call fit() before predict()")
        horizon = int(max(1, horizon))
        fc_obj = self.fitted.get_forecast(steps=horizon)
        mean = np.asarray(fc_obj.predicted_mean, dtype=float)
        conf = np.asarray(fc_obj.conf_int(alpha=0.05), dtype=float)
        idx = pd.bdate_range(start=self.price_history.index[-1] + pd.tseries.offsets.BDay(1), periods=horizon)
        out = pd.DataFrame({"prediction": mean, "lower_bound": conf[:, 0], "upper_bound": conf[:, 1]}, index=idx)
        return _add_distribution_columns(out, float(self.price_history.iloc[-1]), self.return_sigma)


class LSTMForecaster:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("LSTM forecaster is disabled in this runtime profile")


class GRUForecaster:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("GRU forecaster is disabled in this runtime profile")


class EnsembleForecaster:
    def __init__(self, models: Optional[Dict[str, Any]] = None, weights: Optional[Dict[str, float]] = None):
        self.models: Dict[str, Any] = models.copy() if models else {}
        self.weights = weights.copy() if weights else {k: 1.0 / max(len(self.models), 1) for k in self.models.keys()}
        self._normalize_weights()
        self.price_history: Optional[pd.Series] = None

    def _normalize_weights(self):
        if not self.weights:
            return
        s = float(sum(self.weights.values()))
        self.weights = {k: (float(v) / s if s > 0 else 1.0 / len(self.weights)) for k, v in self.weights.items()}

    def add_model(self, name: str, model: Any, weight: float = 1.0):
        self.models[name] = model
        self.weights[name] = float(weight)
        self._normalize_weights()

    def fit(self, price_series: pd.Series, holdout_size: int = 0):
        del holdout_size
        self.price_history = _as_series(price_series).dropna()
        self.price_history.index = price_series.dropna().index
        for _, m in self.models.items():
            m.fit(self.price_history)
        return self

    def predict(self, horizon: int = 5) -> pd.DataFrame:
        if not self.models:
            raise ValueError("No base model in ensemble")
        preds: Dict[str, pd.Series] = {}
        for name, m in self.models.items():
            p = m.predict(horizon)
            preds[name] = _as_series(p["prediction"])
            preds[name].index = p.index
        keys = list(preds.keys())
        w = {k: self.weights.get(k, 0.0) for k in keys}
        s = sum(w.values()) or 1.0
        w = {k: v / s for k, v in w.items()}
        idx = preds[keys[0]].index
        out = pd.DataFrame(index=idx)
        out["prediction"] = 0.0
        for k in keys:
            out[f"{k}_pred"] = preds[k].values
            out["prediction"] += preds[k].values * w[k]
        if self.price_history is not None:
            sigma = max(float(self.price_history.pct_change().dropna().std()), 1e-4)
            out = _add_distribution_columns(out, float(self.price_history.iloc[-1]), sigma)
        return out

class ModelEvaluator:
    @staticmethod
    def _expected_calibration_error(probs: Union[pd.Series, np.ndarray], outcomes: Union[pd.Series, np.ndarray], n_bins: int = 10) -> float:
        p, y = np.asarray(probs, dtype=float), np.asarray(outcomes, dtype=float)
        if p.size == 0 or y.size == 0:
            return 0.0
        p = np.clip(p, 0.0, 1.0)
        bins = np.linspace(0.0, 1.0, n_bins + 1)
        total, ece = len(p), 0.0
        for i in range(n_bins):
            mask = (p >= bins[i]) & (p < bins[i + 1] if i < n_bins - 1 else p <= bins[i + 1])
            if not mask.any():
                continue
            ece += (mask.sum() / total) * abs(float(y[mask].mean()) - float(p[mask].mean()))
        return float(ece)

    @staticmethod
    def _calc_trading_metrics(actual_prices: pd.Series, predicted_prices: pd.Series, transaction_cost: float = 0.001) -> Dict[str, float]:
        actual, predicted = _as_series(actual_prices), _as_series(predicted_prices)
        n = min(len(actual), len(predicted))
        if n < 3:
            return {"Strategy_NetReturn": 0.0, "Strategy_Sharpe": 0.0, "Strategy_MaxDrawdown": 0.0, "Strategy_Turnover": 0.0}
        actual, predicted = actual.iloc[:n].reset_index(drop=True), predicted.iloc[:n].reset_index(drop=True)
        actual_ret, pred_ret = actual.pct_change().fillna(0.0), predicted.pct_change().fillna(0.0)
        signal = np.sign(pred_ret)
        positioned = signal.shift(1).fillna(0.0)
        turnover = signal.diff().abs().fillna(signal.abs())
        costs = turnover * float(max(transaction_cost, 0.0))
        strategy_ret = positioned * actual_ret - costs
        equity = (1.0 + strategy_ret).cumprod()
        drawdown = equity / equity.cummax().replace(0.0, np.nan) - 1.0
        std = float(strategy_ret.std())
        sharpe = float(strategy_ret.mean() / std * np.sqrt(252)) if std > 0 else 0.0
        return {
            "Strategy_NetReturn": float(equity.iloc[-1] - 1.0),
            "Strategy_Sharpe": sharpe,
            "Strategy_MaxDrawdown": float(drawdown.min() if not drawdown.empty else 0.0),
            "Strategy_Turnover": float(turnover.mean()),
        }

    @staticmethod
    def calculate_metrics(actual: Union[pd.Series, np.ndarray], predicted: Union[pd.Series, np.ndarray], transaction_cost: float = 0.001) -> Dict[str, float]:
        y_true = _as_series(actual).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
        y_pred = _as_series(predicted).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
        n = min(len(y_true), len(y_pred))
        if n == 0:
            return {"MAE": 0.0, "RMSE": 0.0, "MAPE": 0.0, "SMAPE": 0.0, "Direction_Accuracy": 0.0, "ECE": 0.0, "Strategy_NetReturn": 0.0, "Strategy_Sharpe": 0.0, "Strategy_MaxDrawdown": 0.0, "Strategy_Turnover": 0.0}
        y_true, y_pred = y_true.iloc[:n].reset_index(drop=True), y_pred.iloc[:n].reset_index(drop=True)
        err = y_true - y_pred
        mae = float(np.abs(err).mean())
        rmse = float(np.sqrt(np.mean(np.square(err))))
        mape = float((np.abs(err) / y_true.replace(0.0, np.nan)).mean() * 100.0)
        smape = float((2.0 * np.abs(y_pred - y_true) / (np.abs(y_true) + np.abs(y_pred)).replace(0.0, np.nan)).mean() * 100.0)
        true_ret, pred_ret = y_true.pct_change().fillna(0.0), y_pred.pct_change().fillna(0.0)
        direction = float((np.sign(true_ret) == np.sign(pred_ret)).mean() * 100.0)
        probs, outcomes = np.clip(pred_ret * 5.0 + 0.5, 0.0, 1.0), (true_ret > 0).astype(float)
        out = {"MAE": mae, "RMSE": rmse, "MAPE": 0.0 if np.isnan(mape) else mape, "SMAPE": 0.0 if np.isnan(smape) else smape, "Direction_Accuracy": direction, "ECE": ModelEvaluator._expected_calibration_error(probs, outcomes)}
        out.update(ModelEvaluator._calc_trading_metrics(y_true, y_pred, transaction_cost=transaction_cost))
        return out

    @staticmethod
    def walk_forward_validation(price_series: pd.Series, model_class: Any, n_splits: int = 5, test_size: int = 20, purge_days: int = 5, embargo_days: int = 2, transaction_cost: float = 0.001, model_kwargs: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        s = _as_series(price_series).dropna()
        s.index = price_series.dropna().index
        if len(s) < max(80, test_size * (n_splits + 1)):
            return pd.DataFrame()
        rows: List[Dict[str, Any]] = []
        kwargs = model_kwargs or {}
        for split in range(n_splits):
            valid_end = len(s) - (n_splits - split - 1) * test_size
            valid_start = valid_end - test_size
            train_end = valid_start - max(purge_days, 0)
            if train_end <= 40:
                continue
            train, valid = s.iloc[:train_end], s.iloc[valid_start:valid_end]
            if len(valid) < 5:
                continue
            try:
                model = model_class(**kwargs)
                model.fit(train)
                pred = model.predict(len(valid))
                y_pred = _as_series(pred["prediction"]).reset_index(drop=True)
                y_true = valid.reset_index(drop=True).iloc[: len(y_pred)]
                y_pred = y_pred.iloc[: len(y_true)]
                m = ModelEvaluator.calculate_metrics(y_true, y_pred, transaction_cost=transaction_cost)
                m.update({"split": split, "train_end": str(train.index[-1])[:10], "valid_start": str(valid.index[0])[:10], "valid_end": str(valid.index[-1])[:10], "purge_days": float(max(purge_days, 0)), "embargo_days": float(max(embargo_days, 0)), "regime": detect_market_state(train)})
                rows.append(m)
            except Exception:
                continue
        return pd.DataFrame(rows)


class ModelRegistry:
    def __init__(self, registry_path: str = "models/registry.json"):
        self.registry_path = registry_path
        self.models: List[Dict[str, Any]] = []
        self.production_models: Dict[str, str] = {}
        self._ensure_loaded()

    def _ensure_loaded(self):
        os.makedirs(os.path.dirname(self.registry_path) or ".", exist_ok=True)
        if not os.path.exists(self.registry_path):
            self._save_registry()
            return
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.models = payload.get("models", [])
            self.production_models = payload.get("production_models", {})
        except Exception:
            self.models, self.production_models = [], {}
            self._save_registry()

    def _save_registry(self):
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump({"models": self.models, "production_models": self.production_models}, f, ensure_ascii=False, indent=2)

    def _make_model_id(self, ticker: str, model_type: str) -> str:
        return f"{ticker}_{model_type}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    def register_model(self, ticker: str, model_type: str, train_data_range: Dict[str, Any], features_version: Optional[str] = None, metrics: Optional[Dict[str, Any]] = None, status: str = "staging", model_path: str = "", model_id: Optional[str] = None) -> str:
        model_id = model_id or self._make_model_id(ticker, model_type)
        entry = {"model_id": model_id, "ticker": ticker, "model_type": model_type, "train_date": datetime.now().strftime("%Y-%m-%d"), "train_data_range": train_data_range, "features_version": features_version or "default", "metrics": metrics or {}, "status": status, "model_path": model_path, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.models = [m for m in self.models if not (m.get("ticker") == ticker and m.get("status") == "staging")]
        self.models.append(entry)
        self._save_registry()
        return model_id

    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        return next((m for m in self.models if m.get("model_id") == model_id), None)

    def get_production_model(self, ticker: str) -> Optional[str]:
        return self.production_models.get(ticker)

    def set_production_model(self, ticker: str, model_id: str) -> bool:
        m = self.get_model_info(model_id)
        if not m or m.get("ticker") != ticker:
            return False
        for x in self.models:
            if x.get("ticker") == ticker and x.get("status") == "production":
                x["status"] = "archived"
        m["status"] = "production"
        self.production_models[ticker] = model_id
        self._save_registry()
        return True

    def update_model_metrics(self, model_id: str, metrics: Dict[str, Any]) -> bool:
        m = self.get_model_info(model_id)
        if not m:
            return False
        cur = m.get("metrics") or {}
        cur.update(metrics)
        m["metrics"] = cur
        self._save_registry()
        return True

    def list_model_history(self, ticker: str) -> List[Dict[str, Any]]:
        out = [m for m in self.models if m.get("ticker") == ticker]
        out.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return out

    def list_production_models(self) -> Dict[str, str]:
        return self.production_models.copy()


class ModelCache:
    def __init__(self, max_size: int = 50):
        self.max_size = max(1, max_size)
        self.cache: Dict[str, Any] = {}
        self.access_time: Dict[str, datetime] = {}

    def get(self, model_id: str) -> Optional[Any]:
        obj = self.cache.get(model_id)
        if obj is not None:
            self.access_time[model_id] = datetime.now()
        return obj

    def put(self, model_id: str, obj: Any):
        if len(self.cache) >= self.max_size and model_id not in self.cache:
            old = min(self.access_time, key=self.access_time.get)
            self.cache.pop(old, None)
            self.access_time.pop(old, None)
        self.cache[model_id] = obj
        self.access_time[model_id] = datetime.now()


class ModelManager:
    def __init__(self, model_dir: str = "models/"):
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        self.registry = ModelRegistry(os.path.join(self.model_dir, "registry.json"))
        self.cache = ModelCache()

    def _build_model(self, model_type: str, kwargs: Dict[str, Any]) -> Any:
        mt = _normalize_model_type(model_type)
        if mt == "xgboost":
            return XGBoostForecaster(**kwargs)
        if mt == "lightgbm":
            return LightGBMForecaster(**kwargs)
        if mt == "random_forest":
            return RandomForestForecaster(**kwargs)
        if mt == "prophet":
            return ProphetForecaster()
        if mt == "arima":
            return ARIMAForecaster()
        if mt == "ensemble":
            return EnsembleForecaster()
        raise ValueError(f"Unsupported model type: {mt}")

    def _save_model(self, model_path: str, model: Any):
        if JOBLIB_AVAILABLE and joblib is not None:
            joblib.dump(model, model_path)
        else:
            with open(model_path, "wb") as f:
                pickle.dump(model, f)

    def _load_model(self, model_path: str) -> Any:
        if JOBLIB_AVAILABLE and joblib is not None:
            return joblib.load(model_path)
        with open(model_path, "rb") as f:
            return pickle.load(f)

    def train_model(self, ticker: str, price_series: pd.Series, model_type: str = "xgboost", use_enhanced_features: bool = True, register_model: bool = True, features_version: Optional[str] = None, **kwargs) -> Optional[str]:
        del use_enhanced_features
        mt = _normalize_model_type(model_type)
        model = self._build_model(mt, kwargs)
        model.fit(price_series)
        train_data = {"start": str(price_series.index[0])[:10], "end": str(price_series.index[-1])[:10], "rows": int(len(price_series))}
        metrics: Dict[str, Any] = {}
        holdout = min(20, max(5, len(price_series) // 6))
        if len(price_series) > holdout + 20:
            valid = price_series.iloc[-holdout:]
            pred = model.predict(holdout)
            metrics = ModelEvaluator.calculate_metrics(valid.reset_index(drop=True), pred["prediction"].reset_index(drop=True))
        model_id = self.registry._make_model_id(ticker, mt)
        path = os.path.join(self.model_dir, f"{model_id}.joblib")
        self._save_model(path, model)
        self.cache.put(model_id, model)
        if register_model:
            self.registry.register_model(ticker=ticker, model_type=mt, train_data_range=train_data, features_version=features_version, metrics=metrics, status="staging", model_path=path, model_id=model_id)
        return model_id

    def load_model_by_id(self, model_id: str) -> Optional[Any]:
        cached = self.cache.get(model_id)
        if cached is not None:
            return cached
        info = self.registry.get_model_info(model_id)
        if not info:
            return None
        path = info.get("model_path")
        if not path or not os.path.exists(path):
            return None
        model = self._load_model(path)
        self.cache.put(model_id, model)
        return model

    def get_xgboost_model(self, ticker: str, price_series: pd.Series, max_age_hours: int = 24) -> Optional[Any]:
        prod_id = self.registry.get_production_model(ticker)
        if prod_id:
            info = self.registry.get_model_info(prod_id)
            if info and info.get("model_type") == "xgboost":
                path = info.get("model_path")
                if path and os.path.exists(path):
                    age_h = (datetime.now().timestamp() - os.path.getmtime(path)) / 3600.0
                    if age_h <= max_age_hours:
                        return self.load_model_by_id(prod_id)
        try:
            m = XGBoostForecaster(lookback=min(60, len(price_series))).fit(price_series)
            return m
        except Exception:
            return None

def detect_market_state(price_series: pd.Series, window: int = 20) -> str:
    s = _as_series(price_series).dropna()
    if len(s) < window + 10:
        return "trend"
    ret = s.pct_change().dropna()
    if ret.empty:
        return "trend"
    vol = float(ret.tail(window).std() * np.sqrt(252) * 100.0)
    trend_strength = float(abs((1.0 + ret.tail(window)).prod() - 1.0) * 100.0)
    if vol > 25.0:
        return "high_volatility"
    if trend_strength > 5.0:
        return "trend"
    return "range"


def _load_ticker_price_series(ticker: str, days: int = 365 * 2) -> pd.Series:
    from .data_service import load_price_data
    from .data_store import load_local_price_history
    try:
        df = load_price_data([ticker], days=days)
        if isinstance(df, pd.DataFrame) and not df.empty and ticker in df.columns:
            return df[ticker].dropna()
    except Exception:
        pass
    local = load_local_price_history(ticker)
    if local is None or local.empty:
        raise ValueError(f"Cannot load historical prices for {ticker}")
    return local.dropna()


def _format_forecast_result(ticker: str, model_name: str, horizon: int, pred_df: pd.DataFrame, regime: Optional[str] = None) -> Dict[str, Any]:
    preds: List[Dict[str, Any]] = []
    for idx, row in pred_df.iterrows():
        e: Dict[str, Any] = {"date": str(idx)[:10], "price": round(float(row.get("prediction", np.nan)), 6)}
        if "lower_bound" in pred_df.columns:
            e["lower"] = round(float(row.get("lower_bound", np.nan)), 6)
        if "upper_bound" in pred_df.columns:
            e["upper"] = round(float(row.get("upper_bound", np.nan)), 6)
        if "up_probability" in pred_df.columns:
            e["up_probability"] = round(float(row.get("up_probability", np.nan)), 6)
        if "confidence" in pred_df.columns:
            e["confidence"] = round(float(row.get("confidence", np.nan)), 6)
        if "signal" in pred_df.columns:
            e["signal"] = str(row.get("signal"))
        preds.append(e)
    out: Dict[str, Any] = {"ticker": ticker, "model": model_name, "horizon": int(horizon), "predictions": preds}
    if regime is not None:
        out["regime"] = regime
    return out


def run_forecast(ticker: str, horizon: int = 30, model_type: str = "prophet") -> Dict[str, Any]:
    mt = _normalize_model_type(model_type)
    s = _load_ticker_price_series(ticker)
    regime = detect_market_state(s)
    if mt == "auto":
        if regime == "high_volatility":
            mt, horizon = "ensemble", min(horizon, 7)
        elif regime == "range" and STATSMODELS_AVAILABLE:
            mt = "arima"
        else:
            mt = "xgboost"
    if mt == "prophet":
        return _format_forecast_result(ticker, "Prophet", horizon, ProphetForecaster().fit(s).predict(horizon), regime)
    if mt == "xgboost":
        return _format_forecast_result(ticker, "XGBoost", horizon, XGBoostForecaster(lookback=min(60, len(s))).fit(s).predict(horizon), regime)
    if mt == "lightgbm":
        return _format_forecast_result(ticker, "LightGBM", horizon, LightGBMForecaster(lookback=min(60, len(s))).fit(s).predict(horizon), regime)
    if mt == "random_forest":
        return _format_forecast_result(ticker, "RandomForest", horizon, RandomForestForecaster(lookback=min(60, len(s))).fit(s).predict(horizon), regime)
    if mt == "arima":
        return _format_forecast_result(ticker, "ARIMA", horizon, ARIMAForecaster().fit(s).predict(horizon), regime)
    if mt == "ensemble":
        models: Dict[str, Any] = {}
        if XGBOOST_AVAILABLE:
            models["xgboost"] = XGBoostForecaster(lookback=min(60, len(s)))
        if LIGHTGBM_AVAILABLE:
            models["lightgbm"] = LightGBMForecaster(lookback=min(60, len(s)))
        if PROPHET_AVAILABLE:
            models["prophet"] = ProphetForecaster()
        if STATSMODELS_AVAILABLE:
            models["arima"] = ARIMAForecaster()
        if not models:
            raise ValueError("No base model is available for ensemble")
        return _format_forecast_result(ticker, "Ensemble", horizon, EnsembleForecaster(models=models, weights=DEFAULT_BASE_WEIGHTS).fit(s).predict(horizon), regime)
    raise ValueError("Unsupported model type")


def advanced_price_forecast(price_df: pd.DataFrame, horizon: int = 5, model_type: str = "xgboost", return_confidence: bool = False, use_enhanced_features: bool = True) -> Union[pd.DataFrame, Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    del use_enhanced_features
    if price_df is None or price_df.empty:
        raise ValueError("price_df is empty; cannot run advanced forecast")
    mt = _normalize_model_type(model_type)
    results: Dict[str, List[float]] = {}
    lower: Dict[str, List[float]] = {}
    upper: Dict[str, List[float]] = {}
    idx: Optional[pd.Index] = None
    for ticker in price_df.columns:
        s = price_df[ticker].dropna()
        if s.empty:
            continue
        effective = mt
        if mt == "auto":
            rg = detect_market_state(s)
            effective = "ensemble" if rg == "high_volatility" else ("arima" if (rg == "range" and STATSMODELS_AVAILABLE) else "xgboost")
        try:
            r = run_forecast(ticker=ticker, horizon=horizon, model_type=effective)
            rows = r.get("predictions", [])
            results[ticker] = [float(x.get("price", np.nan)) for x in rows]
            lower[ticker] = [float(x.get("lower", np.nan)) for x in rows]
            upper[ticker] = [float(x.get("upper", np.nan)) for x in rows]
            if idx is None:
                idx = pd.to_datetime([x.get("date") for x in rows])
        except Exception:
            base = float(s.tail(min(20, len(s))).mean())
            vals = [base for _ in range(horizon)]
            results[ticker], lower[ticker], upper[ticker] = vals, [v * 0.98 for v in vals], [v * 1.02 for v in vals]
            if idx is None:
                idx = pd.bdate_range(start=s.index[-1] + pd.tseries.offsets.BDay(1), periods=horizon)
    index = idx if idx is not None else pd.RangeIndex(0, horizon)
    forecast_df = pd.DataFrame(results, index=index)
    if not return_confidence:
        return forecast_df
    return forecast_df, pd.DataFrame(lower, index=index), pd.DataFrame(upper, index=index)


def quick_predict(ticker: str, horizon: int = 5, model_type: str = "xgboost", use_production_model: bool = True, save_signal: bool = True, lookback_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
    from .data_store import load_local_price_history
    from .signal_store import get_signal_store
    mt = _normalize_model_type(model_type)
    manager = ModelManager()
    registry = manager.registry
    model, model_id = None, None
    if lookback_days is not None:
        use_production_model = False
    if use_production_model:
        model_id = registry.get_production_model(ticker)
        if model_id:
            info = registry.get_model_info(model_id)
            if info and _normalize_model_type(info.get("model_type", "")) == mt:
                model = manager.load_model_by_id(model_id)
    series = load_local_price_history(ticker)
    if series is None or series.empty:
        return None
    if lookback_days is not None:
        series = series.tail(int(max(lookback_days, 10)))
    if len(series) < 10:
        return None
    if model is None:
        model_id = manager.train_model(ticker=ticker, price_series=series, model_type=mt, register_model=True, features_version="runtime", lookback=min(60, len(series)))
        if not model_id:
            return None
        model = manager.load_model_by_id(model_id)
    if model is None:
        return None
    pred = model.predict(int(max(1, horizon)))
    if pred is None or pred.empty:
        return None
    metrics: Dict[str, Any] = {}
    eval_h = min(len(series) // 4, 20)
    if eval_h >= 5:
        hold = series.tail(eval_h)
        try:
            metrics = ModelEvaluator.calculate_metrics(hold.reset_index(drop=True), model.predict(eval_h)["prediction"].reset_index(drop=True))
        except Exception:
            metrics = {}
    if save_signal:
        try:
            first = pred.iloc[0]
            last_price, pred_price = float(series.iloc[-1]), float(first["prediction"])
            pred_ret = (pred_price - last_price) / max(last_price, 1e-6)
            if "up_probability" in pred.columns and "confidence" in pred.columns and "signal" in pred.columns:
                up_prob, confidence, signal = float(first["up_probability"]), float(first["confidence"]), str(first["signal"])
                direction = 1 if up_prob >= 0.5 else -1
                if signal == "hold":
                    direction = 0
            else:
                direction = 1 if pred_ret > 0.01 else (-1 if pred_ret < -0.01 else 0)
                confidence = float(min(abs(pred_ret) * 10.0, 1.0))
                signal = "buy" if direction > 0 else ("sell" if direction < 0 else "hold")
            get_signal_store().save_signal(ticker=ticker, prediction=float(pred_ret), direction=direction, confidence=confidence, signal=signal, model_id=model_id or "unknown", status="pending")
        except Exception:
            pass
    return {"ticker": ticker, "model_id": model_id, "prediction": pred, "metrics": metrics, "regime": detect_market_state(series)}


def run_optuna_xgboost_tuning(price_series: pd.Series, n_trials: int = 30) -> Dict[str, Any]:
    try:
        import optuna  # type: ignore[import]
    except Exception:
        return {}
    if not XGBOOST_AVAILABLE:
        return {}
    s = _as_series(price_series).dropna()
    if len(s) < 80:
        return {}
    feat = FeatureEngineer.add_enhanced_features(FeatureEngineer.create_price_features(s), s)
    target = FeatureEngineer.create_target(s, horizon=1)
    train_df = feat.join(target.rename("target")).dropna()
    if len(train_df) < 50:
        return {}
    X, y = train_df.drop(columns=["target"]), train_df["target"]
    split = int(len(train_df) * 0.8)
    X_train, X_valid, y_train, y_valid = X.iloc[:split], X.iloc[split:], y.iloc[:split], y.iloc[split:]

    def objective(trial: Any) -> float:
        params = {"n_estimators": trial.suggest_int("n_estimators", 80, 300), "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True), "max_depth": trial.suggest_int("max_depth", 2, 8), "subsample": trial.suggest_float("subsample", 0.6, 1.0), "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0)}
        model = xgb.XGBRegressor(objective="reg:squarederror", random_state=42, **params)
        model.fit(X_train, y_train)
        pred = model.predict(X_valid)
        return float(np.abs(np.asarray(y_valid) - pred).mean())

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=int(max(1, n_trials)), show_progress_bar=False)
    return dict(study.best_params)


def get_available_models() -> Dict[str, bool]:
    return {"Prophet": PROPHET_AVAILABLE, "XGBoost": XGBOOST_AVAILABLE, "LightGBM": LIGHTGBM_AVAILABLE, "ARIMA": STATSMODELS_AVAILABLE, "Random Forest": SKLEARN_AVAILABLE, "LSTM": TORCH_AVAILABLE, "GRU": TORCH_AVAILABLE, "Sklearn": SKLEARN_AVAILABLE}


__all__ = [
    "FeatureEngineer", "ModelEvaluator", "XGBoostForecaster", "LightGBMForecaster", "RandomForestForecaster", "ProphetForecaster", "ARIMAForecaster", "LSTMForecaster", "GRUForecaster", "EnsembleForecaster", "ModelRegistry", "ModelManager", "detect_market_state", "run_forecast", "quick_predict", "advanced_price_forecast", "run_optuna_xgboost_tuning", "get_available_models", "XGBOOST_AVAILABLE", "LIGHTGBM_AVAILABLE", "SKLEARN_AVAILABLE", "TORCH_AVAILABLE",
]

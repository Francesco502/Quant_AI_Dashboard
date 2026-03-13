from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from core.advanced_forecasting import (
        ARIMAForecaster,
        LightGBMForecaster,
        ModelEvaluator,
        ProphetForecaster,
        XGBoostForecaster,
    )
    ADVANCED_FORECASTING_AVAILABLE = True
except Exception:
    ADVANCED_FORECASTING_AVAILABLE = False
    ARIMAForecaster = None
    LightGBMForecaster = None
    ModelEvaluator = None
    ProphetForecaster = None
    XGBoostForecaster = None

DEFAULT_BASE_WEIGHTS: Dict[str, float] = {
    "prophet": 1.0,
    "xgboost": 2.0,
    "lightgbm": 1.5,
    "arima": 0.8,
}
AVAILABLE_MODELS = ["prophet", "xgboost", "lightgbm", "arima"]


class WeightedEnsemble:
    def __init__(
        self,
        models: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        base_weights: Optional[Dict[str, float]] = None,
    ):
        self.base_weights = dict(base_weights or DEFAULT_BASE_WEIGHTS)
        self.model_names = [self._normalize_model_name(m) for m in (models or AVAILABLE_MODELS)]
        self.weights: Dict[str, float] = dict(weights or {})
        if not self.weights:
            self._init_weights()
        self._normalize_weights()

        self._model_instances: Dict[str, Any] = {}
        self.trained_models: Dict[str, Any] = {}
        self.prediction_history: List[Dict[str, Any]] = []
        self.fitted = False
        self._prepare_models()

    def _normalize_model_name(self, name: str) -> str:
        return str(name).strip().lower()

    def _init_weights(self):
        self.weights = {m: float(self.base_weights.get(m, 1.0)) for m in self.model_names}

    def _normalize_weights(self):
        if not self.weights:
            return
        total = float(sum(self.weights.values()))
        if total <= 0:
            n = len(self.weights)
            self.weights = {k: 1.0 / n for k in self.weights}
            return
        self.weights = {k: float(v) / total for k, v in self.weights.items()}

    def _prepare_models(self):
        if not ADVANCED_FORECASTING_AVAILABLE:
            return
        for name in list(self.model_names):
            if name in self._model_instances:
                continue
            if name == "prophet" and ProphetForecaster is not None:
                self._model_instances[name] = ProphetForecaster()
            elif name == "xgboost" and XGBoostForecaster is not None:
                self._model_instances[name] = XGBoostForecaster(lookback=60)
            elif name == "lightgbm" and LightGBMForecaster is not None:
                self._model_instances[name] = LightGBMForecaster(lookback=60)
            elif name == "arima" and ARIMAForecaster is not None:
                self._model_instances[name] = ARIMAForecaster()

    def add_model(self, name: str, weight: float = 1.0, model_instance: Any = None):
        normalized = self._normalize_model_name(name)
        if normalized not in self.model_names:
            self.model_names.append(normalized)
        if model_instance is not None:
            self._model_instances[normalized] = model_instance
        self.weights[normalized] = float(weight)
        self._normalize_weights()

    def remove_model(self, name: str):
        normalized = self._normalize_model_name(name)
        if normalized in self.model_names:
            self.model_names.remove(normalized)
        self.weights.pop(normalized, None)
        self._model_instances.pop(normalized, None)
        self.trained_models.pop(normalized, None)
        if self.weights:
            self._normalize_weights()

    def fit(self, price_series: pd.Series, holdout_size: int = 0, fit_params: Optional[Dict[str, Any]] = None) -> "WeightedEnsemble":
        del holdout_size, fit_params
        if len(price_series) < 30:
            raise ValueError("insufficient training data")
        self._prepare_models()
        self.trained_models = {}
        for name in list(self.model_names):
            model = self._model_instances.get(name)
            if model is None:
                continue
            try:
                model.fit(price_series)
                self.trained_models[name] = model
            except Exception:
                continue
        self.fitted = bool(self.trained_models)
        if not self.fitted:
            raise ValueError("all models failed during ensemble fit")
        self.weights = {k: self.weights.get(k, 0.0) for k in self.trained_models.keys()}
        self._normalize_weights()
        return self

    def predict(self, horizon: int = 5, return_confidence: bool = True) -> pd.DataFrame:
        del return_confidence
        if not self.fitted:
            raise ValueError("call fit() before predict()")
        model_preds: Dict[str, pd.Series] = {}
        for name, model in self.trained_models.items():
            p = model.predict(horizon)
            if "prediction" in p.columns:
                model_preds[name] = p["prediction"]
            elif "yhat" in p.columns:
                model_preds[name] = p["yhat"]
        if not model_preds:
            raise ValueError("all models failed during ensemble predict")
        df = pd.DataFrame(model_preds)
        w = {k: self.weights.get(k, 0.0) for k in df.columns}
        total = sum(w.values()) or 1.0
        w = {k: v / total for k, v in w.items()}
        out = pd.DataFrame(index=df.index)
        out["prediction"] = sum(df[c] * w.get(c, 1.0 / len(df.columns)) for c in df.columns)
        out["std"] = df.std(axis=1)
        for c in df.columns:
            out[f"{c}_pred"] = df[c]
        self.prediction_history.append({"timestamp": datetime.now(), "horizon": horizon, "weights": dict(w), "predictions": out.copy()})
        return out

    def get_weights(self) -> Dict[str, float]:
        return dict(self.weights)

    def get_model_performance(self) -> Dict[str, Any]:
        if not self.prediction_history:
            return {}
        return {"weights": dict(self.prediction_history[-1]["weights"])}

class EnsembleForecaster:
    def __init__(self, models: Optional[Dict[str, Any]] = None, weights: Optional[Dict[str, float]] = None):
        self.models = dict(models or {})
        self.weights = dict(weights or {})
        self._ensemble: Optional[WeightedEnsemble] = None

    def _normalize_weights(self):
        if not self.weights:
            return
        s = sum(self.weights.values()) or 1.0
        self.weights = {k: float(v) / s for k, v in self.weights.items()}

    def add_model(self, name: str, model: Any, weight: float = 1.0):
        self.models[name] = model
        self.weights[name] = float(weight)
        self._normalize_weights()
        if self._ensemble is not None:
            self._ensemble.add_model(name, weight, model)

    def fit(self, price_series: pd.Series, holdout_size: int = 0) -> "EnsembleForecaster":
        model_names = list(self.models.keys()) if self.models else None
        self._ensemble = WeightedEnsemble(models=model_names, weights=self.weights)
        for name, model in self.models.items():
            self._ensemble.add_model(name, self.weights.get(name, 1.0), model)
        self._ensemble.fit(price_series, holdout_size=holdout_size)
        return self

    def predict(self, horizon: int = 5) -> pd.DataFrame:
        if self._ensemble is None:
            raise ValueError("call fit() before predict()")
        return self._ensemble.predict(horizon=horizon)

    def get_weights(self) -> Dict[str, float]:
        if self._ensemble is None:
            return dict(self.weights)
        return self._ensemble.get_weights()


def create_ensemble(models: Optional[List[str]] = None, weights: Optional[Dict[str, float]] = None, base_weights: Optional[Dict[str, float]] = None) -> WeightedEnsemble:
    return WeightedEnsemble(models=models, weights=weights, base_weights=base_weights)


def ensemble_predict(predictions: Dict[str, pd.DataFrame], weights: Dict[str, float], return_confidence: bool = True) -> pd.DataFrame:
    if not predictions:
        raise ValueError("predictions 不能为空")

    # collect prediction vectors
    pred_series: Dict[str, pd.Series] = {}
    lower_series: Dict[str, pd.Series] = {}
    upper_series: Dict[str, pd.Series] = {}

    for name, df in predictions.items():
        if "prediction" in df.columns:
            pred_series[name] = df["prediction"]
        elif "yhat" in df.columns:
            pred_series[name] = df["yhat"]
        else:
            continue

        if "lower_bound" in df.columns:
            lower_series[name] = df["lower_bound"]
        elif "yhat_lower" in df.columns:
            lower_series[name] = df["yhat_lower"]

        if "upper_bound" in df.columns:
            upper_series[name] = df["upper_bound"]
        elif "yhat_upper" in df.columns:
            upper_series[name] = df["yhat_upper"]

    if not pred_series:
        raise ValueError("no valid prediction column found")

    pred_df = pd.DataFrame(pred_series)

    if not weights:
        w = {k: 1.0 / len(pred_df.columns) for k in pred_df.columns}
    else:
        w = {k: float(weights.get(k, 0.0)) for k in pred_df.columns}
        s = sum(w.values()) or 1.0
        w = {k: v / s for k, v in w.items()}

    out = pd.DataFrame(index=pred_df.index)
    out["prediction"] = sum(pred_df[c] * w.get(c, 1.0 / len(pred_df.columns)) for c in pred_df.columns)
    out["std"] = pred_df.std(axis=1)

    if return_confidence and lower_series:
        low_df = pd.DataFrame(lower_series).reindex(columns=pred_df.columns)
        out["lower_bound"] = sum(low_df[c].fillna(pred_df[c]) * w.get(c, 0.0) for c in low_df.columns)
    if return_confidence and upper_series:
        up_df = pd.DataFrame(upper_series).reindex(columns=pred_df.columns)
        out["upper_bound"] = sum(up_df[c].fillna(pred_df[c]) * w.get(c, 0.0) for c in up_df.columns)

    return out

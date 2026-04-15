"""
Offline training pipeline for model retraining, evaluation, and prediction generation.

Responsibilities:
- Batch-train models for a ticker universe
- Evaluate candidates, promote better models, and generate prediction signals
"""

from __future__ import annotations

import gc
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .advanced_forecasting import (
    ModelManager,
    ModelRegistry,
    XGBoostForecaster,
    LightGBMForecaster,
    RandomForestForecaster,
    LSTMForecaster,
    GRUForecaster,
    ModelEvaluator,
    run_optuna_xgboost_tuning,
    XGBOOST_AVAILABLE,
    LIGHTGBM_AVAILABLE,
    SKLEARN_AVAILABLE,
    TORCH_AVAILABLE,
)
from .feature_store import get_feature_store
from .signal_store import get_signal_store
from .data_store import load_local_price_history

logger = logging.getLogger(__name__)


class TrainingPipeline:
    """Offline training pipeline for model retraining and promotion."""

    def __init__(
        self,
        model_dir: str = "models/",
        min_train_days: int = 60,
        retrain_interval_days: int = 7,
        min_improvement_threshold: float = 0.02,
    ):
        """Initialize the training pipeline.

        Args:
            model_dir: Directory used to store trained models.
            min_train_days: Minimum number of days required for training.
            retrain_interval_days: Minimum interval between retraining runs.
            min_improvement_threshold: Minimum score improvement required for promotion.
        """
        self.model_manager = ModelManager(model_dir=model_dir)
        self.registry = self.model_manager.registry
        self.feature_store = get_feature_store()
        self.signal_store = get_signal_store()
        self.min_train_days = min_train_days
        self.retrain_interval_days = retrain_interval_days
        self.min_improvement_threshold = min_improvement_threshold
        self.shadow_required_wins = int(os.environ.get("MODEL_SHADOW_REQUIRED_WINS", "4"))
        self.shadow_score_margin = float(os.environ.get("MODEL_SHADOW_MARGIN", "0.01"))

    def should_retrain(self, ticker: str) -> bool:
        """
        Return whether the ticker should be retrained now.
        鍙傛暟:
            ticker: 鏍囩殑浠ｇ爜

        杩斿洖:
            Whether retraining should run for the ticker.
        """
        # 妫€鏌ユ槸鍚︽湁鐢熶骇妯″瀷
        prod_model_id = self.registry.get_production_model(ticker)
        if not prod_model_id:
            return True

        # Check production model metadata before retraining decision.
        model_info = self.registry.get_model_info(prod_model_id)
        if not model_info:
            return True

        train_date_str = model_info.get("train_date")
        if train_date_str:
            train_date = datetime.strptime(train_date_str, "%Y-%m-%d")
            days_since_train = (datetime.now() - train_date).days
            if days_since_train >= self.retrain_interval_days:
                return True

        return False

    def train_model(
        self,
        ticker: str,
        price_series: Optional[pd.Series] = None,
        model_type: str = "xgboost",
        use_enhanced_features: bool = True,
        hyperparams: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Train one candidate model for the target ticker.
        鍙傛暟:
            ticker: 鏍囩殑浠ｇ爜
            price_series: Optional price history. If omitted, local history is loaded.
            model_type: Model family to train (xgboost, lightgbm, random_forest, lstm, gru).
            use_enhanced_features: Whether to use enhanced features for tree models.
            hyperparams: Optional tuned hyperparameters.
            妯″瀷ID锛屽け璐ヨ繑鍥濶one
        """
        # Allow disabling heavy sequence models in low-resource runtime.
        _disable_heavy = os.environ.get("DISABLE_HEAVY_MODELS", "").strip().lower() in ("1", "true", "yes")
        _torch_ok = TORCH_AVAILABLE and not _disable_heavy
        model_available = {
            "xgboost": XGBOOST_AVAILABLE,
            "lightgbm": LIGHTGBM_AVAILABLE,
            "random_forest": SKLEARN_AVAILABLE,
            "lstm": _torch_ok,
            "gru": _torch_ok,
        }

        if not model_available.get(model_type, False):
            logger.warning(f"{model_type} is not available, skipping training for {ticker}")
            return None

        # 鍔犺浇浠锋牸鏁版嵁
        if price_series is None:
            price_series = load_local_price_history(ticker)

        if price_series is None or price_series.empty:
            logger.warning(f"鏃犳硶鍔犺浇浠锋牸鏁版嵁: {ticker}")
            return None

        if len(price_series) < self.min_train_days:
            logger.warning(f"Insufficient data for {ticker}: need at least {self.min_train_days} days, got {len(price_series)}")
            return None

        try:
            # Resolve the feature-version snapshot used for this training run.
            features_version = self.feature_store.get_feature_version()
            
            # Prepare train_model keyword arguments.
            train_kwargs = {
                "ticker": ticker,
                "price_series": price_series,
                "model_type": model_type,
                "use_enhanced_features": use_enhanced_features if model_type in ["xgboost", "lightgbm", "random_forest"] else False,
                "register_model": True,
                "features_version": features_version,
            }
            
            # 娣诲姞妯″瀷鐗瑰畾鍙傛暟
            if hyperparams:
                train_kwargs.update(hyperparams)
            elif model_type in ["lstm", "gru"]:
                train_kwargs["epochs"] = 50
                train_kwargs["sequence_length"] = min(30, len(price_series) // 2)
            
            model_id = self.model_manager.train_model(**train_kwargs)

            if model_id:
                logger.info(f"Model trained successfully: {ticker} ({model_type}) -> {model_id}")
                # After training, run Walk-Forward evaluation and persist metrics into the registry.
                try:
                    metrics = self.evaluate_model(ticker, model_id, price_series)
                    if metrics:
                        self.registry.update_model_metrics(model_id, metrics)
                        logger.info(f"Model metrics persisted to registry: {list(metrics.keys())}")
                except Exception as eval_err:
                    logger.warning(f"Model evaluation or registry update failed without blocking training: {eval_err}")
            else:
                logger.warning(f"Model training returned no model id: {ticker} ({model_type})")
                return None

            return model_id
        except Exception as e:
            logger.error(f"Training pipeline error ({ticker}, {model_type}): {e}", exc_info=True)
            return None

    def run_hyperparameter_tuning(
        self,
        ticker: str,
        model_type: str = "xgboost",
        n_trials: int = 30,
        price_series: Optional[pd.Series] = None,
    ) -> Optional[str]:
        """
        Run Optuna tuning for one ticker and train a tuned XGBoost model.
        鍙傛暟:
            ticker: 鏍囩殑浠ｇ爜
            model_type: 妯″瀷绫诲瀷锛岀洰鍓嶄粎 "xgboost"
            n_trials: Number of Optuna trials.
            price_series: Optional price history. If omitted, local history is loaded.
            
        杩斿洖:
            Trained model id on success, otherwise None.
        """
        if model_type != "xgboost" or not XGBOOST_AVAILABLE:
            logger.warning("Hyperparameter tuning currently supports xgboost only")
            return None
        if price_series is None:
            price_series = load_local_price_history(ticker)
        if price_series is None or len(price_series) < self.min_train_days:
            logger.warning(f"鏁版嵁涓嶈冻鏃犳硶璋冧紭: {ticker}")
            return None
        try:
            best_params = run_optuna_xgboost_tuning(price_series, n_trials=n_trials)
            if not best_params:
                logger.warning("Optuna returned no valid parameters, falling back to default training parameters")
            return self.train_model(
                ticker,
                price_series=price_series,
                model_type=model_type,
                use_enhanced_features=True,
                hyperparams=best_params,
            )
        except Exception as e:
            logger.error(f"瓒呭弬璋冧紭澶辫触 ({ticker}): {e}", exc_info=True)
            return None

    def evaluate_model(
        self, ticker: str, model_id: str, price_series: pd.Series
    ) -> Dict[str, float]:
        """
        璇勪及妯″瀷琛ㄧ幇

        鍙傛暟:
            ticker: 鏍囩殑浠ｇ爜
            model_id: 妯″瀷ID
            price_series: 浠锋牸搴忓垪锛堢敤浜庤瘎浼帮級

        杩斿洖:
            璇勪及鎸囨爣瀛楀吀
        """
        try:
            # 鍔犺浇妯″瀷
            model_info = self.registry.get_model_info(model_id)
            if not model_info:
                return {}

            model_path = model_info.get("model_path")
            if not model_path:
                return {}

            import joblib

            model = joblib.load(model_path)
            
            # Continue with the requested model family after validation and tuning.
            model_class = None
            if isinstance(model, XGBoostForecaster):
                model_class = XGBoostForecaster
            elif isinstance(model, LightGBMForecaster):
                model_class = LightGBMForecaster
            elif isinstance(model, RandomForestForecaster):
                model_class = RandomForestForecaster
            elif isinstance(model, LSTMForecaster):
                model_class = LSTMForecaster
            elif isinstance(model, GRUForecaster):
                model_class = GRUForecaster
            
            if model_class is None:
                return {}

            # 浣跨敤婊氬姩绐楀彛楠岃瘉
            validation_results = ModelEvaluator.walk_forward_validation(
                price_series,
                model_class,
                n_splits=3,
                test_size=20,
                purge_days=5,
                embargo_days=2,
                transaction_cost=0.001,
            )

            if validation_results.empty:
                return {}

            # 璁＄畻骞冲潎鎸囨爣
            metrics = {
                "direction_accuracy": float(validation_results["Direction_Accuracy"].mean()),
                "mae": float(validation_results["MAE"].mean()),
                "rmse": float(validation_results["RMSE"].mean()),
                "smape": float(validation_results.get("SMAPE", pd.Series(dtype=float)).mean() or 0.0),
                "ece": float(validation_results.get("ECE", pd.Series(dtype=float)).mean() or 0.0),
                "strategy_sharpe": float(validation_results["Strategy_Sharpe"].mean()),
                "strategy_net_return": float(validation_results.get("Strategy_NetReturn", pd.Series(dtype=float)).mean() or 0.0),
                "strategy_max_drawdown": float(validation_results.get("Strategy_MaxDrawdown", pd.Series(dtype=float)).mean() or 0.0),
                "strategy_turnover": float(validation_results.get("Strategy_Turnover", pd.Series(dtype=float)).mean() or 0.0),
                "evaluation_folds": int(len(validation_results)),
                "walk_forward_purge_days": 5.0,
                "walk_forward_embargo_days": 2.0,
            }

            return metrics

        except Exception as e:
            logger.error(f"璇勪及妯″瀷澶辫触 ({ticker}, {model_id}): {e}")
            return {}

    def compare_models(
        self, ticker: str, new_model_id: str, old_model_id: Optional[str] = None
    ) -> Tuple[bool, Dict]:
        """
        Compare champion/challenger models.

        New model runs in shadow mode first. It must outperform the current
        production model for consecutive evaluation rounds before promotion.
        """
        if old_model_id is None:
            old_model_id = self.registry.get_production_model(ticker)

        new_info = self.registry.get_model_info(new_model_id) or {}
        new_metrics = new_info.get("metrics", {})
        comparison = {
            "new_model_id": new_model_id,
            "old_model_id": old_model_id,
            "should_update": False,
            "reason": "",
        }

        if not old_model_id:
            comparison["should_update"] = True
            comparison["reason"] = "no production model exists"
            return True, comparison

        old_info = self.registry.get_model_info(old_model_id) or {}
        old_metrics = old_info.get("metrics", {})

        def _composite_score(metrics: Dict) -> float:
            net = float(metrics.get("strategy_net_return", metrics.get("strategy_cumreturn", 0.0)))
            sharpe = float(metrics.get("strategy_sharpe", 0.0))
            max_drawdown = abs(float(metrics.get("strategy_max_drawdown", 0.0)))
            turnover = float(metrics.get("strategy_turnover", 0.0))
            direction = float(metrics.get("direction_accuracy", 0.0)) / 100.0
            ece = float(metrics.get("ece", 0.0))
            return net + 0.10 * sharpe + 0.05 * direction - 0.50 * max_drawdown - 0.10 * turnover - 0.20 * ece

        new_score = _composite_score(new_metrics)
        old_score = _composite_score(old_metrics)
        score_delta = new_score - old_score

        shadow_win_streak = int(new_metrics.get("shadow_win_streak", 0))
        if score_delta >= self.shadow_score_margin:
            shadow_win_streak += 1
        else:
            shadow_win_streak = 0

        self.registry.update_model_metrics(
            new_model_id,
            {
                "shadow_win_streak": float(shadow_win_streak),
                "shadow_required_wins": float(self.shadow_required_wins),
                "shadow_score_delta": float(score_delta),
                "shadow_reference_score": float(old_score),
            },
        )

        comparison["new_score"] = float(new_score)
        comparison["old_score"] = float(old_score)
        comparison["score_delta"] = float(score_delta)
        comparison["shadow_win_streak"] = shadow_win_streak
        comparison["shadow_required_wins"] = self.shadow_required_wins

        if shadow_win_streak >= self.shadow_required_wins and score_delta >= self.shadow_score_margin:
            comparison["should_update"] = True
            comparison["reason"] = (
                f"challenger won shadow phase ({shadow_win_streak}/{self.shadow_required_wins})"
            )
        else:
            comparison["reason"] = (
                f"shadow phase in progress ({shadow_win_streak}/{self.shadow_required_wins}), "
                f"score_delta={score_delta:.4f}"
            )

        return comparison["should_update"], comparison

    def train_and_evaluate(
        self,
        ticker: str,
        price_series: Optional[pd.Series] = None,
        model_type: str = "xgboost",
        auto_promote: bool = True,
    ) -> Dict:
        """
        Train, evaluate, and optionally promote a candidate model.

        鍙傛暟:
            ticker: 鏍囩殑浠ｇ爜
            price_series: 浠锋牸搴忓垪
            model_type: 妯″瀷绫诲瀷
            auto_promote: Whether to promote the candidate when it outperforms production.
        杩斿洖:
            Result summary for the training run.
        """
        result = {
            "ticker": ticker,
            "model_type": model_type,
            "success": False,
            "model_id": None,
            "promoted": False,
            "message": "",
        }

        # Train the candidate model first.
        model_id = self.train_model(ticker, price_series, model_type=model_type)
        if not model_id:
            result["message"] = "Model training failed"
            return result

        result["model_id"] = model_id
        result["success"] = True

        # 璇勪及妯″瀷
        if price_series is None:
            price_series = load_local_price_history(ticker)

        if price_series is not None:
            metrics = self.evaluate_model(ticker, model_id, price_series)
            if metrics:
                # Persist evaluation metrics in model registry.
                self.registry.update_model_metrics(model_id, metrics)

        # Auto-promote model when enabled and criteria are met.
        if auto_promote:
            should_update, comparison = self.compare_models(ticker, model_id)
            if should_update:
                if self.registry.set_production_model(ticker, model_id):
                    result["promoted"] = True
                    result["message"] = f"妯″瀷宸叉彁鍗囦负鐢熶骇妯″瀷: {comparison.get('reason', '')}"
                else:
                    result["message"] = "妯″瀷璇勪及閫氳繃锛屼絾鎻愬崌澶辫触"
            else:
                result["message"] = f"Model trained successfully, but promotion criteria were not met: {comparison.get('reason', '')}"

        return result

    def generate_predictions(
        self, ticker: str, horizon: int = 5, model_id: Optional[str] = None
    ) -> bool:
        """
        Generate prediction signals and persist them into the signal store.
        鍙傛暟:
            ticker: 鏍囩殑浠ｇ爜
            horizon: 棰勬祴澶╂暟
            model_id: 妯″瀷ID锛圢one鍒欎娇鐢ㄧ敓浜фā鍨嬶級

        杩斿洖:
            Whether signal generation succeeded.
        """
        if model_id is None:
            model_id = self.registry.get_production_model(ticker)

        if not model_id:
            logger.warning(f"鏃犵敓浜фā鍨嬶紝鏃犳硶鐢熸垚棰勬祴: {ticker}")
            return False

        try:
            # 鍔犺浇浠锋牸鏁版嵁
            price_series = load_local_price_history(ticker)
            if price_series is None or price_series.empty:
                return False

            # 鍔犺浇妯″瀷
            model_info = self.registry.get_model_info(model_id)
            if not model_info:
                return False

            import joblib

            model = joblib.load(model_info["model_path"])
            
            # Validate model class support before generating signals.
            if not isinstance(model, (XGBoostForecaster, LightGBMForecaster, RandomForestForecaster,
                                     LSTMForecaster, GRUForecaster)):
                return False

            # 棰勬祴
            pred = model.predict(horizon)
            if pred is None or pred.empty:
                return False

            # 鐢熸垚淇″彿
            last_price = float(price_series.iloc[-1])
            pred_price = float(pred["prediction"].iloc[0])
            prediction_return = (pred_price - last_price) / last_price

            if "up_probability" in pred.columns and "confidence" in pred.columns and "signal" in pred.columns:
                up_prob = float(pred["up_probability"].iloc[0])
                confidence = float(pred["confidence"].iloc[0])
                signal = str(pred["signal"].iloc[0])
                direction = 1 if up_prob >= 0.5 else -1
                if signal == "hold":
                    direction = 0
            else:
                direction = 1 if prediction_return > 0.01 else (-1 if prediction_return < -0.01 else 0)
                confidence = min(abs(prediction_return) * 10, 1.0)
                signal = "buy" if direction > 0 else ("sell" if direction < 0 else "hold")

            # 淇濆瓨淇″彿
            self.signal_store.save_signal(
                ticker=ticker,
                prediction=prediction_return,
                direction=direction,
                confidence=confidence,
                signal=signal,
                model_id=model_id,
                status="pending",
            )

            return True

        except Exception as e:
            logger.error(f"鐢熸垚棰勬祴淇″彿澶辫触 ({ticker}): {e}")
            return False

    def run_training_job(
        self, 
        tickers: List[str], 
        model_type: str = "xgboost",
        auto_promote: bool = True, 
        generate_signals: bool = True
    ) -> Dict:
        """
        Run batch model training for a ticker list and collect execution stats.

        鍙傛暟:
            tickers: 鏍囩殑鍒楄〃
            auto_promote: Whether to auto-promote a better candidate model.
            generate_signals: Whether to generate prediction signals after training.
        杩斿洖:
            Aggregated execution statistics for the batch job.
        """
        stats = {
            "total": len(tickers),
            "trained": 0,
            "promoted": 0,
            "failed": 0,
            "skipped": 0,
            "details": [],
        }

        for ticker in tickers:
            try:
                # Skip work when retraining is not required for the ticker.
                if not self.should_retrain(ticker):
                    stats["skipped"] += 1
                    stats["details"].append(
                        {"ticker": ticker, "status": "skipped", "reason": "retrain not required"}
                    )
                    continue

                # Low-spec optimization: skip the ticker when available memory is too low.
                try:
                    import psutil
                    mem = psutil.virtual_memory()
                    if mem.available < 400 * 1024 * 1024:  # 400MB
                        stats["skipped"] += 1
                        stats["details"].append(
                            {"ticker": ticker, "status": "skipped", "reason": f"鍐呭瓨涓嶈冻({mem.available // 1024 // 1024}MB)"}
                        )
                        gc.collect()
                        continue
                except Exception:
                    pass

                # Train and evaluate each ticker in batch job.
                result = self.train_and_evaluate(ticker, model_type=model_type, auto_promote=auto_promote)

                if result["success"]:
                    stats["trained"] += 1
                    if result["promoted"]:
                        stats["promoted"] += 1

                    # 鐢熸垚棰勬祴淇″彿
                    if generate_signals:
                        self.generate_predictions(ticker)

                    stats["details"].append(
                        {
                            "ticker": ticker,
                            "status": "success",
                            "model_id": result["model_id"],
                            "promoted": result["promoted"],
                            "message": result["message"],
                        }
                    )
                else:
                    stats["failed"] += 1
                    stats["details"].append(
                        {"ticker": ticker, "status": "failed", "reason": result["message"]}
                    )

            except Exception as e:
                stats["failed"] += 1
                stats["details"].append(
                    {"ticker": ticker, "status": "error", "error": str(e)}
                )
                logger.error(f"Batch training failed for {ticker}: {e}", exc_info=True)
            finally:
                gc.collect()  # Low-spec optimization: release memory after each ticker.
        return stats

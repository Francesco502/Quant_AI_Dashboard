"""
离线训练流水线模块（阶段二：训练/预测解耦）

职责：
- 批量训练模型
- 模型评估与对比
- 自动注册生产模型
- 生成预测信号
"""

from __future__ import annotations

import logging
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
    """离线训练流水线"""

    def __init__(
        self,
        model_dir: str = "models/",
        min_train_days: int = 60,
        retrain_interval_days: int = 7,
        min_improvement_threshold: float = 0.02,
    ):
        """
        初始化训练流水线

        参数:
            model_dir: 模型目录
            min_train_days: 最小训练天数
            retrain_interval_days: 重训练间隔天数
            min_improvement_threshold: 最小改进阈值（用于决定是否更新生产模型）
        """
        self.model_manager = ModelManager(model_dir=model_dir)
        self.registry = self.model_manager.registry
        self.feature_store = get_feature_store()
        self.signal_store = get_signal_store()
        self.min_train_days = min_train_days
        self.retrain_interval_days = retrain_interval_days
        self.min_improvement_threshold = min_improvement_threshold

    def should_retrain(self, ticker: str) -> bool:
        """
        判断是否需要重新训练模型

        参数:
            ticker: 标的代码

        返回:
            是否需要重训练
        """
        # 检查是否有生产模型
        prod_model_id = self.registry.get_production_model(ticker)
        if not prod_model_id:
            return True

        # 检查模型年龄
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
        训练单个标的的模型

        参数:
            ticker: 标的代码
            price_series: 价格序列（None则从本地加载）
            model_type: 模型类型 ("xgboost", "lightgbm", "random_forest", "lstm", "gru")
            use_enhanced_features: 是否使用增强特征（仅适用于树模型）
            hyperparams: 超参数（None则使用默认值）

        返回:
            模型ID，失败返回None
        """
        # 检查模型可用性
        model_available = {
            "xgboost": XGBOOST_AVAILABLE,
            "lightgbm": LIGHTGBM_AVAILABLE,
            "random_forest": SKLEARN_AVAILABLE,
            "lstm": TORCH_AVAILABLE,
            "gru": TORCH_AVAILABLE,
        }
        
        if not model_available.get(model_type, False):
            logger.warning(f"{model_type}未安装，跳过训练 {ticker}")
            return None

        # 加载价格数据
        if price_series is None:
            price_series = load_local_price_history(ticker)

        if price_series is None or price_series.empty:
            logger.warning(f"无法加载价格数据: {ticker}")
            return None

        if len(price_series) < self.min_train_days:
            logger.warning(f"数据不足，跳过训练 {ticker} (需要{self.min_train_days}天，实际{len(price_series)}天)")
            return None

        try:
            # 训练模型
            features_version = self.feature_store.get_feature_version()
            
            # 准备训练参数
            train_kwargs = {
                "ticker": ticker,
                "price_series": price_series,
                "model_type": model_type,
                "use_enhanced_features": use_enhanced_features if model_type in ["xgboost", "lightgbm", "random_forest"] else False,
                "register_model": True,
                "features_version": features_version,
            }
            
            # 添加模型特定参数
            if hyperparams:
                train_kwargs.update(hyperparams)
            elif model_type in ["lstm", "gru"]:
                train_kwargs["epochs"] = 50
                train_kwargs["sequence_length"] = min(30, len(price_series) // 2)
            
            model_id = self.model_manager.train_model(**train_kwargs)

            if model_id:
                logger.info(f"模型训练成功: {ticker} ({model_type}) -> {model_id}")
                return model_id
            else:
                logger.warning(f"模型训练失败: {ticker} ({model_type})")
                return None

        except Exception as e:
            logger.error(f"训练模型异常 ({ticker}, {model_type}): {e}", exc_info=True)
            return None

    def evaluate_model(
        self, ticker: str, model_id: str, price_series: pd.Series
    ) -> Dict[str, float]:
        """
        评估模型表现

        参数:
            ticker: 标的代码
            model_id: 模型ID
            price_series: 价格序列（用于评估）

        返回:
            评估指标字典
        """
        try:
            # 加载模型
            model_info = self.registry.get_model_info(model_id)
            if not model_info:
                return {}

            model_path = model_info.get("model_path")
            if not model_path:
                return {}

            import joblib

            model = joblib.load(model_path)
            
            # 确定模型类型
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

            # 使用滚动窗口验证
            validation_results = ModelEvaluator.walk_forward_validation(
                price_series, model_class, n_splits=3, test_size=20
            )

            if validation_results.empty:
                return {}

            # 计算平均指标
            metrics = {
                "direction_accuracy": validation_results["Direction_Accuracy"].mean(),
                "mae": validation_results["MAE"].mean(),
                "rmse": validation_results["RMSE"].mean(),
                "strategy_sharpe": validation_results["Strategy_Sharpe"].mean(),
                "strategy_cumreturn": validation_results["Strategy_CumReturn"].mean(),
            }

            return metrics

        except Exception as e:
            logger.error(f"评估模型失败 ({ticker}, {model_id}): {e}")
            return {}

    def compare_models(
        self, ticker: str, new_model_id: str, old_model_id: Optional[str] = None
    ) -> Tuple[bool, Dict]:
        """
        对比新旧模型，决定是否更新生产模型

        参数:
            ticker: 标的代码
            new_model_id: 新模型ID
            old_model_id: 旧模型ID（None则自动获取当前生产模型）

        返回:
            (是否更新, 对比结果)
        """
        if old_model_id is None:
            old_model_id = self.registry.get_production_model(ticker)

        new_metrics = self.registry.get_model_info(new_model_id).get("metrics", {})
        comparison = {
            "new_model_id": new_model_id,
            "old_model_id": old_model_id,
            "should_update": False,
            "reason": "",
        }

        # 如果没有旧模型，直接使用新模型
        if not old_model_id:
            comparison["should_update"] = True
            comparison["reason"] = "无现有生产模型"
            return True, comparison

        old_metrics = self.registry.get_model_info(old_model_id).get("metrics", {})

        # 对比关键指标
        new_direction_acc = new_metrics.get("direction_accuracy", 0)
        old_direction_acc = old_metrics.get("direction_accuracy", 0)

        new_sharpe = new_metrics.get("strategy_sharpe", 0)
        old_sharpe = old_metrics.get("strategy_sharpe", 0)

        # 决策逻辑：新模型在方向准确率或夏普比率上有显著提升
        direction_improved = (
            new_direction_acc - old_direction_acc
        ) >= self.min_improvement_threshold
        sharpe_improved = (new_sharpe - old_sharpe) >= self.min_improvement_threshold

        if direction_improved or sharpe_improved:
            comparison["should_update"] = True
            if direction_improved and sharpe_improved:
                comparison["reason"] = "方向准确率和夏普比率均有提升"
            elif direction_improved:
                comparison["reason"] = "方向准确率提升"
            else:
                comparison["reason"] = "夏普比率提升"
        else:
            comparison["reason"] = "新模型未达到改进阈值"

        comparison["new_direction_acc"] = new_direction_acc
        comparison["old_direction_acc"] = old_direction_acc
        comparison["new_sharpe"] = new_sharpe
        comparison["old_sharpe"] = old_sharpe

        return comparison["should_update"], comparison

    def train_and_evaluate(
        self,
        ticker: str,
        price_series: Optional[pd.Series] = None,
        model_type: str = "xgboost",
        auto_promote: bool = True,
    ) -> Dict:
        """
        训练模型并评估，可选自动提升为生产模型

        参数:
            ticker: 标的代码
            price_series: 价格序列
            model_type: 模型类型
            auto_promote: 是否自动提升为生产模型（如果表现更好）

        返回:
            训练结果字典
        """
        result = {
            "ticker": ticker,
            "model_type": model_type,
            "success": False,
            "model_id": None,
            "promoted": False,
            "message": "",
        }

        # 训练模型
        model_id = self.train_model(ticker, price_series, model_type=model_type)
        if not model_id:
            result["message"] = "模型训练失败"
            return result

        result["model_id"] = model_id
        result["success"] = True

        # 评估模型
        if price_series is None:
            price_series = load_local_price_history(ticker)

        if price_series is not None:
            metrics = self.evaluate_model(ticker, model_id, price_series)
            if metrics:
                # 更新模型元数据中的评估指标
                self.registry.update_model_metrics(model_id, metrics)

        # 自动提升为生产模型
        if auto_promote:
            should_update, comparison = self.compare_models(ticker, model_id)
            if should_update:
                if self.registry.set_production_model(ticker, model_id):
                    result["promoted"] = True
                    result["message"] = f"模型已提升为生产模型: {comparison.get('reason', '')}"
                else:
                    result["message"] = "模型评估通过，但提升失败"
            else:
                result["message"] = f"模型训练成功，但未达到提升标准: {comparison.get('reason', '')}"

        return result

    def generate_predictions(
        self, ticker: str, horizon: int = 5, model_id: Optional[str] = None
    ) -> bool:
        """
        生成预测信号并保存

        参数:
            ticker: 标的代码
            horizon: 预测天数
            model_id: 模型ID（None则使用生产模型）

        返回:
            是否成功
        """
        if model_id is None:
            model_id = self.registry.get_production_model(ticker)

        if not model_id:
            logger.warning(f"无生产模型，无法生成预测: {ticker}")
            return False

        try:
            # 加载价格数据
            price_series = load_local_price_history(ticker)
            if price_series is None or price_series.empty:
                return False

            # 加载模型
            model_info = self.registry.get_model_info(model_id)
            if not model_info:
                return False

            import joblib

            model = joblib.load(model_info["model_path"])
            
            # 检查模型类型是否支持预测
            if not isinstance(model, (XGBoostForecaster, LightGBMForecaster, RandomForestForecaster, 
                                     LSTMForecaster, GRUForecaster)):
                return False

            # 预测
            pred = model.predict(horizon)
            if pred is None or pred.empty:
                return False

            # 生成信号
            last_price = float(price_series.iloc[-1])
            pred_price = float(pred["prediction"].iloc[0])
            prediction_return = (pred_price - last_price) / last_price

            direction = 1 if prediction_return > 0.01 else (-1 if prediction_return < -0.01 else 0)
            confidence = min(abs(prediction_return) * 10, 1.0)
            signal = "buy" if direction > 0 else ("sell" if direction < 0 else "hold")

            # 保存信号
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
            logger.error(f"生成预测信号失败 ({ticker}): {e}")
            return False

    def run_training_job(
        self, 
        tickers: List[str], 
        model_type: str = "xgboost",
        auto_promote: bool = True, 
        generate_signals: bool = True
    ) -> Dict:
        """
        批量训练任务

        参数:
            tickers: 标的列表
            auto_promote: 是否自动提升为生产模型
            generate_signals: 是否生成预测信号

        返回:
            任务结果统计
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
                # 检查是否需要重训练
                if not self.should_retrain(ticker):
                    stats["skipped"] += 1
                    stats["details"].append(
                        {"ticker": ticker, "status": "skipped", "reason": "无需重训练"}
                    )
                    continue

                # 训练并评估
                result = self.train_and_evaluate(ticker, model_type=model_type, auto_promote=auto_promote)

                if result["success"]:
                    stats["trained"] += 1
                    if result["promoted"]:
                        stats["promoted"] += 1

                    # 生成预测信号
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
                logger.error(f"训练任务异常 ({ticker}): {e}", exc_info=True)

        return stats


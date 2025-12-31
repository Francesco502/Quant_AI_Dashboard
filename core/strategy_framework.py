"""
统一策略框架模块（阶段三：策略与AI融合）

职责：
- 提供统一的策略接口
- 支持技术指标策略、AI预测策略、混合策略
- 策略配置化和版本管理
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .advanced_forecasting import quick_predict
from .strategy_engine import generate_multi_asset_signals

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STRATEGIES_DIR = os.path.join(BASE_DIR, "strategies")
STRATEGIES_CONFIG_FILE = os.path.join(STRATEGIES_DIR, "config.json")


def _ensure_strategies_dir() -> None:
    """确保策略目录存在"""
    os.makedirs(STRATEGIES_DIR, exist_ok=True)


@dataclass
class StrategySignal:
    """策略信号数据类"""

    ticker: str
    signal: float  # -1 到 1 的信号强度
    direction: int  # -1=卖出, 0=持有, 1=买入
    confidence: float  # 0 到 1 的置信度
    action: str  # 文字化动作
    reason: str  # 信号理由
    target_weight: Optional[float] = None  # 建议仓位权重


class BaseStrategy(ABC):
    """策略基类"""

    def __init__(self, strategy_id: str, version: str = "v1.0", config: Optional[Dict] = None):
        """
        初始化策略

        参数:
            strategy_id: 策略唯一ID
            version: 策略版本
            config: 策略配置字典
        """
        self.strategy_id = strategy_id
        self.version = version
        self.config = config or {}
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @abstractmethod
    def generate_signals(
        self, price_df: pd.DataFrame, **kwargs
    ) -> pd.DataFrame:
        """
        生成信号（子类实现）

        参数:
            price_df: 价格DataFrame，列为资产代码，行为日期
            **kwargs: 其他参数

        返回:
            信号DataFrame，包含ticker、signal、direction、confidence、action等列
        """
        raise NotImplementedError

    def get_config(self) -> Dict:
        """
        返回策略配置（用于复现）

        返回:
            配置字典
        """
        return {
            "strategy_id": self.strategy_id,
            "version": self.version,
            "type": self.__class__.__name__,
            "config": self.config,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.strategy_id}, version={self.version})"


class TechnicalStrategy(BaseStrategy):
    """基于技术指标的策略"""

    def __init__(
        self,
        strategy_id: str,
        version: str = "v1.0",
        fast_window: int = 20,
        slow_window: int = 50,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        buy_threshold: float = 0.3,
        sell_threshold: float = -0.3,
        **kwargs
    ):
        """
        初始化技术指标策略

        参数:
            strategy_id: 策略ID
            version: 策略版本
            fast_window: 快线窗口
            slow_window: 慢线窗口
            rsi_oversold: RSI超卖阈值
            rsi_overbought: RSI超买阈值
            buy_threshold: 买入信号阈值
            sell_threshold: 卖出信号阈值
        """
        config = {
            "fast_window": fast_window,
            "slow_window": slow_window,
            "rsi_oversold": rsi_oversold,
            "rsi_overbought": rsi_overbought,
            "buy_threshold": buy_threshold,
            "sell_threshold": sell_threshold,
            **kwargs,
        }
        super().__init__(strategy_id, version, config)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def generate_signals(
        self, price_df: pd.DataFrame, **kwargs
    ) -> pd.DataFrame:
        """
        生成技术指标信号

        参数:
            price_df: 价格DataFrame

        返回:
            信号DataFrame
        """
        if price_df is None or price_df.empty:
            return pd.DataFrame()

        # 使用现有的技术指标信号生成函数
        signals_df = generate_multi_asset_signals(
            price_df,
            buy_threshold=self.buy_threshold,
            sell_threshold=self.sell_threshold,
            **kwargs
        )

        if signals_df.empty:
            return pd.DataFrame()

        # 转换为统一格式
        result_rows = []
        for _, row in signals_df.iterrows():
            combined_signal = float(row.get("combined_signal", 0))
            
            # 确定方向和动作
            if combined_signal >= self.buy_threshold:
                direction = 1
                action = "买入"
            elif combined_signal <= self.sell_threshold:
                direction = -1
                action = "卖出"
            else:
                direction = 0
                action = "持有"

            # 置信度基于信号强度
            confidence = min(abs(combined_signal), 1.0)

            result_rows.append({
                "ticker": row["ticker"],
                "signal": combined_signal,
                "direction": direction,
                "confidence": confidence,
                "action": action,
                "reason": row.get("reason", ""),
                "strategy_id": self.strategy_id,
            })

        return pd.DataFrame(result_rows)


class AIStrategy(BaseStrategy):
    """基于AI预测的策略"""

    def __init__(
        self,
        strategy_id: str,
        version: str = "v1.0",
        model_type: str = "xgboost",
        buy_threshold: float = 0.02,
        sell_threshold: float = -0.01,
        horizon: int = 1,
        use_production_model: bool = True,
        **kwargs
    ):
        """
        初始化AI策略

        参数:
            strategy_id: 策略ID
            version: 策略版本
            model_type: 模型类型
            buy_threshold: 买入阈值（预测收益率）
            sell_threshold: 卖出阈值（预测收益率）
            horizon: 预测天数
            use_production_model: 是否使用生产模型
        """
        config = {
            "model_type": model_type,
            "buy_threshold": buy_threshold,
            "sell_threshold": sell_threshold,
            "horizon": horizon,
            "use_production_model": use_production_model,
            **kwargs,
        }
        super().__init__(strategy_id, version, config)
        self.model_type = model_type
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.horizon = horizon
        self.use_production_model = use_production_model

    def generate_signals(
        self, price_df: pd.DataFrame, **kwargs
    ) -> pd.DataFrame:
        """
        生成AI预测信号

        参数:
            price_df: 价格DataFrame

        返回:
            信号DataFrame
        """
        if price_df is None or price_df.empty:
            return pd.DataFrame()

        result_rows = []
        
        for ticker in price_df.columns:
            try:
                # 使用快速预测接口
                pred = quick_predict(
                    ticker=ticker,
                    horizon=self.horizon,
                    model_type=self.model_type,
                    use_production_model=self.use_production_model,
                    save_signal=False,  # 不在这里保存，由策略管理器统一处理
                )

                if pred is None or pred.empty:
                    continue

                # 获取当前价格
                price_series = price_df[ticker].dropna()
                if price_series.empty:
                    continue

                last_price = float(price_series.iloc[-1])
                pred_price = float(pred["prediction"].iloc[0])
                prediction_return = (pred_price - last_price) / last_price

                # 确定方向和动作
                if prediction_return >= self.buy_threshold:
                    direction = 1
                    action = "买入"
                elif prediction_return <= self.sell_threshold:
                    direction = -1
                    action = "卖出"
                else:
                    direction = 0
                    action = "持有"

                # 置信度基于预测收益率的绝对值
                confidence = min(abs(prediction_return) * 10, 1.0)

                result_rows.append({
                    "ticker": ticker,
                    "signal": prediction_return,
                    "direction": direction,
                    "confidence": confidence,
                    "action": action,
                    "reason": f"AI预测收益率: {prediction_return:.2%}",
                    "strategy_id": self.strategy_id,
                    "prediction_return": prediction_return,
                })

            except Exception as e:
                # 单个资产失败不影响其他资产
                print(f"AI策略生成信号失败 ({ticker}): {e}")
                continue

        return pd.DataFrame(result_rows)


class EnsembleStrategy(BaseStrategy):
    """混合策略：技术指标 + AI 预测加权"""

    def __init__(
        self,
        strategy_id: str,
        version: str = "v1.0",
        sub_strategies: Optional[List[str]] = None,
        weights: Optional[List[float]] = None,
        **kwargs
    ):
        """
        初始化混合策略

        参数:
            strategy_id: 策略ID
            version: 策略版本
            sub_strategies: 子策略ID列表
            weights: 权重列表（需与子策略数量一致）
        """
        config = {
            "sub_strategies": sub_strategies or [],
            "weights": weights or [],
            **kwargs,
        }
        super().__init__(strategy_id, version, config)
        self.sub_strategies = sub_strategies or []
        self.weights = weights or []
        
        # 归一化权重
        if self.weights:
            total = sum(self.weights)
            if total > 0:
                self.weights = [w / total for w in self.weights]
            else:
                # 如果权重全为0，则平均分配
                self.weights = [1.0 / len(self.weights)] * len(self.weights)

    def generate_signals(
        self, price_df: pd.DataFrame, strategy_manager=None, **kwargs
    ) -> pd.DataFrame:
        """
        生成混合策略信号

        参数:
            price_df: 价格DataFrame
            strategy_manager: 策略管理器（用于获取子策略）
            **kwargs: 其他参数

        返回:
            信号DataFrame
        """
        if price_df is None or price_df.empty:
            return pd.DataFrame()

        if not self.sub_strategies:
            return pd.DataFrame()

        if strategy_manager is None:
            from .strategy_manager import get_strategy_manager
            strategy_manager = get_strategy_manager()

        # 收集所有子策略的信号
        all_signals = {}
        
        for i, sub_strategy_id in enumerate(self.sub_strategies):
            try:
                sub_strategy = strategy_manager.get_strategy(sub_strategy_id)
                if sub_strategy is None:
                    continue

                sub_signals = sub_strategy.generate_signals(price_df, **kwargs)
                if sub_signals.empty:
                    continue

                weight = self.weights[i] if i < len(self.weights) else 1.0 / len(self.sub_strategies)
                
                # 按ticker组织信号
                for _, row in sub_signals.iterrows():
                    ticker = row["ticker"]
                    if ticker not in all_signals:
                        all_signals[ticker] = {
                            "signals": [],
                            "weights": [],
                            "directions": [],
                            "confidences": [],
                            "reasons": [],
                        }
                    
                    all_signals[ticker]["signals"].append(float(row.get("signal", 0)))
                    all_signals[ticker]["weights"].append(weight)
                    all_signals[ticker]["directions"].append(int(row.get("direction", 0)))
                    all_signals[ticker]["confidences"].append(float(row.get("confidence", 0)))
                    all_signals[ticker]["reasons"].append(row.get("reason", ""))

            except Exception as e:
                print(f"子策略执行失败 ({sub_strategy_id}): {e}")
                continue

        # 加权聚合信号
        result_rows = []
        for ticker, data in all_signals.items():
            signals = np.array(data["signals"])
            weights = np.array(data["weights"])
            directions = np.array(data["directions"])
            confidences = np.array(data["confidences"])

            # 加权平均信号
            weighted_signal = np.sum(signals * weights)
            
            # 加权平均方向（四舍五入）
            weighted_direction = int(np.round(np.sum(directions * weights)))
            
            # 加权平均置信度
            weighted_confidence = np.sum(confidences * weights)

            # 确定动作
            if weighted_direction > 0:
                action = "买入"
            elif weighted_direction < 0:
                action = "卖出"
            else:
                action = "持有"

            # 合并理由
            reasons = "; ".join(set(data["reasons"]))
            if not reasons:
                reasons = f"混合策略信号: {weighted_signal:.4f}"

            result_rows.append({
                "ticker": ticker,
                "signal": weighted_signal,
                "direction": weighted_direction,
                "confidence": weighted_confidence,
                "action": action,
                "reason": reasons,
                "strategy_id": self.strategy_id,
            })

        return pd.DataFrame(result_rows)


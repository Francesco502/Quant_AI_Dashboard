"""选股策略库

包含13种选股策略：
技术分析类：
1. MA金叉策略 - 买入信号
2. RSI超卖策略 - 超卖反弹机会
3. 多头趋势策略 - 持续上涨趋势
4. 突破策略 - 价格突破阻力位
5. MACD策略 - 趋势转折信号
6. 布林带策略 - 波动率突破
7. 均值回归策略 - 价格偏离回归

基本面类：
8. 价值策略 - 低PE/PB价值股
9. 动量因子策略 - 过去表现好的股票
10. 质量因子策略 - 高质量财务指标
11. 低波动率策略 - 低波动率异象

事件/统计类：
12. 资金流向策略 - 主力资金跟随
13. 配对交易策略 - 价差套利

策略文件结构：
- ma_cross.py: MA金叉策略
- rsi_oversold.py: RSI超卖策略
- multi_trend.py: 多头趋势策略
- breakout.py: 突破策略
- value_investing.py: 价值策略
- macd_strategy.py: MACD策略
- bollinger_bands.py: 布林带策略
- mean_reversion.py: 均值回归策略
- momentum_factor.py: 动量因子策略
- quality_factor.py: 质量因子策略
- low_volatility.py: 低波动率策略
- money_flow.py: 资金流向策略
- pairs_trading.py: 配对交易策略
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Type
from dataclasses import dataclass
import logging
import importlib

logger = logging.getLogger(__name__)


@dataclass
class StrategySignal:
    """策略信号"""
    ticker: str
    score: float  # 0-100
    action: str  # 买入/观望/卖出
    reason: str
    metrics: Dict[str, float]
    weight: float = 1.0  # 策略权重


class BaseStrategy:
    """策略基类"""

    def __init__(self, name: str = "Base Strategy", weight: float = 1.0):
        self._name = name
        self.weight = weight

    def name(self) -> str:
        """返回策略名称"""
        return self._name

    def set_name(self, name: str):
        """设置策略名称"""
        self._name = name

    def description(self) -> str:
        """返回策略描述"""
        return "该策略基于价格、趋势或因子信号生成选股评分，请结合教学说明理解其适用场景。"

    def get_learning_info(self) -> dict:
        """
        获取策略学习信息

        Returns:
            {
                "type": "技术分析/基本面/统计套利",
                "difficulty": 1-5,
                "principles": "策略原理说明",
                "pros": ["优点1", "优点2"],
                "cons": ["缺点1", "缺点2"],
                "suitable_market": "适用市场环境",
                "risk_warning": "风险提示",
            }
        """
        return {
            "type": "未分类",
            "difficulty": 3,
            "principles": "暂无说明",
            "pros": [],
            "cons": [],
            "suitable_market": "未指定",
            "risk_warning": "投资有风险",
        }

    def calculate_signal(self, df: pd.DataFrame) -> float:
        """
        计算策略信号评分

        Args:
            df: OHLCV数据

        Returns:
            策略评分（0-100）
        """
        raise NotImplementedError

    def get_params(self) -> dict:
        """返回策略参数"""
        return {"weight": self.weight}

    def generate_signal(self, price_df: pd.DataFrame) -> List[StrategySignal]:
        """
        为多个股票生成信号

        Args:
            price_df: 股票价格数据DataFrame

        Returns:
            信号列表
        """
        raise NotImplementedError


# 导入所有策略类（使用try/except处理缺失的模块）
STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {}

def _try_import_strategy(module_name: str, class_name: str, strategy_name: str):
    """尝试导入策略类，失败时记录警告"""
    try:
        module = importlib.import_module(f"core.scanner.strategies.{module_name}")
        strategy_class = getattr(module, class_name)
        STRATEGY_REGISTRY[strategy_name] = strategy_class
        return strategy_class
    except (ImportError, AttributeError) as e:
        logger.debug(f"策略模块未找到: {module_name}.{class_name} - {e}")
        return None

# 尝试导入所有策略
MAStrategy = _try_import_strategy("ma_cross", "MAStrategy", "MA金叉策略")
RSIStrategy = _try_import_strategy("rsi_oversold", "RSIStrategy", "RSI超卖策略")
TrendStrategy = _try_import_strategy("multi_trend", "MultiTrendStrategy", "多头趋势策略")
BreakoutStrategy = _try_import_strategy("breakout", "BreakoutStrategy", "突破策略")
ValueStrategy = _try_import_strategy("value_investing", "ValueStrategy", "价值策略")
MACDStrategy = _try_import_strategy("macd_strategy", "MACDStrategy", "MACD策略")
BollingerStrategy = _try_import_strategy("bollinger_bands", "BollingerBandsStrategy", "布林带策略")
MeanReversionStrategy = _try_import_strategy("mean_reversion", "MeanReversionStrategy", "均值回归策略")
MomentumFactorStrategy = _try_import_strategy("momentum_factor", "MomentumFactorStrategy", "动量因子策略")
QualityFactorStrategy = _try_import_strategy("quality_factor", "QualityFactorStrategy", "质量因子策略")
LowVolatilityStrategy = _try_import_strategy("low_volatility", "LowVolatilityStrategy", "低波动率策略")
MoneyFlowStrategy = _try_import_strategy("money_flow", "MoneyFlowStrategy", "资金流向策略")
PairsTradingStrategy = _try_import_strategy("pairs_trading", "PairsTradingStrategy", "配对交易策略")


def get_strategy(strategy_name: str, **kwargs) -> BaseStrategy:
    """
    根据名称获取策略实例

    Args:
        strategy_name: 策略名称
        **kwargs: 策略参数

    Returns:
        策略实例
    """
    strategy_class = STRATEGY_REGISTRY.get(strategy_name)
    if strategy_class is None:
        raise ValueError(f"未知策略：{strategy_name}。可用策略：{list(STRATEGY_REGISTRY.keys())}")

    return strategy_class(**kwargs)


def list_strategies() -> List[dict]:
    """
    列出所有可用策略

    Returns:
        策略列表，每个包含name和description
    """
    strategies = []
    for name, cls in STRATEGY_REGISTRY.items():
        try:
            instance = cls()
            strategies.append({
                "name": instance.name() if hasattr(instance, 'name') else name,
                "description": instance.description() if hasattr(instance, 'description') else "",
                "class": cls,
                "params": instance.get_params() if hasattr(instance, 'get_params') else {}
            })
        except Exception as e:
            logger.warning(f"无法初始化策略 {name}: {e}")
            strategies.append({
                "name": name,
                "description": "无法获取策略详情",
                "class": cls,
                "params": {}
            })
    return strategies


class StockSelector:
    """选股器 - 综合多种策略"""

    def __init__(self, strategies: Optional[List[BaseStrategy]] = None):
        """
        初始化选股器

        Args:
            strategies: 策略列表，None则使用默认策略
        """
        if strategies is None:
            self.strategies = []
            # 尝试使用可用的策略
            if MAStrategy:
                self.strategies.append(MAStrategy(short_period=5, long_period=20))
            if RSIStrategy:
                self.strategies.append(RSIStrategy(period=14, oversold=30, overbought=70))
            if TrendStrategy:
                self.strategies.append(TrendStrategy())
            if BreakoutStrategy:
                self.strategies.append(BreakoutStrategy(period=20))
            if ValueStrategy:
                self.strategies.append(ValueStrategy())

            # 如果没有策略可用，使用空列表
            if not self.strategies:
                logger.warning("没有可用的选股策略")
        else:
            self.strategies = strategies

    def select_stocks(self, price_df: pd.DataFrame, top_n: int = 20, min_score: int = 50) -> pd.DataFrame:
        """
        综合选股

        Args:
            price_df: 价格数据
            top_n: 返回前N个股票
            min_score: 最低评分阈值

        Returns:
            选股结果DataFrame
        """
        all_signals = []

        # 生成各策略信号
        for strategy in self.strategies:
            try:
                signals = strategy.generate_signal(price_df)
                all_signals.extend(signals)
            except Exception as e:
                logger.error(f"策略 {strategy.name} 执行失败: {e}")

        # 汇总评分
        ticker_scores = {}
        ticker_reasons = {}
        ticker_metrics = {}
        ticker_actions = {}

        for signal in all_signals:
            if signal.ticker not in ticker_scores:
                ticker_scores[signal.ticker] = 0
                ticker_reasons[signal.ticker] = []
                ticker_metrics[signal.ticker] = {}
                ticker_actions[signal.ticker] = []

            ticker_scores[signal.ticker] += signal.score * signal.weight / len(self.strategies)
            ticker_reasons[signal.ticker].append(signal.reason)
            ticker_metrics[signal.ticker].update(signal.metrics)
            ticker_actions[signal.ticker].append(signal.action)

        # 生成汇总结果
        results = []
        for ticker, score in ticker_scores.items():
            # 大多数策略的买入建议
            action_counts = {}
            for action in ticker_actions[ticker]:
                action_counts[action] = action_counts.get(action, 0) + 1
            action = max(action_counts.keys(), key=lambda x: action_counts[x]) if action_counts else "观望"

            # 综合理由
            reasons = ticker_reasons[ticker]

            results.append({
                "ticker": ticker,
                "score": round(score, 2),
                "action": action,
                "reasons": "; ".join(reasons[:3]),  # 仅显示前3条
                **ticker_metrics[ticker],
            })

        # 按评分排序
        df = pd.DataFrame(results)
        if df.empty:
            return pd.DataFrame()

        df = df[df["score"] >= min_score]  # 过滤最低评分
        df = df.sort_values("score", ascending=False).head(top_n)

        return df


def get_stock_selector() -> StockSelector:
    """获取选股器实例"""
    return StockSelector()

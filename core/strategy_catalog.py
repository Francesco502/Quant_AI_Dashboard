from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


StrategyFunc = Callable[[pd.DataFrame, Dict[str, Any]], Dict[str, int]]


@dataclass(frozen=True)
class StrategyDefinition:
    id: str
    name: str
    description: str
    func: StrategyFunc
    category: str = "classic"
    default_params: Dict[str, Any] = field(default_factory=dict)


def _price_tickers(history: pd.DataFrame) -> Iterable[str]:
    for column in history.columns:
        if not str(column).endswith("_volume"):
            yield str(column)


def _series_for(history: pd.DataFrame, ticker: str, minimum_rows: int) -> Optional[pd.Series]:
    if ticker not in history.columns:
        return None

    series = pd.to_numeric(history[ticker], errors="coerce").dropna()
    if len(series) < minimum_rows:
        return None
    return series


def sma_crossover_strategy(history: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, int]:
    short_window = int(params.get("short_window", 10))
    long_window = int(params.get("long_window", 30))
    positions: Dict[str, int] = {}

    for ticker in _price_tickers(history):
        prices = _series_for(history, ticker, long_window)
        if prices is None:
            continue
        short_ma = prices.tail(short_window).mean()
        long_ma = prices.tail(long_window).mean()
        positions[ticker] = 100 if short_ma > long_ma else 0
    return positions


def ema_crossover_strategy(history: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, int]:
    fast_span = int(params.get("fast_span", 12))
    slow_span = int(params.get("slow_span", 26))
    positions: Dict[str, int] = {}

    for ticker in _price_tickers(history):
        prices = _series_for(history, ticker, slow_span + 5)
        if prices is None:
            continue
        fast_ema = prices.ewm(span=fast_span, adjust=False).mean().iloc[-1]
        slow_ema = prices.ewm(span=slow_span, adjust=False).mean().iloc[-1]
        positions[ticker] = 100 if fast_ema > slow_ema else 0
    return positions


def mean_reversion_strategy(history: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, int]:
    window = int(params.get("window", 20))
    std_dev = float(params.get("std_dev", 2.0))
    positions: Dict[str, int] = {}

    for ticker in _price_tickers(history):
        prices = _series_for(history, ticker, window)
        if prices is None:
            continue
        sma = prices.tail(window).mean()
        std = prices.tail(window).std()
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        current = float(prices.iloc[-1])

        if current < lower:
            positions[ticker] = 100
        elif current > upper:
            positions[ticker] = 0
    return positions


def rsi_reversion_strategy(history: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, int]:
    window = int(params.get("window", 14))
    oversold = float(params.get("oversold", 30.0))
    overbought = float(params.get("overbought", 70.0))
    positions: Dict[str, int] = {}

    for ticker in _price_tickers(history):
        prices = _series_for(history, ticker, window + 5)
        if prices is None:
            continue

        delta = prices.diff().dropna()
        gains = delta.clip(lower=0).rolling(window).mean()
        losses = (-delta.clip(upper=0)).rolling(window).mean()
        relative_strength = gains / losses.replace(0, np.nan)
        rsi = 100 - (100 / (1 + relative_strength))
        latest_rsi = float(rsi.iloc[-1]) if not rsi.dropna().empty else 50.0

        if latest_rsi <= oversold:
            positions[ticker] = 100
        elif latest_rsi >= overbought:
            positions[ticker] = 0
    return positions


def macd_trend_strategy(history: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, int]:
    fast = int(params.get("fast", 12))
    slow = int(params.get("slow", 26))
    signal = int(params.get("signal", 9))
    positions: Dict[str, int] = {}

    for ticker in _price_tickers(history):
        prices = _series_for(history, ticker, slow + signal + 5)
        if prices is None:
            continue

        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        bullish = macd_line.iloc[-1] > signal_line.iloc[-1] and histogram.iloc[-1] > 0
        positions[ticker] = 100 if bullish else 0
    return positions


def breakout_momentum_strategy(history: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, int]:
    breakout_window = int(params.get("breakout_window", 20))
    exit_window = int(params.get("exit_window", 10))
    momentum_window = int(params.get("momentum_window", 60))
    positions: Dict[str, int] = {}

    minimum_rows = max(breakout_window + 2, exit_window + 2, momentum_window + 2)

    for ticker in _price_tickers(history):
        prices = _series_for(history, ticker, minimum_rows)
        if prices is None:
            continue

        current = float(prices.iloc[-1])
        prior_breakout = float(prices.iloc[-(breakout_window + 1):-1].max())
        prior_exit = float(prices.iloc[-(exit_window + 1):-1].min())
        momentum_base = float(prices.iloc[-momentum_window])
        momentum = (current / momentum_base) - 1 if momentum_base > 0 else 0.0

        if current >= prior_breakout and momentum > 0:
            positions[ticker] = 100
        elif current <= prior_exit:
            positions[ticker] = 0
    return positions


def donchian_breakout_strategy(history: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, int]:
    breakout_window = int(params.get("breakout_window", 55))
    exit_window = int(params.get("exit_window", 20))
    positions: Dict[str, int] = {}

    minimum_rows = max(breakout_window + 2, exit_window + 2)

    for ticker in _price_tickers(history):
        prices = _series_for(history, ticker, minimum_rows)
        if prices is None:
            continue

        current = float(prices.iloc[-1])
        breakout_level = float(prices.iloc[-(breakout_window + 1):-1].max())
        exit_level = float(prices.iloc[-(exit_window + 1):-1].min())

        if current >= breakout_level:
            positions[ticker] = 100
        elif current <= exit_level:
            positions[ticker] = 0
    return positions


def momentum_rotation_strategy(history: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, int]:
    lookback = int(params.get("lookback", 60))
    top_n = max(int(params.get("top_n", 3)), 1)
    positions: Dict[str, int] = {}
    momentum_scores: List[tuple[str, float]] = []

    for ticker in _price_tickers(history):
        prices = _series_for(history, ticker, lookback + 2)
        if prices is None:
            continue

        base = float(prices.iloc[-(lookback + 1)])
        current = float(prices.iloc[-1])
        if base <= 0:
            continue

        momentum = (current / base) - 1.0
        positions[ticker] = 0
        if momentum > 0:
            momentum_scores.append((ticker, momentum))

    for ticker, _score in sorted(momentum_scores, key=lambda item: item[1], reverse=True)[:top_n]:
        positions[ticker] = 100

    return positions


_BUILTIN_STRATEGIES: Dict[str, StrategyDefinition] = {
    "sma_crossover": StrategyDefinition(
        id="sma_crossover",
        name="SMA 金叉策略",
        description="短期均线上穿长期均线时买入，下穿时卖出。",
        func=sma_crossover_strategy,
        default_params={"short_window": 10, "long_window": 30},
    ),
    "ema_crossover": StrategyDefinition(
        id="ema_crossover",
        name="EMA 趋势跟随",
        description="快慢 EMA 金叉持有，多用于平滑后的趋势跟随。",
        func=ema_crossover_strategy,
        default_params={"fast_span": 12, "slow_span": 26},
    ),
    "mean_reversion": StrategyDefinition(
        id="mean_reversion",
        name="布林带均值回归",
        description="价格偏离布林带下轨时介入，回到上轨附近退出。",
        func=mean_reversion_strategy,
        default_params={"window": 20, "std_dev": 2.0},
    ),
    "rsi_reversion": StrategyDefinition(
        id="rsi_reversion",
        name="RSI 超跌反弹",
        description="RSI 进入超跌区买入，进入超买区退出。",
        func=rsi_reversion_strategy,
        default_params={"window": 14, "oversold": 30.0, "overbought": 70.0},
    ),
    "macd_trend": StrategyDefinition(
        id="macd_trend",
        name="MACD 趋势确认",
        description="MACD 线上穿信号线且柱体转正时持有。",
        func=macd_trend_strategy,
        default_params={"fast": 12, "slow": 26, "signal": 9},
    ),
    "breakout_momentum": StrategyDefinition(
        id="breakout_momentum",
        name="唐奇安突破动量",
        description="突破近期高点且中期动量为正时介入，跌破退出带时离场。",
        func=breakout_momentum_strategy,
        default_params={"breakout_window": 20, "exit_window": 10, "momentum_window": 60},
    ),
    "donchian_breakout": StrategyDefinition(
        id="donchian_breakout",
        name="唐奇安通道突破",
        description="价格创出阶段新高时买入，跌破中期通道低点时退出。",
        func=donchian_breakout_strategy,
        default_params={"breakout_window": 55, "exit_window": 20},
    ),
    "momentum_rotation": StrategyDefinition(
        id="momentum_rotation",
        name="横截面动量轮动",
        description="在当前资产池中持有一段时间内动量最强的少数标的，并随强弱切换。",
        func=momentum_rotation_strategy,
        default_params={"lookback": 60, "top_n": 3},
    ),
}


def get_strategy_definition(strategy_id: str) -> Optional[StrategyDefinition]:
    return _BUILTIN_STRATEGIES.get(strategy_id)


def get_strategy_map() -> Dict[str, StrategyDefinition]:
    return dict(_BUILTIN_STRATEGIES)


def list_backtestable_strategies() -> List[Dict[str, Any]]:
    return [
        {
            "id": definition.id,
            "name": definition.name,
            "description": definition.description,
            "category": definition.category,
            "default_params": dict(definition.default_params),
            "class_name": definition.id,
            "alias": definition.name,
            "activate": True,
        }
        for definition in _BUILTIN_STRATEGIES.values()
    ]

"""Pairs-trading strategy — identifies co-integrated pairs for mean-reversion."""

from __future__ import annotations

import pandas as pd
import numpy as np

from core.scanner.strategies import BaseStrategy, StrategySignal


class PairsTradingStrategy(BaseStrategy):
    """Statistical arbitrage via co-integrated pairs (single-asset proxy)."""

    def __init__(self, lookback: int = 60, entry_z: float = 2.0, weight: float = 0.5):
        super().__init__("配对交易策略", weight)
        self.lookback = lookback
        self.entry_z = entry_z

    def name(self) -> str:
        return "配对交易策略"

    def description(self) -> str:
        return f"配对交易策略（回看{self.lookback}日，{self.entry_z}σ入场）"

    def calculate_signal(self, df: pd.DataFrame) -> float:
        """Signal based on z-score relative to rolling mean (proxy for spread)."""
        if len(df) < self.lookback:
            return 50
        close = df["close"]
        rolling_mean = close.rolling(self.lookback).mean()
        rolling_std = close.rolling(self.lookback).std().replace(0, np.nan).fillna(1e-6)
        z_score = (close.iloc[-1] - rolling_mean.iloc[-1]) / rolling_std.iloc[-1]
        # Negative z → oversold → bullish, positive z → overbought → bearish
        if z_score <= -self.entry_z:
            return float(np.clip(50 + abs(z_score) * 12, 0, 100))  # Buy signal
        if z_score >= self.entry_z:
            return float(np.clip(50 - abs(z_score) * 12, 0, 100))  # Sell/short signal
        return 50  # Neutral

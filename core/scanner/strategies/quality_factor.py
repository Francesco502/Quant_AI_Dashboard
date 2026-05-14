"""Quality factor strategy — favours stocks with strong fundamentals."""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass

from core.scanner.strategies import BaseStrategy, StrategySignal


class QualityFactorStrategy(BaseStrategy):
    """Quality factor strategy using profitability and stability proxies."""

    def __init__(self, lookback: int = 60, weight: float = 0.8):
        super().__init__("质量因子策略", weight)
        self.lookback = lookback

    def name(self) -> str:
        return "质量因子策略"

    def description(self) -> str:
        return f"质量因子策略（回看{self.lookback}日）— 偏好盈利稳定、低波动的标的"

    def calculate_signal(self, df: pd.DataFrame) -> float:
        if len(df) < self.lookback:
            return 50
        close = df["close"]
        returns = close.pct_change().dropna()
        if returns.empty:
            return 50
        # Quality = higher cumulative return + lower volatility
        cum_ret = (close.iloc[-1] / close.iloc[0] - 1.0) * 100
        vol = returns.std() * np.sqrt(252)
        if vol <= 0:
            return 50
        # Sharpe-like quality score mapped to 0-100
        quality = cum_ret / vol
        score = 50 + np.clip(quality * 25, -50, 50)
        return float(np.clip(score, 0, 100))

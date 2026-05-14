"""Low-volatility strategy — selects stocks with stable price behaviour."""

from __future__ import annotations

import pandas as pd
import numpy as np

from core.scanner.strategies import BaseStrategy, StrategySignal


class LowVolatilityStrategy(BaseStrategy):
    """Prefer stocks with lower-than-average realised volatility."""

    def __init__(self, lookback: int = 60, weight: float = 0.7):
        super().__init__("低波动策略", weight)
        self.lookback = lookback

    def name(self) -> str:
        return "低波动策略"

    def description(self) -> str:
        return f"低波动策略（回看{self.lookback}日）— 偏好历史波动较低的标的"

    def calculate_signal(self, df: pd.DataFrame) -> float:
        if len(df) < self.lookback:
            return 50
        close = df["close"]
        returns = close.pct_change().dropna()
        if returns.empty:
            return 50
        annual_vol = returns.std() * np.sqrt(252)
        # Lower vol → higher score; map ~10%→80, ~40%→20
        score = 80 - annual_vol * 200
        return float(np.clip(score, 0, 100))

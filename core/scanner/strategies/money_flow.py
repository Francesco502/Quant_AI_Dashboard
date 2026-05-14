"""Money-flow strategy — uses volume-price relationship to gauge capital flow."""

from __future__ import annotations

import pandas as pd
import numpy as np

from core.scanner.strategies import BaseStrategy, StrategySignal


class MoneyFlowStrategy(BaseStrategy):
    """Simple Chaikin-style money flow oscillator."""

    def __init__(self, period: int = 20, weight: float = 0.7):
        super().__init__("资金流策略", weight)
        self.period = period

    def name(self) -> str:
        return "资金流策略"

    def description(self) -> str:
        return f"资金流策略（{self.period}日）— 追踪量价关系判断资金方向"

    def calculate_signal(self, df: pd.DataFrame) -> float:
        if len(df) < self.period + 5:
            return 50
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"].replace(0, np.nan).fillna(1)

        # Typical price
        typical = (high + low + close) / 3
        # Raw money flow
        raw_mf = typical * volume
        pos_flow = raw_mf.where(typical > typical.shift(1), 0).rolling(self.period).sum()
        neg_flow = raw_mf.where(typical < typical.shift(1), 0).rolling(self.period).sum()
        mf_ratio = pos_flow / neg_flow.replace(0, np.nan).fillna(1)
        # Scale to 0–100
        score = 50 + (mf_ratio.iloc[-1] - 1) * 25
        return float(np.clip(score, 0, 100))

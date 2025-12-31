"""简单模拟交易与持仓规划模块（阶段2起点）

当前目标：
- 在不引入真实券商 API 和持久化账户的前提下，
  基于“交易信号总览”给出一份「等权模拟建仓计划」，
  方便从信号过渡到“具体买多少”的直觉。

后续可以在此模块基础上扩展：
- 引入真实账户现金/持仓
- 记录历史成交与权益曲线
- 支持多策略、多账户等
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict

import numpy as np
import pandas as pd


@dataclass
class SimulatedTrade:
    """单笔模拟交易记录"""

    ticker: str
    action: str  # BUY/SELL
    shares: int
    price: float
    notional: float


def generate_equal_weight_plan(
    signal_table: pd.DataFrame,
    total_capital: float = 100_000.0,
    max_positions: int = 5,
) -> pd.DataFrame:
    """基于信号表生成一个「等权模拟建仓计划」

    规则（简化版）：
    - 只考虑 action 为「买入/强烈买入」的资产；
    - 按 combined_signal 从高到低排序，最多取 max_positions 个；
    - 总资金 total_capital 等权分配到这些标的上；
    - 每个标的的买入数量 = floor(资金/最新价格)，不足一股/份则忽略。
    """
    if signal_table is None or signal_table.empty:
        return pd.DataFrame()

    # 只考虑买入方向的候选
    buy_candidates = signal_table[
        signal_table["action"].isin(["买入", "强烈买入"])
    ].copy()
    if buy_candidates.empty:
        return pd.DataFrame()

    # 按综合信号排序，取前 max_positions 个
    buy_candidates = buy_candidates.sort_values(
        "combined_signal", ascending=False
    ).head(max_positions)

    n = len(buy_candidates)
    if n == 0:
        return pd.DataFrame()

    capital_per_pos = total_capital / n
    plans = []

    for _, row in buy_candidates.iterrows():
        ticker = row["ticker"]
        price = float(row["last_price"])
        if price <= 0:
            continue

        shares = int(capital_per_pos // price)
        if shares <= 0:
            continue

        notional = shares * price
        plans.append(
            {
                "ticker": ticker,
                "action": "BUY",
                "last_price": price,
                "shares": shares,
                "notional": notional,
                "combined_signal": float(row.get("combined_signal", np.nan)),
            }
        )

    if not plans:
        return pd.DataFrame()

    df = pd.DataFrame(plans)
    df = df.sort_values("combined_signal", ascending=False).reset_index(drop=True)
    return df



"""模拟账户账户模块（阶段 3）

职责：
- 管理模拟账户的现金、持仓、交易日志与权益曲线；
- 提供基于简单 dict 的读写接口，方便与 Streamlit session_state 集成。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any


@dataclass
class AccountState:
    initial_capital: float = 1_000_000.0
    cash: float = 1_000_000.0
    positions: Dict[str, int] | None = None
    equity_history: List[Dict[str, Any]] | None = None
    trade_log: List[Dict[str, Any]] | None = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # 确保默认空结构不为 None
        d["positions"] = d["positions"] or {}
        d["equity_history"] = d["equity_history"] or []
        d["trade_log"] = d["trade_log"] or []
        return d


def ensure_account_dict(
    raw: Dict[str, Any] | None, initial_capital: float = 1_000_000.0
) -> Dict[str, Any]:
    """确保 session_state 中的账户字典存在且结构完整"""
    if not raw:
        acc = AccountState(initial_capital=initial_capital, cash=initial_capital)
        return acc.to_dict()

    # 填补缺失字段
    positions = raw.get("positions") or {}
    equity_history = raw.get("equity_history") or []
    trade_log = raw.get("trade_log") or []
    initial_capital = float(raw.get("initial_capital", initial_capital))
    cash = float(raw.get("cash", initial_capital))

    acc = AccountState(
        initial_capital=initial_capital,
        cash=cash,
        positions=dict(positions),
        equity_history=list(equity_history),
        trade_log=list(trade_log),
    )
    return acc.to_dict()


def compute_equity(account: Dict[str, Any], latest_prices: Dict[str, float]) -> float:
    """基于当前持仓与最新价格计算总权益"""
    cash = float(account.get("cash", 0.0))
    positions: Dict[str, int] = account.get("positions", {}) or {}
    equity_pos = 0.0
    for t, sh in positions.items():
        price = float(latest_prices.get(t, 0.0))
        equity_pos += sh * price
    return cash + equity_pos


def append_equity_history(
    account: Dict[str, Any], equity: float, dt: datetime | None = None
) -> None:
    """向账户的权益历史中追加一条记录"""
    if dt is None:
        dt = datetime.now()
    hist: List[Dict[str, Any]] = account.get("equity_history") or []
    hist.append({"date": dt, "equity": float(equity)})
    account["equity_history"] = hist



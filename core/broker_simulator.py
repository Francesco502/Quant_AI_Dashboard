"""模拟撮合模块（阶段 3）

职责：
- 根据目标持仓与当前持仓差异，生成买卖指令；
- 按给定价格撮合（这里简化为最新收盘价），并更新账户现金与持仓。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Tuple


@dataclass
class Trade:
    ticker: str
    side: str  # BUY / SELL
    shares: int
    price: float

    @property
    def notional(self) -> float:
        return float(self.shares * self.price)

    def to_log_item(self, trade_date: datetime) -> Dict[str, Any]:
        return {
            "日期": trade_date.strftime("%Y-%m-%d"),
            "代码": self.ticker,
            "方向": self.side,
            "数量": self.shares,
            "价格": round(self.price, 4),
            "成交金额": round(self.notional, 2),
        }


def generate_rebalance_trades(
    current_positions: Dict[str, int],
    target_positions: Dict[str, int],
    last_prices: Dict[str, float],
) -> List[Trade]:
    """基于当前持仓与目标持仓生成调仓所需的交易列表"""
    trades: List[Trade] = []

    # 先处理当前已有持仓（不在目标则全平）
    for t, cur_shares in current_positions.items():
        tgt_shares = target_positions.get(t, 0)
        diff = tgt_shares - cur_shares
        price = float(last_prices.get(t, 0.0))
        if diff > 0:
            trades.append(Trade(ticker=t, side="BUY", shares=diff, price=price))
        elif diff < 0:
            trades.append(Trade(ticker=t, side="SELL", shares=-diff, price=price))

    # 再处理新的标的（当前无持仓但目标有）
    for t, tgt_shares in target_positions.items():
        if t in current_positions:
            continue
        if tgt_shares <= 0:
            continue
        price = float(last_prices.get(t, 0.0))
        trades.append(Trade(ticker=t, side="BUY", shares=tgt_shares, price=price))

    return trades


def apply_trades_to_account(
    account: Dict[str, Any],
    trades: List[Trade],
) -> Tuple[bool, str]:
    """将交易列表应用到账户，返回是否成功及失败原因

    - 若资金不足则整体拒绝执行（不进行部分成交），以保持逻辑简单可控。
    """
    if not trades:
        return True, "无交易需要执行"

    cash = float(account.get("cash", 0.0))
    positions: Dict[str, int] = account.get("positions", {}) or {}

    # 试算资金变化
    new_cash = cash
    for tr in trades:
        if tr.side == "BUY":
            new_cash -= tr.notional
        else:
            new_cash += tr.notional

    if new_cash < 0:
        return False, "资金不足，无法在当前初始资金和已有仓位下完成该调仓计划。请减少总资金或持仓数量。"

    # 资金充足则正式更新
    account["cash"] = new_cash
    for tr in trades:
        t = tr.ticker
        sh = tr.shares
        if tr.side == "BUY":
            positions[t] = positions.get(t, 0) + sh
        else:
            positions[t] = positions.get(t, 0) - sh
            if positions[t] <= 0:
                positions.pop(t, None)

    account["positions"] = positions
    return True, "执行成功"



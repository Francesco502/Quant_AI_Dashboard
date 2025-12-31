"""简单模拟交易引擎（阶段 3 + 风险管理集成）

职责：
- 将策略信号（如多资产交易信号表）转换为调仓目标；
- 调用 broker_simulator 生成并执行交易；
- 集成风险检查，确保交易符合风险限制；
- 更新账户状态和交易日志。
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Tuple, Optional

import pandas as pd

from .paper_trading import generate_equal_weight_plan
from .broker_simulator import (
    Trade,
    generate_rebalance_trades,
    apply_trades_to_account,
)
from .account import append_equity_history, compute_equity
from .risk_monitor import RiskMonitor
from .risk_types import RiskAction, RiskCheckResult
from .stop_loss_manager import StopLossManager
from .order_manager import OrderManager
from .order_types import Order, OrderType, OrderSide, Fill
from .slippage_model import SlippageModel, SlippageConfig
from .execution_algorithms import ExecutionAlgorithm, get_execution_algorithm


def apply_equal_weight_rebalance(
    account: Dict[str, Any],
    signal_table: pd.DataFrame,
    data: pd.DataFrame,
    total_capital: float,
    max_positions: int,
    risk_monitor: Optional[RiskMonitor] = None,
    stop_loss_manager: Optional[StopLossManager] = None,
    order_manager: Optional[OrderManager] = None,
    slippage_model: Optional[SlippageModel] = None,
    execution_algorithm: Optional[ExecutionAlgorithm] = None,
) -> Tuple[Dict[str, Any], str]:
    """基于当前信号表与等权配置规则，对账户执行一轮调仓（集成风险检查）

    - 使用 generate_equal_weight_plan 生成目标买入计划（BUY 方向）；
    - 将当前未在计划中的持仓视为目标持仓 0（全平）；
    - 对每个交易进行风险检查；
    - 使用 broker_simulator 生成并应用交易；
    - 更新账户的权益历史与交易日志。

    Args:
        account: 账户字典
        signal_table: 信号表
        data: 价格数据
        total_capital: 总资金
        max_positions: 最大持仓数
        risk_monitor: 风险监控器（可选）
        stop_loss_manager: 止损止盈管理器（可选）

    Returns:
        (账户字典, 执行结果消息)
    """
    if signal_table is None or signal_table.empty:
        return account, "当前无有效信号，未执行调仓。"

    # 1. 生成等权建仓计划（仅包含 BUY 目标）
    plan_df = generate_equal_weight_plan(
        signal_table,
        total_capital=total_capital,
        max_positions=max_positions,
    )
    if plan_df is None or plan_df.empty:
        return account, "当前没有符合条件的买入候选，未执行调仓。"

    target_positions: Dict[str, int] = {
        row["ticker"]: int(row["shares"]) for _, row in plan_df.iterrows()
    }
    current_positions: Dict[str, int] = account.get("positions", {}) or {}

    # 2. 获取最新价格
    last_prices: Dict[str, float] = {}
    for t in set(list(current_positions.keys()) + list(target_positions.keys())):
        if t in signal_table["ticker"].values:
            price = float(
                signal_table.loc[signal_table["ticker"] == t, "last_price"].iloc[0]
            )
        elif t in data.columns:
            price = float(data[t].iloc[-1])
        else:
            price = 0.0
        last_prices[t] = price

    # 3. 根据当前持仓与目标持仓生成交易
    trades: list[Trade] = generate_rebalance_trades(
        current_positions=current_positions,
        target_positions=target_positions,
        last_prices=last_prices,
    )
    if not trades:
        return account, "目标持仓与当前持仓一致，无需调仓。"

    # 3.5. 使用订单管理系统（如果提供）
    if order_manager is not None:
        # 将Trade转换为Order并创建订单
        orders: List[Order] = []
        for trade in trades:
            order = order_manager.create_order(
                symbol=trade.ticker,
                side=OrderSide.BUY if trade.side == "BUY" else OrderSide.SELL,
                quantity=trade.shares,
                order_type=OrderType.MARKET,
                price=last_prices.get(trade.ticker, trade.price),
            )
            orders.append(order)
            order_manager.submit_order(order.order_id)
        
        # 使用执行算法执行订单（如果提供）
        if execution_algorithm is not None:
            all_fills: List[Fill] = []
            for order in orders:
                fills = execution_algorithm.execute(
                    order=order,
                    current_price=last_prices.get(order.symbol, 0),
                    market_data=data[[order.symbol]] if order.symbol in data.columns else None,
                )
                # 应用滑点（如果提供滑点模型）
                if slippage_model is not None:
                    for fill in fills:
                        adjusted_price = slippage_model.apply_slippage(
                            order=order,
                            current_price=fill.price,
                            market_data=data[[order.symbol]] if order.symbol in data.columns else None,
                        )
                        fill.price = adjusted_price
                
                # 添加成交记录到订单管理器
                for fill in fills:
                    order_manager.add_fill(order.order_id, fill)
                    all_fills.append(fill)
            
            # 将Fill转换为Trade（用于后续处理）
            new_trades = []
            for fill in all_fills:
                new_trades.append(Trade(
                    ticker=fill.symbol,
                    side=fill.side.value,
                    shares=fill.quantity,
                    price=fill.price
                ))
            trades = new_trades
        else:
            # 没有执行算法，直接使用原价格（但可以应用滑点）
            if slippage_model is not None:
                for i, trade in enumerate(trades):
                    # 创建临时订单用于滑点计算
                    temp_order = Order(
                        order_id=f"TEMP_{i}",
                        symbol=trade.ticker,
                        side=OrderSide.BUY if trade.side == "BUY" else OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=trade.shares,
                    )
                    adjusted_price = slippage_model.apply_slippage(
                        order=temp_order,
                        current_price=trade.price,
                        market_data=data[[trade.ticker]] if trade.ticker in data.columns else None,
                    )
                    trade.price = adjusted_price

    # 4. 风险检查（如果提供了风险监控器）
    rejected_trades: list[Tuple[Trade, str]] = []
    if risk_monitor is not None:
        approved_trades: list[Trade] = []
        
        for trade in trades:
            order = {
                "symbol": trade.ticker,
                "side": trade.side,
                "quantity": trade.shares if trade.side == "BUY" else -trade.shares,
                "price": trade.price
            }
            
            result: RiskCheckResult = risk_monitor.check_order_risk(
                order, account, last_prices
            )
            
            if result.action == RiskAction.EMERGENCY_STOP:
                return account, f"触发紧急停止：{result.message}。所有交易已中止。"
            elif result.action == RiskAction.REJECT:
                rejected_trades.append((trade, result.message))
                continue
            elif result.action == RiskAction.WARN:
                # 警告但允许执行
                approved_trades.append(trade)
            else:
                # ALLOW
                approved_trades.append(trade)
        
        # 更新交易列表为通过风险检查的交易
        trades = approved_trades
        
        # 如果有被拒绝的交易，记录信息
        if rejected_trades:
            rejected_info = "; ".join([f"{t[0].ticker}: {t[1]}" for t in rejected_trades])
            if not trades:
                return account, f"所有交易均未通过风险检查：{rejected_info}"

    # 5. 试算并应用交易到账户
    ok, msg = apply_trades_to_account(account, trades)
    if not ok:
        return account, msg

    # 6. 为新持仓设置止损止盈（如果提供了止损止盈管理器）
    if stop_loss_manager is not None:
        for trade in trades:
            if trade.side == "BUY" and trade.shares > 0:
                # 为新买入的持仓设置止损（5%止损，10%止盈）
                stop_loss_manager.set_stop_loss(
                    symbol=trade.ticker,
                    entry_price=trade.price,
                    stop_type="percentage",
                    stop_percentage=0.05
                )
                stop_loss_manager.set_take_profit(
                    symbol=trade.ticker,
                    entry_price=trade.price,
                    take_profit_type="percentage",
                    take_profit_percentage=0.1
                )

    # 7. 更新交易日志与权益历史
    trade_date = (
        data.index[-1]
        if isinstance(data.index, pd.DatetimeIndex) and len(data.index) > 0
        else datetime.now()
    )
    trade_log = account.get("trade_log") or []
    for tr in trades:
        trade_log.append(tr.to_log_item(trade_date))
    account["trade_log"] = trade_log

    # 权益曲线
    # 构建当前最新价格字典
    latest_prices: Dict[str, float] = {}
    for t in account.get("positions", {}).keys():
        if t in data.columns:
            latest_prices[t] = float(data[t].iloc[-1])
    equity = compute_equity(account, latest_prices)
    append_equity_history(account, equity, trade_date)

    risk_info = ""
    if risk_monitor is not None and rejected_trades:
        risk_info = f"（{len(rejected_trades)} 笔交易因风险检查被拒绝）"

    return account, f"本次调仓共执行 {len(trades)} 笔交易。{risk_info}"



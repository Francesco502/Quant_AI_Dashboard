"""
统一测试数据管理模块

提供可复用的测试数据和工具函数
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


def generate_price_data(
    tickers: List[str] = None,
    n_days: int = 252,
    start_date: str = None,
    trend: float = 0.0002,
    volatility: float = 0.02,
    seed: int = None
) -> pd.DataFrame:
    """
    生成价格数据（OHLCV）

    Args:
        tickers: 股票代码列表
        n_days: 天数
        start_date: 开始日期 (YYYY-MM-DD)
        trend: 日度趋势
        volatility: 日度波动率
        seed: 随机种子

    Returns:
        DataFrame: 价格数据 (open, high, low, close, volume)
    """
    if seed is not None:
        np.random.seed(seed)

    if tickers is None:
        tickers = ["600519", "000001", "AAPL"]

    if start_date is None:
        start_date = "2025-01-01"

    dates = pd.bdate_range(start=start_date, periods=n_days)

    data = {}
    for ticker in tickers:
        base_price = 100 + np.random.randn() * 20
        returns = np.random.normal(trend, volatility, n_days)
        prices = base_price * (1 + pd.Series(returns)).cumprod()

        open_prices = prices[:-1].values
        close_prices = prices[1:].values
        high_prices = np.maximum(open_prices, close_prices) * (1 + np.random.rand(n_days-1) * 0.01)
        low_prices = np.minimum(open_prices, close_prices) * (1 - np.random.rand(n_days-1) * 0.01)
        base_volume = 1000000 + np.random.randn() * 500000
        volumes = np.maximum(base_volume * (1 + np.random.randn(n_days-1) * 0.5), 100000).astype(int)

        data[ticker] = pd.DataFrame({
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes
        }, index=dates[1:])

    result = pd.concat(
        {ticker: df for ticker, df in data.items()},
        axis=1,
        keys=[ticker for ticker in data.keys()]
    )

    return result


def generate_ohlcv_data(
    ticker: str = "600519",
    n_days: int = 252,
    seed: int = None
) -> pd.DataFrame:
    """
    生成单个股票的OHLCV数据

    Args:
        ticker: 股票代码
        n_days: 天数
        seed: 随机种子

    Returns:
        DataFrame: OHLCV数据
    """
    if seed is not None:
        np.random.seed(seed)

    dates = pd.bdate_range(start="2025-01-01", periods=n_days)
    base_price = 100 + np.random.randn() * 20
    returns = np.random.normal(0.0002, 0.02, n_days)
    prices = base_price * (1 + pd.Series(returns)).cumprod()

    data = pd.DataFrame({
        "open": prices[:-1].values,
        "high": np.maximum(prices[:-1].values, prices[1:].values) * (1 + np.random.rand(n_days-1) * 0.01),
        "low": np.minimum(prices[:-1].values, prices[1:].values) * (1 - np.random.rand(n_days-1) * 0.01),
        "close": prices[1:].values,
        "volume": np.maximum(1000000 + np.random.randn(n_days-1) * 500000, 100000).astype(int)
    }, index=dates[1:])

    return data


def generate_equity_curve(
    n_points: int = 252,
    initial_equity: float = 100000,
    trend: float = 0.001,
    volatility: float = 0.015,
    seed: int = None
) -> List[Dict[str, Any]]:
    """
    生成权益曲线数据

    Args:
        n_points: 点数
        initial_equity: 初始权益
        trend: 日度趋势
        volatility: 日度波动率
        seed: 随机种子

    Returns:
        Equity curve list of dicts
    """
    if seed is not None:
        np.random.seed(seed)

    equity = initial_equity
    curve = []

    for i in range(n_points):
        date = pd.Timestamp("2025-01-01") + pd.Timedelta(days=i)
        cash = equity * (0.5 + 0.3 * np.sin(i / 30))

        curve.append({
            "date": date.strftime("%Y-%m-%d"),
            "equity": equity,
            "cash": cash
        })

        ret = np.random.normal(trend, volatility)
        equity = equity * (1 + ret)

    return curve


def generate_trades(
    n_trades: int = 50,
    tickers: List[str] = None,
    seed: int = None
) -> List[Dict[str, Any]]:
    """
    生成交易记录

    Args:
        n_trades: 交易数量
        tickers: 股票代码列表
        seed: 随机种子

    Returns:
        Trades list of dicts
    """
    if seed is not None:
        np.random.seed(seed)

    if tickers is None:
        tickers = ["600519", "000001", "AAPL", "MSFT", "GOOGL"]

    actions = ["买入", "卖出"]

    trades = []
    for i in range(n_trades):
        date = pd.Timestamp("2025-01-01") + pd.Timedelta(days=np.random.randint(0, 200))
        ticker = np.random.choice(tickers)
        action = np.random.choice(actions)
        shares = np.random.randint(10, 500) * 100
        price = 50 + np.random.rand() * 200

        trades.append({
            "date": date.strftime("%Y-%m-%d"),
            "ticker": ticker,
            "action": action,
            "shares": shares,
            "price": round(price, 2),
            "cost": round(price * shares * 1.0018, 2)
        })

    return trades


def generate_risk_events(
    n_events: int = 10,
    seed: int = None
) -> List[Dict[str, Any]]:
    """
    生成风险事件记录

    Args:
        n_events: 事件数量
        seed: 随机种子

    Returns:
        Risk events list of dicts
    """
    if seed is not None:
        np.random.seed(seed)

    event_types = ["order_risk_check", "loss_risk", "concentration_risk", "liquidity_risk"]
    severities = ["INFO", "WARNING", "ERROR", "CRITICAL"]

    events = []
    for i in range(n_events):
        date = pd.Timestamp("2025-01-01") + pd.Timedelta(days=np.random.randint(0, 100))
        event_type = np.random.choice(event_types)
        severity = np.random.choice(severities, p=[0.2, 0.3, 0.3, 0.2])

        events.append({
            "event_id": f"{event_type}_{date.timestamp()}",
            "timestamp": date.isoformat(),
            "event_type": event_type,
            "severity": severity,
            "message": f"测试{event_type}事件",
            "symbol": np.random.choice(["600519", "000001", "AAPL"]),
            "details": {"value": np.random.rand()}
        })

    return events


def create_test_account(
    initial_capital: float = 1000000,
    positions: Dict[str, int] = None,
    cash: float = None
) -> Dict[str, Any]:
    """
    创建测试账户

    Args:
        initial_capital: 初始资金
        positions: 持仓字典
        cash: 现金

    Returns:
        账户字典
    """
    return {
        "account_id": "test_account_001",
        "user_id": 1,
        "initial_capital": initial_capital,
        "cash": cash if cash is not None else initial_capital,
        "positions": positions or {},
        "equity_history": [],
        "trade_log": [],
        "created_at": datetime.now().isoformat()
    }


def create_portfolio_analyzer_data(
    tickers: List[str] = None,
    n_days: int = 252,
    seed: int = None
) -> Dict[str, Any]:
    """
    创建 PortfolioAnalyzer 测试数据

    Returns:
        Dict with price_data, expected_weights, etc.
    """
    if tickers is None:
        tickers = ["600519", "000001", "AAPL"]

    price_data = generate_price_data(
        tickers=tickers,
        n_days=n_days,
        seed=seed
    )

    weights = [1.0 / len(tickers)] * len(tickers)

    return {
        "price_data": price_data,
        "tickers": tickers,
        "weights": weights
    }


def create_backtest_engine_data(
    tickers: List[str] = None,
    n_days: int = 252,
    seed: int = None
) -> Dict[str, Any]:
    """
    创建 BacktestEngine 测试数据

    Returns:
        Dict with price_data, strategy, etc.
    """
    if tickers is None:
        tickers = ["600519", "000001"]

    price_data = generate_price_data(
        tickers=tickers,
        n_days=n_days,
        seed=seed
    )

    def buy_and_hold_strategy(df, params):
        return {ticker: 100 for ticker in df.columns}

    return {
        "price_data": price_data,
        "strategy_func": buy_and_hold_strategy,
        "strategy_params": {}
    }


def create_signal_data(
    n_signals: int = 10,
    seed: int = None
) -> pd.DataFrame:
    """
    创建信号数据

    Args:
        n_signals: 信号数量
        seed: 随机种子

    Returns:
        DataFrame with signal data
    """
    if seed is not None:
        np.random.seed(seed)

    tickers = ["600519", "000001", "AAPL", "MSFT", "GOOGL"]
    actions = ["买入", "卖出", "观望"]

    data = {
        "ticker": np.random.choice(tickers, n_signals),
        "action": np.random.choice(actions, n_signals, p=[0.4, 0.2, 0.4]),
        "combined_signal": np.random.uniform(0, 1, n_signals),
        "last_price": np.random.uniform(50, 200, n_signals),
        "signal_date": [datetime.now().strftime("%Y-%m-%d")] * n_signals,
    }

    return pd.DataFrame(data)


def create_order_data(
    n_orders: int = 10,
    seed: int = None
) -> List[Dict[str, Any]]:
    """
    创建订单数据

    Args:
        n_orders: 订单数量
        seed: 随机种子

    Returns:
        Orders list of dicts
    """
    if seed is not None:
        np.random.seed(seed)

    sides = ["BUY", "SELL"]
    order_types = ["MARKET", "LIMIT", "STOP_LOSS", "TAKE_PROFIT"]
    statuses = ["PENDING", "SUBMITTED", "FILLED", "PARTIALLY_FILLED", "CANCELED", "REJECTED"]

    orders = []
    for i in range(n_orders):
        orders.append({
            "order_id": f"ORD_{i}_{datetime.now().timestamp()}",
            "symbol": np.random.choice(["600519", "000001", "AAPL", "MSFT"]),
            "side": np.random.choice(sides),
            "order_type": np.random.choice(order_types),
            "quantity": np.random.randint(10, 500) * 100,
            "price": round(np.random.uniform(50, 200), 2),
            "status": np.random.choice(statuses),
            "timestamp": datetime.now().isoformat()
        })

    return orders


def create_risk_check_result(
    action: str = "ALLOW",
    risk_level: str = "LOW",
    violations: List[str] = None
) -> Dict[str, Any]:
    """
    创建风险检查结果

    Args:
        action: 风险动作
        risk_level: 风险等级
        violations: 违规列表

    Returns:
        Risk check result dict
    """
    return {
        "action": action,
        "risk_level": risk_level,
        "message": "; ".join(violations) if violations else "风险检查通过",
        "violations": violations or [],
        "metadata": {}
    }


def get_test_data_path() -> str:
    """获取测试数据目录路径"""
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

"""Performance analysis helpers (legacy compatibility module)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class PerformanceMetrics:
    total_return: float
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    var_95: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    total_trades: int
    start_date: str
    end_date: str
    trading_days: int


class PerformanceAnalyzer:
    TRADING_DAYS_PER_YEAR = 252

    def __init__(self, initial_capital: float = 100000) -> None:
        self.initial_capital = float(initial_capital)
        self.equity_curve: List[Dict[str, Any]] = []
        self.trades: List[Dict[str, Any]] = []

    def add_equity_point(self, date: datetime | str, equity: float, cash: float = 0) -> None:
        self.equity_curve.append({"date": pd.to_datetime(date), "equity": float(equity), "cash": float(cash)})

    def add_trade(
        self,
        date: datetime | str,
        ticker: str,
        action: str,
        shares: int,
        price: float,
        cost: float = 0,
    ) -> None:
        self.trades.append(
            {
                "date": pd.to_datetime(date),
                "ticker": str(ticker),
                "action": str(action).upper(),
                "shares": int(shares),
                "price": float(price),
                "cost": float(cost),
            }
        )

    def calculate_metrics(self) -> PerformanceMetrics:
        equity_df = self.get_equity_dataframe()
        trades_df = self.get_trades_dataframe()

        if equity_df.empty:
            return self._default_metrics()

        equity_df = equity_df.sort_index()
        equity = equity_df["equity"].astype(float)
        returns = equity.pct_change().dropna()

        total_return = float(equity.iloc[-1] / self.initial_capital - 1.0) if self.initial_capital > 0 else 0.0
        trading_days = int(len(returns))

        annual_return = self._annualize_return(total_return, trading_days)
        annual_volatility = float(returns.std() * sqrt(self.TRADING_DAYS_PER_YEAR)) if not returns.empty else 0.0
        sharpe_ratio = self._calculate_sharpe(returns)
        sortino_ratio = self._calculate_sortino(returns)

        drawdown_stats = self._calculate_drawdown(equity)
        max_drawdown = float(drawdown_stats["max_drawdown"])
        max_drawdown_duration = int(drawdown_stats["max_duration"])

        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown < 0 else 0.0
        var_95 = self._calculate_var(returns)
        win_rate, profit_factor = self._calculate_trade_metrics(trades_df)

        start_date = pd.to_datetime(equity_df.index.min()).strftime("%Y-%m-%d")
        end_date = pd.to_datetime(equity_df.index.max()).strftime("%Y-%m-%d")

        return PerformanceMetrics(
            total_return=float(total_return),
            annual_return=float(annual_return),
            annual_volatility=float(annual_volatility),
            sharpe_ratio=float(sharpe_ratio),
            sortino_ratio=float(sortino_ratio),
            calmar_ratio=float(calmar_ratio),
            max_drawdown=float(max_drawdown),
            var_95=float(var_95),
            max_drawdown_duration=max_drawdown_duration,
            win_rate=float(win_rate),
            profit_factor=float(profit_factor),
            total_trades=int(len(trades_df)),
            start_date=start_date,
            end_date=end_date,
            trading_days=trading_days,
        )

    def get_equity_dataframe(self) -> pd.DataFrame:
        if not self.equity_curve:
            return pd.DataFrame()
        df = pd.DataFrame(self.equity_curve)
        return df.set_index("date")

    def get_trades_dataframe(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame(self.trades)

    def _annualize_return(self, total_return: float, trading_days: int) -> float:
        if trading_days <= 0:
            return 0.0
        return (1.0 + total_return) ** (self.TRADING_DAYS_PER_YEAR / trading_days) - 1.0

    def _calculate_sharpe(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        if returns.empty:
            return 0.0
        std = float(returns.std())
        if std == 0:
            return 0.0
        excess_returns = returns - risk_free_rate / self.TRADING_DAYS_PER_YEAR
        return float(excess_returns.mean() / std * sqrt(self.TRADING_DAYS_PER_YEAR))

    def _calculate_sortino(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        if returns.empty:
            return 0.0
        downside = returns[returns < 0]
        std = float(downside.std()) if not downside.empty else 0.0
        if std == 0:
            return 0.0
        excess_returns = returns - risk_free_rate / self.TRADING_DAYS_PER_YEAR
        return float(excess_returns.mean() / std * sqrt(self.TRADING_DAYS_PER_YEAR))

    def _calculate_drawdown(self, equity: pd.Series) -> Dict[str, Any]:
        if equity.empty:
            return {"max_drawdown": 0.0, "max_duration": 0}

        cumulative = equity / float(equity.iloc[0]) if float(equity.iloc[0]) != 0 else pd.Series(1.0, index=equity.index)
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max.replace(0, np.nan)
        drawdown = drawdown.fillna(0.0)

        max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

        max_duration = 0
        current_duration = 0
        for dd in drawdown:
            if dd < 0:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        return {"max_drawdown": max_drawdown, "max_duration": int(max_duration)}

    def _calculate_var(self, returns: pd.Series, confidence: float = 0.95) -> float:
        if returns.empty:
            return 0.0
        return float(np.percentile(returns.values, (1 - confidence) * 100))

    def _calculate_trade_metrics(self, trades_df: pd.DataFrame) -> Tuple[float, float]:
        if trades_df.empty:
            return 0.0, 1.0

        trades_df = trades_df.sort_values("date")
        buy_lots: Dict[str, List[Tuple[int, float]]] = {}
        closed_trade_pnls: List[float] = []

        for _, trade in trades_df.iterrows():
            ticker = str(trade.get("ticker", ""))
            action = str(trade.get("action", "")).upper()
            shares = int(trade.get("shares", 0) or 0)
            price = float(trade.get("price", 0.0) or 0.0)
            cost = float(trade.get("cost", 0.0) or 0.0)

            if shares <= 0 or not ticker:
                continue

            if action == "BUY":
                per_share_cost = price + cost / max(shares, 1)
                buy_lots.setdefault(ticker, []).append((shares, per_share_cost))
                continue

            if action != "SELL":
                continue

            remaining = shares
            sell_price = price - cost / max(shares, 1)
            lots = buy_lots.get(ticker, [])

            while remaining > 0 and lots:
                lot_shares, lot_cost = lots[0]
                matched = min(remaining, lot_shares)
                pnl = (sell_price - lot_cost) * matched
                closed_trade_pnls.append(float(pnl))
                lot_shares -= matched
                remaining -= matched
                if lot_shares == 0:
                    lots.pop(0)
                else:
                    lots[0] = (lot_shares, lot_cost)

        if not closed_trade_pnls:
            return 0.0, 1.0

        wins = [x for x in closed_trade_pnls if x > 0]
        losses = [x for x in closed_trade_pnls if x < 0]
        win_rate = len(wins) / len(closed_trade_pnls)

        gross_profit = float(sum(wins))
        gross_loss = float(abs(sum(losses)))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1.0
        return float(win_rate), float(profit_factor)

    def _default_metrics(self) -> PerformanceMetrics:
        today = datetime.now().strftime("%Y-%m-%d")
        return PerformanceMetrics(
            total_return=0.0,
            annual_return=0.0,
            annual_volatility=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            var_95=0.0,
            max_drawdown_duration=0,
            win_rate=0.0,
            profit_factor=1.0,
            total_trades=0,
            start_date=today,
            end_date=today,
            trading_days=0,
        )


def analyze_backtest_results(
    equity_curve: List[Dict[str, Any]],
    trades: List[Dict[str, Any]],
    initial_capital: float = 100000,
) -> Dict[str, Any]:
    analyzer = PerformanceAnalyzer(initial_capital)

    for point in equity_curve:
        analyzer.add_equity_point(
            point.get("date", datetime.now()),
            float(point.get("equity", initial_capital)),
            float(point.get("cash", 0)),
        )

    for trade in trades:
        analyzer.add_trade(
            trade.get("date", datetime.now()),
            str(trade.get("ticker", "")),
            str(trade.get("action", "")),
            int(trade.get("shares", 0) or 0),
            float(trade.get("price", 0.0) or 0.0),
            float(trade.get("cost", 0.0) or 0.0),
        )

    metrics = analyzer.calculate_metrics()
    return {
        "metrics": metrics.__dict__,
        "equity_curve": analyzer.get_equity_dataframe().reset_index().to_dict("records"),
        "trades": analyzer.get_trades_dataframe().to_dict("records"),
        "summary": {
            "total_return": f"{metrics.total_return * 100:.2f}%",
            "annual_return": f"{metrics.annual_return * 100:.2f}%",
            "annual_volatility": f"{metrics.annual_volatility * 100:.2f}%",
            "sharpe_ratio": f"{metrics.sharpe_ratio:.2f}",
            "max_drawdown": f"{metrics.max_drawdown * 100:.2f}%",
            "win_rate": f"{metrics.win_rate * 100:.2f}%",
            "total_trades": metrics.total_trades,
        },
    }


def compare_strategies(
    strategy_results: Dict[str, Dict[str, Any]],
    initial_capital: float = 100000,
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    for strategy_name, data in strategy_results.items():
        analysis = analyze_backtest_results(
            equity_curve=data.get("equity_curve", []),
            trades=data.get("trades", []),
            initial_capital=initial_capital,
        )
        metrics = analysis["metrics"]
        rows.append(
            {
                "strategy_name": strategy_name,
                "total_return": metrics["total_return"],
                "annual_return": metrics["annual_return"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown": metrics["max_drawdown"],
                "win_rate": metrics["win_rate"],
                "total_trades": metrics["total_trades"],
            }
        )

    return pd.DataFrame(rows)

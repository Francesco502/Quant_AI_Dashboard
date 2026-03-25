"""Legacy simple backtest helpers.

This module is retained for compatibility with older scripts, but its
performance metrics should remain numerically correct when called.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

import numpy as np
import pandas as pd


class SimpleBacktest:
    """A minimal long-only backtest engine."""

    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.positions: Dict[str, int] = {}
        self.cash = initial_capital
        self.equity_curve = []
        self.trades = []

    def run_backtest(
        self,
        price_data: pd.DataFrame,
        signals: pd.DataFrame,
        commission: float = 0.001,
    ) -> Dict:
        """Run a simple long-only backtest."""
        dates = price_data.index
        tickers = price_data.columns.tolist()

        for date in dates:
            portfolio_value = self.cash
            for ticker in tickers:
                if ticker in self.positions:
                    portfolio_value += self.positions[ticker] * price_data.loc[date, ticker]

            self.equity_curve.append(
                {
                    "date": date,
                    "equity": portfolio_value,
                    "cash": self.cash,
                    "positions_value": portfolio_value - self.cash,
                }
            )

            for ticker in tickers:
                if ticker not in signals.columns:
                    continue

                signal = signals.loc[date, ticker] if date in signals.index else 0
                current_price = price_data.loc[date, ticker]

                if signal == 1:
                    self._buy(ticker, current_price, commission, date)
                elif signal == -1:
                    self._sell(ticker, current_price, commission, date)

        return self._calculate_performance()

    def _buy(self, ticker: str, price: float, commission: float, date: datetime):
        target_value = self.cash * 0.5
        shares = int(target_value / (price * (1 + commission)))
        cost = shares * price * (1 + commission)

        if cost <= self.cash:
            if ticker not in self.positions:
                self.positions[ticker] = 0
            self.positions[ticker] += shares
            self.cash -= cost

            self.trades.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "action": "buy",
                    "shares": shares,
                    "price": price,
                    "cost": cost,
                }
            )

    def _sell(self, ticker: str, price: float, commission: float, date: datetime):
        if ticker in self.positions and self.positions[ticker] > 0:
            shares = self.positions[ticker]
            proceeds = shares * price * (1 - commission)

            self.positions[ticker] = 0
            self.cash += proceeds

            self.trades.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "action": "sell",
                    "shares": shares,
                    "price": price,
                    "proceeds": proceeds,
                }
            )

    def _calculate_win_rate(self) -> float:
        inventory_cost: Dict[str, float] = {}
        inventory_shares: Dict[str, int] = {}
        winning_trades = 0
        closed_trades = 0

        for trade in self.trades:
            ticker = str(trade.get("ticker") or "")
            action = str(trade.get("action") or "").lower()
            shares = int(trade.get("shares") or 0)
            if shares <= 0 or not ticker:
                continue

            if action == "buy":
                inventory_shares[ticker] = inventory_shares.get(ticker, 0) + shares
                inventory_cost[ticker] = inventory_cost.get(ticker, 0.0) + float(trade.get("cost") or 0.0)
                continue

            if action != "sell":
                continue

            held_shares = inventory_shares.get(ticker, 0)
            held_cost = inventory_cost.get(ticker, 0.0)
            if held_shares <= 0 or held_cost <= 0:
                continue

            avg_cost = held_cost / held_shares
            pnl = float(trade.get("proceeds") or 0.0) - (avg_cost * shares)
            closed_trades += 1
            if pnl > 0:
                winning_trades += 1

            inventory_shares[ticker] = max(0, held_shares - shares)
            inventory_cost[ticker] = max(0.0, held_cost - (avg_cost * shares))

        return winning_trades / closed_trades if closed_trades > 0 else 0.0

    def _calculate_performance(self) -> Dict:
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.set_index("date", inplace=True)

        equity_df["returns"] = equity_df["equity"].pct_change()
        equity_df["cumulative_returns"] = (1 + equity_df["returns"]).cumprod() - 1

        total_return = (equity_df["equity"].iloc[-1] / self.initial_capital) - 1
        days = (equity_df.index[-1] - equity_df.index[0]).days
        annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
        annual_vol = equity_df["returns"].std() * np.sqrt(252)
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0

        cumulative = equity_df["equity"] / self.initial_capital
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        win_rate = self._calculate_win_rate() if self.trades else 0

        return {
            "equity_curve": equity_df,
            "total_return": total_return,
            "annual_return": annual_return,
            "annual_volatility": annual_vol,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "total_trades": len(self.trades),
            "final_equity": equity_df["equity"].iloc[-1],
        }


def simple_ma_strategy(price_data: pd.Series, short_window: int = 20, long_window: int = 50) -> pd.Series:
    """Simple moving-average crossover signals."""
    short_ma = price_data.rolling(window=short_window).mean()
    long_ma = price_data.rolling(window=long_window).mean()

    signals = pd.Series(0, index=price_data.index)
    signals[short_ma > long_ma] = 1
    signals[short_ma < long_ma] = -1
    return signals


def run_backtest(
    price_data: pd.DataFrame,
    signals: pd.DataFrame,
    initial_capital: float = 100000,
    commission: float = 0.001,
) -> Dict:
    """Compatibility wrapper for the legacy module-level API."""
    engine = SimpleBacktest(initial_capital=initial_capital)
    return engine.run_backtest(price_data=price_data, signals=signals, commission=commission)

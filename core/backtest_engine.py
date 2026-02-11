import pandas as pd
import numpy as np
from typing import Dict, Any, Callable, List, Optional
from datetime import datetime
import logging

from core.brokers.backtest_broker import BacktestBroker
from core.trading_engine import TradingEngine
from core.order_types import Order, OrderStatus

logger = logging.getLogger(__name__)

class BacktestEngine:
    """
    Event-Driven Backtest Engine.
    Uses TradingEngine and BacktestBroker to simulate realistic trading.
    """
    def __init__(self, initial_capital: float = 100000.0):
        self.broker = BacktestBroker(initial_capital)
        self.trading_engine = TradingEngine(self.broker)
        self.equity_curve = []
        
    def run(self, 
            price_data: pd.DataFrame, 
            strategy_func: Callable[[pd.DataFrame, Dict], Dict[str, int]], 
            strategy_params: Dict = None):
        """
        Run backtest.
        
        Args:
            price_data: DataFrame with index as datetime, columns as tickers (Close price).
            strategy_func: Function that takes (current_history_data, params) and returns target_positions {ticker: shares}.
            strategy_params: Parameters for the strategy.
        """
        if strategy_params is None:
            strategy_params = {}
            
        dates = price_data.index.sort_values()
        tickers = price_data.columns.tolist()
        
        logger.info(f"Starting backtest from {dates[0]} to {dates[-1]}")
        
        for date in dates:
            # 1. Update Time
            self.broker.set_time(date)
            
            # 2. Get Current Prices
            # Assuming price_data contains Close prices
            current_prices = {ticker: float(price_data.loc[date, ticker]) for ticker in tickers if not pd.isna(price_data.loc[date, ticker])}
            
            # 3. Run Strategy
            # Pass data up to current date
            current_history = price_data.loc[:date]
            target_positions = strategy_func(current_history, strategy_params)
            
            # 4. Execute Rebalance via TradingEngine
            # This generates orders and places them in the broker (status=SUBMITTED)
            self.trading_engine.execute_rebalance(target_positions, current_prices)
            
            # 5. Match Orders (Simulate Execution)
            # Match immediately against current close prices
            self.broker.match_orders(current_prices)
            
            # 6. Record Performance
            account_info = self.broker.get_account_info()
            self.equity_curve.append({
                "date": date,
                "equity": account_info["equity"],
                "cash": account_info["cash"]
            })
            
        return self._calculate_metrics()

    def _calculate_metrics(self) -> Dict:
        if not self.equity_curve:
            return {}
            
        df = pd.DataFrame(self.equity_curve).set_index("date")
        df["returns"] = df["equity"].pct_change().fillna(0)
        
        total_return = (df["equity"].iloc[-1] / df["equity"].iloc[0]) - 1
        volatility = df["returns"].std() * np.sqrt(252)
        sharpe = (df["returns"].mean() * 252) / volatility if volatility > 0 else 0
        
        # Drawdown
        cum_max = df["equity"].cummax()
        drawdown = (df["equity"] - cum_max) / cum_max
        max_drawdown = drawdown.min()
        
        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "volatility": volatility,
            "equity_curve": df,
            "trade_history": self.broker.get_history()
        }

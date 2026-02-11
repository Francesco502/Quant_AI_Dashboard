import pandas as pd
import numpy as np
import sys
import os
sys.path.append(os.getcwd())
from core.backtest_engine import BacktestEngine
import logging

# Configure logging
logging.basicConfig(level=logging.WARNING)

# 1. Generate Dummy Data
dates = pd.date_range(start="2023-01-01", periods=200)
np.random.seed(42)
price_data = pd.DataFrame({
    "AAPL": 100 + np.cumsum(np.random.randn(200)),
    "GOOG": 100 + np.cumsum(np.random.randn(200))
}, index=dates)

# 2. Define Strategy
def sma_strategy(history, params):
    short_window = params.get("short", 10)
    long_window = params.get("long", 30)
    
    positions = {}
    
    for ticker in history.columns:
        if len(history) < long_window:
            continue
            
        prices = history[ticker]
        short_ma = prices.tail(short_window).mean()
        long_ma = prices.tail(long_window).mean()
        current_price = prices.iloc[-1]
        
        # Simple Logic: Hold 100 shares if Short > Long
        if short_ma > long_ma:
            positions[ticker] = 100
        else:
            positions[ticker] = 0
            
    return positions

# 3. Run Backtest
print("Initializing Backtest Engine...")
engine = BacktestEngine(initial_capital=100000)
print("Running Backtest...")
results = engine.run(price_data, sma_strategy, {"short": 10, "long": 30})

print("\n=== Backtest Results ===")
results_str = f"""
Total Return: {results['total_return']:.2%}
Sharpe Ratio: {results['sharpe_ratio']:.2f}
Max Drawdown: {results['max_drawdown']:.2%}
Trades Count: {len(results.get('trade_history', []))}
"""
print(results_str)

with open("phase4_results.log", "w", encoding="utf-8") as f:
    f.write(results_str)

from core.optimization import StrategyOptimizer

# ... (Previous Backtest Code) ...

# 4. Run Optimization
print("\n=== Running Optimization ===")
optimizer = StrategyOptimizer(price_data, sma_strategy, initial_capital=100000)
opt_results = optimizer.grid_search(
    param_grid={
        "short": [5, 10, 15],
        "long": [20, 30, 50]
    },
    metric="sharpe_ratio"
)

print(f"Best Params: {opt_results['best_params']}")
print(f"Best Sharpe: {opt_results['best_score']:.2f}")

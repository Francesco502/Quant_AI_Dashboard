import itertools
import pandas as pd
from typing import Dict, List, Callable, Any
import logging
from core.backtest_engine import BacktestEngine

logger = logging.getLogger(__name__)

class StrategyOptimizer:
    def __init__(self, price_data: pd.DataFrame, strategy_func: Callable, initial_capital: float = 100000.0):
        self.price_data = price_data
        self.strategy_func = strategy_func
        self.initial_capital = initial_capital

    def grid_search(self, param_grid: Dict[str, List[Any]], metric: str = "sharpe_ratio") -> Dict:
        """
        Run Grid Search optimization.
        
        Args:
            param_grid: Dict of parameter names to lists of values. e.g. {'short': [5, 10], 'long': [20, 50]}
            metric: Metric to optimize (sharpe_ratio, total_return, max_drawdown)
            
        Returns:
            Dict with 'best_params', 'best_score', 'results'
        """
        keys = param_grid.keys()
        values = param_grid.values()
        combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
        
        logger.info(f"Starting Grid Search with {len(combinations)} combinations...")
        
        results = []
        best_score = -float('inf')
        best_params = None
        
        # Sequential execution
        for i, params in enumerate(combinations):
            try:
                logger.info(f"Testing combination {i+1}/{len(combinations)}: {params}")
                engine = BacktestEngine(self.initial_capital)
                res = engine.run(self.price_data, self.strategy_func, params)
                score = res.get(metric, -float('inf'))
                
                # If metric is max_drawdown, we usually want to minimize magnitude (closer to 0)
                # But typically max_drawdown is negative. So maximizing it (closer to 0) is correct.
                # If user wants to minimize volatility, they should pass -volatility or handle it.
                
                results.append({
                    "params": params,
                    "metrics": res
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    
            except Exception as e:
                logger.error(f"Optimization failed for {params}: {e}")
                
        return {
            "best_params": best_params,
            "best_score": best_score,
            "all_results": results
        }

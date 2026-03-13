import pandas as pd
import numpy as np
from typing import Dict, Any, Callable, List, Optional, Tuple
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.brokers.backtest_broker import BacktestBroker
from core.trading_engine import TradingEngine
from core.order_types import Order, OrderStatus

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Event-Driven Backtest Engine.
    Uses TradingEngine and BacktestBroker to simulate realistic trading.

    v1.2.0 新增：
    - 多策略组合回测
    - 基准指数对比
    - 参数优化支持
    """
    def __init__(self, initial_capital: float = 100000.0, fees: Dict = None):
        """
        初始化回测引擎

        Args:
            initial_capital: 初始资本
            fees: 交易费用配置 {stamp_duty: 0.001, commission: 0.0003, slippage: 0.0005}
        """
        self.initial_capital = initial_capital
        self.fees = fees or {
            'stamp_duty': 0.001,      # 印花税 0.1%
            'commission': 0.0003,     # 佣金 0.03%
            'slippage': 0.0005        # 滑点 0.05%
        }
        self.broker = BacktestBroker(
            initial_capital=initial_capital,
            commission_rate=float(self.fees.get("commission", 0.0003)),
            stamp_duty_rate=float(self.fees.get("stamp_duty", 0.001)),
            base_slippage_bps=float(self.fees.get("slippage", 0.0005)) * 10000.0,
        )
        self.trading_engine = TradingEngine(self.broker)
        self.equity_curve = []
        self.positions_history = []  # 持仓历史

    def run(
        self,
        price_data: pd.DataFrame,
        strategy_func: Callable[[pd.DataFrame, Dict], Dict[str, int]],
        strategy_params: Dict = None
    ) -> Dict:
        """
        Run backtest.

        Args:
            price_data: DataFrame with index as datetime, columns as tickers (Close price).
            strategy_func: Function that takes (current_history_data, params) and returns target_positions {ticker: shares}.
            strategy_params: Parameters for the strategy.

        Returns:
            Dict with metrics, equity_curve, and trade_history
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
            current_prices = {
                ticker: float(price_data.loc[date, ticker])
                for ticker in tickers
                if not pd.isna(price_data.loc[date, ticker])
            }
            market_snapshot = {}
            for ticker, price in current_prices.items():
                quote = {"price": float(price)}
                volume_col = f"{ticker}_volume"
                if volume_col in price_data.columns and not pd.isna(price_data.loc[date, volume_col]):
                    quote["volume"] = float(price_data.loc[date, volume_col])
                market_snapshot[ticker] = quote

            # 3. Run Strategy
            # Pass data up to current date
            current_history = price_data.loc[:date]
            target_positions = strategy_func(current_history, strategy_params)

            # 4. Execute Rebalance via TradingEngine
            # This generates orders and places them in the broker (status=SUBMITTED)
            self.trading_engine.execute_rebalance(target_positions, current_prices)

            # 5. Match Orders (Simulate Execution)
            # Match immediately against current close prices
            self.broker.match_orders(market_snapshot)

            # 6. Record Performance
            account_info = self.broker.get_account_info()
            self.equity_curve.append({
                "date": date,
                "equity": account_info["equity"],
                "cash": account_info["cash"]
            })

            # 记录持仓（用于集中度分析）
            positions = {p.ticker: p.shares for p in self.broker.get_positions()}
            total_equity = account_info["equity"]
            self.positions_history.append({
                "date": date,
                "positions": positions,
                "total_equity": total_equity
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
        trade_history = self.broker.get_history()
        total_commission = float(sum(float(t.get("commission", 0.0)) for t in trade_history))
        total_notional = float(sum(abs(float(t.get("notional", 0.0))) for t in trade_history))
        avg_equity = float(df["equity"].mean()) if not df.empty else 0.0
        turnover = (total_notional / avg_equity) if avg_equity > 0 else 0.0

        return {
            "total_return": total_return,
            "net_return_after_cost": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "volatility": volatility,
            "transaction_cost": total_commission,
            "turnover": turnover,
            "equity_curve": df,
            "trade_history": trade_history,
            "positions_history": self.positions_history
        }

    # --------------------------------------------------------------------------
    # v1.2.0 新增功能
    # --------------------------------------------------------------------------

    def run_with_benchmark(
        self,
        price_data: pd.DataFrame,
        strategy_func: Callable[[pd.DataFrame, Dict], Dict[str, int]],
        benchmark_ticker: str,
        benchmark_data: pd.DataFrame = None,
        strategy_params: Dict = None,
        start_date: str = None
    ) -> Dict:
        """
        运行回测并计算相对于基准指数的 alpha 和信息比率

        Args:
            price_data: 策略标的的价格数据
            strategy_func: 策略函数
            benchmark_ticker: 基准指数代码（如 '000300.SH'）
            benchmark_data: 基准指数的价格数据（可选，如果为None则从price_data中取）
            strategy_params: 策略参数
            start_date: 回测开始日期（用于对齐数据）

        Returns:
            包含基准对比指标的字典
        """
        # 运行策略回测
        result = self.run(price_data, strategy_func, strategy_params)

        if benchmark_data is None and benchmark_ticker in price_data.columns:
            # 从同一数据中提取基准
            benchmark_price = benchmark_data[benchmark_ticker] if benchmark_data is not None else price_data[benchmark_ticker]
        else:
            # 如果单独提供了基准数据，则使用
            if benchmark_data is not None:
                benchmark_price = benchmark_data[benchmark_ticker]
            else:
                # 无法计算基准对比
                result["benchmark_comparison"] = {
                    "information_ratio": 0,
                    "beta": 1.0,
                    "alpha": 0,
                    "r_squared": 0,
                    "tracking_error": 0
                }
                return result

        # 计算基准收益率
        benchmark_returns = benchmark_price.pct_change().fillna(0)

        # 计算超额收益
        strategy_returns = result["equity_curve"]["returns"]
        aligned = pd.DataFrame({
            "strategy": strategy_returns.values,
            "benchmark": benchmark_returns.values
        }).dropna()

        if len(aligned) < 2:
            result["benchmark_comparison"] = {
                "information_ratio": 0,
                "beta": 1.0,
                "alpha": 0,
                "r_squared": 0,
                "tracking_error": 0
            }
            return result

        # 线性回归计算 beta, alpha, r_squared
        strategy_mean, benchmark_mean = aligned["strategy"].mean(), aligned["benchmark"].mean()
        beta = ((aligned["strategy"] - strategy_mean) * (aligned["benchmark"] - benchmark_mean)).sum() / \
               ((aligned["benchmark"] - benchmark_mean) ** 2).sum()
        alpha = strategy_mean - beta * benchmark_mean
        alpha = alpha * 252  # 年化 alpha

        y_pred = alpha + beta * aligned["benchmark"]
        ss_res = ((aligned["strategy"] - y_pred) ** 2).sum()
        ss_tot = ((aligned["strategy"] - strategy_mean) ** 2).sum()
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # 跟踪误差和信息比率
        excess_returns = aligned["strategy"] - aligned["benchmark"]
        tracking_error = excess_returns.std() * np.sqrt(252)
        information_ratio = (excess_returns.mean() * 252) / tracking_error if tracking_error > 0 else 0

        result["benchmark_comparison"] = {
            "benchmark_ticker": benchmark_ticker,
            "information_ratio": float(information_ratio),
            "beta": float(beta),
            "alpha": float(alpha),
            "r_squared": float(r_squared),
            "tracking_error": float(tracking_error)
        }

        return result

    def run_multi_strategy(
        self,
        price_data: pd.DataFrame,
        strategies: Dict[str, Tuple[Callable, Dict]],
        weights: Dict[str, float] = None,
        benchmark_ticker: str = None,
        benchmark_data: pd.DataFrame = None
    ) -> Dict:
        """
        多策略组合回测

        Args:
            price_data: 价格数据
            strategies: {strategy_id: (strategy_func, params)}
            weights: 策略权重 {strategy_id: weight}，如果为None则等权重
            benchmark_ticker: 基准指数代码
            benchmark_data: 基准指数数据

        Returns:
            包含组合结果和单策略结果的字典
        """
        if not strategies:
            return {"error": "No strategies provided"}

        # 计算权重
        strategy_ids = list(strategies.keys())
        if weights is None:
            weights = {sid: 1.0 / len(strategy_ids) for sid in strategy_ids}
        else:
            # 归一化权重
            total_weight = sum(weights.get(sid, 0) for sid in strategy_ids)
            if total_weight > 0:
                weights = {sid: w / total_weight for sid, w in weights.items()}

        # 单策略回测
        individual_results = {}
        for sid, (func, params) in strategies.items():
            engine = BacktestEngine(self.initial_capital, self.fees)
            individual_results[sid] = engine.run(price_data, func, params)

        # 计算组合权益曲线
        # 将各策略的收益率按权重加权
        combined_returns = pd.Series(0.0, index=individual_results[strategy_ids[0]]["equity_curve"].index)

        for sid, result in individual_results.items():
            strategy_ret = result["equity_curve"]["returns"]
            combined_returns = combined_returns + strategy_ret * weights.get(sid, 0)

        # 构建组合 equity curve
        combined_equity = (1 + combined_returns).cumprod() * self.initial_capital
        combined_df = pd.DataFrame({"equity": combined_equity})
        combined_df.index.name = "date"

        # 计算组合指标
        total_return = (combined_df["equity"].iloc[-1] / self.initial_capital) - 1
        volatility = combined_returns.std() * np.sqrt(252)
        sharpe = (combined_returns.mean() * 252) / volatility if volatility > 0 else 0
        cum_max = combined_df["equity"].cummax()
        drawdown = (combined_df["equity"] - cum_max) / cum_max
        max_drawdown = drawdown.min()

        # 基准对比
        benchmark_comparison = {}
        if benchmark_ticker and benchmark_data is not None:
            benchmark_price = benchmark_data[benchmark_ticker]
            benchmark_returns = benchmark_price.pct_change().fillna(0)

            # 对齐日期
            aligned = pd.DataFrame({
                "portfolio": combined_returns.values,
                "benchmark": benchmark_returns.values
            }).dropna()

            if len(aligned) >= 2:
                strategy_mean = aligned["portfolio"].mean()
                benchmark_mean = aligned["benchmark"].mean()
                beta = ((aligned["portfolio"] - strategy_mean) * (aligned["benchmark"] - benchmark_mean)).sum() / \
                       ((aligned["benchmark"] - benchmark_mean) ** 2).sum()
                alpha = strategy_mean - beta * benchmark_mean
                alpha = alpha * 252

                y_pred = alpha + beta * aligned["benchmark"]
                ss_res = ((aligned["portfolio"] - y_pred) ** 2).sum()
                ss_tot = ((aligned["portfolio"] - strategy_mean) ** 2).sum()
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                excess_returns = aligned["portfolio"] - aligned["benchmark"]
                tracking_error = excess_returns.std() * np.sqrt(252)
                information_ratio = (excess_returns.mean() * 252) / tracking_error if tracking_error > 0 else 0

                benchmark_comparison = {
                    "benchmark_ticker": benchmark_ticker,
                    "information_ratio": float(information_ratio),
                    "beta": float(beta),
                    "alpha": float(alpha),
                    "r_squared": float(r_squared),
                    "tracking_error": float(tracking_error)
                }

        # 合并交易历史
        combined_trades = []
        for result in individual_results.values():
            combined_trades.extend(result.get("trade_history", []))

        return {
            "portfolio": {
                "total_return": total_return,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_drawdown,
                "volatility": volatility,
                "equity_curve": combined_df,
                "trade_history": combined_trades,
                "weights": weights,
                "benchmark_comparison": benchmark_comparison
            },
            "individual": individual_results
        }

    def optimize_parameters(
        self,
        price_data: pd.DataFrame,
        strategy_func: Callable[[pd.DataFrame, Dict], Dict[str, int]],
        param_grid: Dict[str, List[Any]],
        objective: str = "trading_objective",
        cv_days: int = 60,
        parallel: bool = True
    ) -> Dict:
        """
        参数优化（网格搜索）

        Args:
            price_data: 价格数据
            strategy_func: 策略函数
            param_grid: 参数网格 {param_name: [values]}
            objective: 优化目标 'sharpe_ratio', 'total_return', 'sortino_ratio', 'calmar_ratio'
            cv_days: 交叉验证窗口天数
            parallel: 是否并行计算

        Returns:
            最优参数和优化结果
        """
        from itertools import product

        # 生成所有参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        all_combinations = list(product(*param_values))

        best_score = -np.inf
        best_params = {}
        all_results = []

        # 确定优化方向
        maximize = objective in ["trading_objective", "sharpe_ratio", "total_return", "sortino_ratio", "calmar_ratio"]

        def _objective_score(result: Dict[str, Any]) -> float:
            if objective == "trading_objective":
                net = float(result.get("net_return_after_cost", result.get("total_return", 0.0)))
                sharpe_ratio = float(result.get("sharpe_ratio", 0.0))
                max_dd = abs(float(result.get("max_drawdown", 0.0)))
                turnover_ratio = float(result.get("turnover", 0.0))
                return net + 0.10 * sharpe_ratio - 0.50 * max_dd - 0.10 * turnover_ratio
            raw = result.get(objective, 0.0)
            return float(raw if raw is not None else 0.0)

        def evaluate_params(params: Dict) -> Tuple[Dict, float]:
            """评估一组参数"""
            try:
                # 使用较短的回测窗口进行快速评估
                if isinstance(params, (list, tuple)):
                    params = dict(zip(param_names, params))
                dates = price_data.index.sort_values()
                if len(dates) > cv_days:
                    # 使用滚动窗口
                    end_idx = len(dates) - 1
                    start_idx = max(0, end_idx - cv_days)
                    sub_data = price_data.iloc[start_idx:end_idx]
                else:
                    sub_data = price_data

                engine = BacktestEngine(self.initial_capital, self.fees)
                result = engine.run(sub_data, strategy_func, params)

                # 获取目标分数
                score = _objective_score(result)
                if score is None or (isinstance(score, (float, int)) and np.isnan(score)):
                    score = -np.inf if maximize else np.inf

                return params, float(score)
            except Exception as e:
                logger.warning(f"Error evaluating params {params}: {e}")
                return params, -np.inf if maximize else np.inf

        if parallel:
            # 并行计算
            with ThreadPoolExecutor(max_workers=min(4, len(all_combinations))) as executor:
                futures = {executor.submit(evaluate_params, params): params for params in all_combinations}
                for future in as_completed(futures):
                    params, score = future.result()
                    all_results.append({"params": params, "score": score})
                    if (maximize and score > best_score) or (not maximize and score < best_score):
                        best_score = score
                        best_params = params
        else:
            # 串行计算
            for params in all_combinations:
                params, score = evaluate_params(params)
                all_results.append({"params": params, "score": score})
                if (maximize and score > best_score) or (not maximize and score < best_score):
                    best_score = score
                    best_params = params

        return {
            "best_params": best_params,
            "best_score": float(best_score),
            "all_results": all_results,
            "param_names": param_names,
            "objective": objective
        }

    def get_positions_at_date(self, date: datetime) -> Dict[str, float]:
        """获取指定日期的持仓权重"""
        for entry in self.positions_history:
            if entry["date"] == date:
                total = entry["total_equity"]
                if total == 0:
                    return {}
                return {k: v * p / total for k, (v, p) in
                        zip(entry["positions"].keys(),
                            [(entry["positions"][k],
                              self._get_price_at_date(k, date)) for k in entry["positions"]])}
        return {}

    def _get_price_at_date(self, ticker: str, date: datetime) -> float:
        """获取指定日期的股票价格（简化实现）"""
        try:
            # 从交易历史中获取
            for fill in self.broker.fills:
                if fill.symbol == ticker:
                    return fill.price
        except:
            pass
        return 0.0


def optimize_strategy(
    price_data: pd.DataFrame,
    strategy_func: Callable[[pd.DataFrame, Dict], Dict[str, int]],
    param_grid: Dict[str, List[Any]],
    objective: str = "trading_objective",
    initial_capital: float = 100000
) -> Dict:
    """
    便捷函数：优化策略参数

    Args:
        price_data: 价格数据
        strategy_func: 策略函数
        param_grid: 参数网格
        objective: 优化目标
        initial_capital: 初始资本

    Returns:
        优化结果
    """
    engine = BacktestEngine(initial_capital)
    return engine.optimize_parameters(price_data, strategy_func, param_grid, objective)


def run_multi_strategy_backtest(
    price_data: pd.DataFrame,
    strategies: Dict[str, Tuple[Callable, Dict]],
    weights: Dict[str, float] = None,
    initial_capital: float = 100000,
    benchmark_ticker: str = None,
    benchmark_data: pd.DataFrame = None
) -> Dict:
    """
    便捷函数：多策略组合回测

    Args:
        price_data: 价格数据
        strategies: 策略字典
        weights: 策略权重
        initial_capital: 初始资本
        benchmark_ticker: 基准指数代码
        benchmark_data: 基准数据

    Returns:
        回测结果
    """
    engine = BacktestEngine(initial_capital)
    return engine.run_multi_strategy(
        price_data, strategies, weights,
        benchmark_ticker, benchmark_data
    )

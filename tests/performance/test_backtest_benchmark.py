"""
回测性能基准测试 - v1.3.0
使用 pytest-benchmark 验证关键操作性能阈值

Note: pytest-benchmark is optional. Run with:
    pip install pytest-benchmark
    pytest tests/performance/test_backtest_benchmark.py -v
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

# 设置项目路径
project_root = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(project_root))

from core.backtest_engine import BacktestEngine


# 创建模拟价格数据的辅助函数
def generate_price_data(n_stocks: int, n_days: int) -> pd.DataFrame:
    """生成模拟价格数据"""
    dates = pd.bdate_range(end=pd.Timestamp.today(), periods=n_days)
    tickers = [f"Stock_{i}" for i in range(n_stocks)]

    data = {}
    for ticker in tickers:
        # 生成带有趋势的价格序列
        base_price = 100 + np.random.randn() * 10
        trend = np.linspace(0, 20, n_days)
        noise = np.random.randn(n_days) * 5
        data[ticker] = base_price + trend + noise

    return pd.DataFrame(data, index=dates)


def simple_moving_average_strategy(df, params):
    """简单的移动平均策略"""
    window = params.get("window", 10)
    positions = {}
    for ticker in df.columns:
        if len(df) < window:
            positions[ticker] = 0
            continue
        prices = df[ticker]
        ma = prices.tail(window).mean()
        current = prices.iloc[-1]
        positions[ticker] = 100 if current > ma else 0
    return positions


class TestBacktestPerformance:
    """回测性能基准测试"""

    @pytest.fixture
    def small_dataset(self):
        """小数据集：10只股票，60天"""
        return generate_price_data(n_stocks=10, n_days=60)

    @pytest.fixture
    def medium_dataset(self):
        """中等数据集：50只股票，120天"""
        return generate_price_data(n_stocks=50, n_days=120)

    @pytest.fixture
    def large_dataset(self):
        """大数据集：100只股票，252天"""
        return generate_price_data(n_stocks=100, n_days=252)

    #Benchmark fixture requires pytest-benchmark: pip install pytest-benchmark
    @pytest.mark.skip(reason="pytest-benchmark not installed. Install with: pip install pytest-benchmark")
    def test_single_strategy_small_dataset(self, benchmark, small_dataset):
        """基准：单策略回测 - 小数据集"""
        engine = BacktestEngine(initial_capital=100000)

        def run():
            return engine.run(
                price_data=small_dataset,
                strategy_func=simple_moving_average_strategy,
                strategy_params={"window": 10}
            )

        result = benchmark(run)

        # 验证结果有效性
        assert "total_return" in result
        assert "equity_curve" in result

    @pytest.mark.skip(reason="pytest-benchmark not installed. Install with: pip install pytest-benchmark")
    def test_single_strategy_medium_dataset(self, benchmark, medium_dataset):
        """基准：单策略回测 - 中等数据集"""
        engine = BacktestEngine(initial_capital=100000)

        def run():
            return engine.run(
                price_data=medium_dataset,
                strategy_func=simple_moving_average_strategy,
                strategy_params={"window": 10}
            )

        result = benchmark(run)

        assert "total_return" in result
        assert "equity_curve" in result

    @pytest.mark.skip(reason="pytest-benchmark not installed. Install with: pip install pytest-benchmark")
    def test_single_strategy_large_dataset(self, benchmark, large_dataset):
        """基准：单策略回测 - 大数据集"""
        engine = BacktestEngine(initial_capital=100000)

        def run():
            return engine.run(
                price_data=large_dataset,
                strategy_func=simple_moving_average_strategy,
                strategy_params={"window": 10}
            )

        result = benchmark(run)

        assert "total_return" in result
        assert "equity_curve" in result

    @pytest.mark.skip(reason="pytest-benchmark not installed. Install with: pip install pytest-benchmark")
    def test_multi_strategy_small_dataset(self, benchmark, small_dataset):
        """基准：多策略回测 - 小数据集"""
        engine = BacktestEngine(initial_capital=100000)

        strategies = {
            "strategy1": (simple_moving_average_strategy, {"window": 5}),
            "strategy2": (simple_moving_average_strategy, {"window": 10}),
            "strategy3": (simple_moving_average_strategy, {"window": 20}),
        }

        def run():
            return engine.run_multi_strategy(
                price_data=small_dataset,
                strategies=strategies,
                weights=None,
                benchmark_ticker=None,
                benchmark_data=None
            )

        result = benchmark(run)

        assert "portfolio" in result
        assert "individual" in result

    @pytest.mark.skip(reason="pytest-benchmark not installed. Install with: pip install pytest-benchmark")
    def test_multi_strategy_medium_dataset(self, benchmark, medium_dataset):
        """基准：多策略回测 - 中等数据集"""
        engine = BacktestEngine(initial_capital=100000)

        strategies = {
            "strategy1": (simple_moving_average_strategy, {"window": 5}),
            "strategy2": (simple_moving_average_strategy, {"window": 10}),
            "strategy3": (simple_moving_average_strategy, {"window": 20}),
        }

        def run():
            return engine.run_multi_strategy(
                price_data=medium_dataset,
                strategies=strategies,
                weights=None,
                benchmark_ticker=None,
                benchmark_data=None
            )

        result = benchmark(run)

        assert "portfolio" in result
        assert "individual" in result

    @pytest.mark.skip(reason="pytest-benchmark not installed. Install with: pip install pytest-benchmark")
    def test_parameter_optimization_small_grid(self, benchmark, small_dataset):
        """基准：参数优化 - 小参数网格"""
        engine = BacktestEngine(initial_capital=100000)

        param_grid = {
            "window": [5, 10, 15]
        }

        def run():
            return engine.optimize_parameters(
                price_data=small_dataset,
                strategy_func=simple_moving_average_strategy,
                param_grid=param_grid,
                objective="sharpe_ratio",
                cv_days=60,
                parallel=False  # 测试环境可能不支持多线程
            )

        result = benchmark(run)

        assert "best_params" in result
        assert "best_score" in result

    @pytest.mark.skip(reason="pytest-benchmark not installed. Install with: pip install pytest-benchmark")
    def test_parameter_optimization_medium_grid(self, benchmark, small_dataset):
        """基准：参数优化 - 中等参数网格"""
        engine = BacktestEngine(initial_capital=100000)

        param_grid = {
            "short_window": [5, 10],
            "long_window": [15, 20, 25]
        }

        def run():
            return engine.optimize_parameters(
                price_data=small_dataset,
                strategy_func=simple_moving_average_strategy,
                param_grid=param_grid,
                objective="sharpe_ratio",
                cv_days=30,
                parallel=False
            )

        result = benchmark(run)

        assert "best_params" in result
        assert "all_results" in result

    # --------------------------------------------------------------------------
    # 性能阈值验证（不使用 benchmark fixture）
    # --------------------------------------------------------------------------

    def test_backtest_performance_threshold(self, small_dataset):
        """验证：单策略回测应在可接受时间内完成"""
        engine = BacktestEngine(initial_capital=100000)

        import time
        start = time.time()

        result = engine.run(
            price_data=small_dataset,
            strategy_func=simple_moving_average_strategy,
            strategy_params={"window": 10}
        )

        elapsed = time.time() - start

        # 阈值：1000ms
        assert elapsed < 1.0, f"Backtest took {elapsed:.2f}s, exceeding 1.0s threshold"

    def test_multi_strategy_performance_threshold(self, small_dataset):
        """验证：多策略回测应在可接受时间内完成"""
        engine = BacktestEngine(initial_capital=100000)

        strategies = {
            "s1": (simple_moving_average_strategy, {"window": 5}),
            "s2": (simple_moving_average_strategy, {"window": 10}),
            "s3": (simple_moving_average_strategy, {"window": 15}),
        }

        import time
        start = time.time()

        result = engine.run_multi_strategy(
            price_data=small_dataset,
            strategies=strategies,
            weights=None
        )

        elapsed = time.time() - start

        # 阈值：3000ms
        assert elapsed < 3.0, f"Multi-strategy backtest took {elapsed:.2f}s, exceeding 3.0s threshold"

    def test_optimization_performance_threshold(self, small_dataset):
        """验证：参数优化应在可接受时间内完成"""
        engine = BacktestEngine(initial_capital=100000)

        param_grid = {
            "window": [5, 10, 15, 20]
        }

        import time
        start = time.time()

        result = engine.optimize_parameters(
            price_data=small_dataset,
            strategy_func=simple_moving_average_strategy,
            param_grid=param_grid,
            cv_days=30,
            parallel=False
        )

        elapsed = time.time() - start

        # 阈值：10000ms
        assert elapsed < 10.0, f"Optimization took {elapsed:.2f}s, exceeding 10.0s threshold"


class TestDataLoadingPerformance:
    """数据加载性能测试"""

    def test_price_data_generation_performance(self):
        """验证：价格数据生成应在可接受时间内完成"""
        import time

        start = time.time()

        # 生成大数据集
        df = generate_price_data(n_stocks=500, n_days=252)

        elapsed = time.time() - start

        # 阈值：5000ms
        assert elapsed < 5.0, f"Data generation took {elapsed:.2f}s"

"""快速测试验证脚本"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """测试基本导入"""
    print("=" * 60)
    print("测试模块导入...")
    print("=" * 60)

    try:
        from core.backtest_engine import BacktestEngine
        print("✓ core.backtest_engine 导入成功")
    except Exception as e:
        print(f"✗ core.backtest_engine 导入失败: {e}")

    try:
        from core.risk_monitor import RiskMonitor
        print("✓ core.risk_monitor 导入成功")
    except Exception as e:
        print(f"✗ core.risk_monitor 导入失败: {e}")

    try:
        from core.trading_engine import TradingEngine, apply_equal_weight_rebalance
        print("✓ core.trading_engine 导入成功")
    except Exception as e:
        print(f"✗ core.trading_engine 导入失败: {e}")

    try:
        from core.portfolio_analyzer import PortfolioAnalyzer
        print("✓ core.portfolio_analyzer 导入成功")
    except Exception as e:
        print(f"✗ core.portfolio_analyzer 导入失败: {e}")

    try:
        from core.risk_analysis import (
            calculate_var,
            calculate_cvar,
            calculate_max_drawdown,
            calculate_portfolio_risk_metrics,
        )
        print("✓ core.risk_analysis 导入成功")
    except Exception as e:
        print(f"✗ core.risk_analysis 导入失败: {e}")

def test_risk_analysis_functions():
    """测试风险分析函数"""
    print("\n" + "=" * 60)
    print("测试风险分析函数...")
    print("=" * 60)

    import pandas as pd
    import numpy as np

    from core.risk_analysis import (
        calculate_var,
        calculate_cvar,
        calculate_max_drawdown,
        calculate_portfolio_risk_metrics,
    )

    # 测试数据
    returns = pd.Series([0.01, 0.02, -0.01, -0.02, 0.01, 0.015, -0.015, 0.005])
    prices = pd.Series([100, 110, 120, 115, 100, 90])

    # 测试 VaR
    try:
        var = calculate_var(returns, 0.05)
        print(f"✓ calculate_var: {var:.4f}")
    except Exception as e:
        print(f"✗ calculate_var 错误: {e}")

    # 测试 CVaR
    try:
        cvar = calculate_cvar(returns, 0.05)
        print(f"✓ calculate_cvar: {cvar:.4f}")
    except Exception as e:
        print(f"✗ calculate_cvar 错误: {e}")

    # 测试最大回撤
    try:
        max_dd, _ = calculate_max_drawdown(prices)
        print(f"✓ calculate_max_drawdown: {max_dd:.4f}")
    except Exception as e:
        print(f"✗ calculate_max_drawdown 错误: {e}")

    # 测试组合风险指标
    try:
        returns_df = pd.DataFrame({
            "AAPL": [0.01, 0.02, -0.01],
            "MSFT": [0.012, 0.018, -0.008],
        })
        weights = np.array([0.6, 0.4])
        metrics = calculate_portfolio_risk_metrics(returns_df, weights)
        print(f"✓ calculate_portfolio_risk_metrics: Sharpe={metrics['sharpe_ratio']:.4f}")
    except Exception as e:
        print(f"✗ calculate_portfolio_risk_metrics 错误: {e}")

def test_risk_monitor():
    """测试风险监控器"""
    print("\n" + "=" * 60)
    print("测试风险监控器...")
    print("=" * 60)

    from core.risk_monitor import RiskMonitor
    from core.risk_types import RiskAction, RiskLevel

    monitor = RiskMonitor()

    # 测试风险检查
    portfolio = {
        "cash": 1000000,
        "positions": {},
        "initial_capital": 1000000
    }
    prices = {"600519": 100.0}

    order = {
        "symbol": "600519",
        "side": "BUY",
        "quantity": 100,
        "price": 100.0
    }

    try:
        result = monitor.check_order_risk(order, portfolio, prices)
        print(f"✓ check_order_risk: action={result.action.value}, level={result.risk_level.value}")
    except Exception as e:
        print(f"✗ check_order_risk 错误: {e}")

    # 测试风险事件记录
    try:
        monitor._record_risk_event(
            event_type="test_event",
            severity="warning",
            message="测试事件",
            symbol="600519"
        )
        print(f"✓ _record_risk_event: 记录 {len(monitor.risk_events)} 个事件")
    except Exception as e:
        print(f"✗ _record_risk_event 错误: {e}")

def test_trading_engine():
    """测试交易引擎"""
    print("\n" + "=" * 60)
    print("测试交易引擎...")
    print("=" * 60)

    from core.trading_engine import TradingEngine
    from core.position_manager import PositionManager
    from core.risk_monitor import RiskMonitor

    # 创建 Mock Broker
    class MockBroker:
        def __init__(self):
            self.cash = 100000
            self.positions = []

        def get_positions(self):
            return self.positions

        def get_account_info(self):
            return {"cash": self.cash, "total_assets": self.cash, "equity": self.cash}

        def place_order(self, order):
            return order

    broker = MockBroker()
    risk_monitor = RiskMonitor()
    engine = TradingEngine(broker=broker, risk_monitor=risk_monitor)

    # 测试回测执行
    try:
        prices = {"600519": 100.0}
        target_positions = {"600519": 100}
        orders, messages = engine.execute_rebalance(target_positions, prices)
        print(f"✓ execute_rebalance: 生成 {len(orders)} 个订单")
    except Exception as e:
        print(f"✗ execute_rebalance 错误: {e}")

def test_portfolio_analyzer():
    """测试组合分析器"""
    print("\n" + "=" * 60)
    print("测试组合分析器...")
    print("=" * 60)

    import pandas as pd
    import numpy as np

    from core.portfolio_analyzer import PortfolioAnalyzer
    from core.risk_analysis import calculate_portfolio_risk_metrics

    # 测试风险指标计算
    try:
        returns = pd.DataFrame({
            "AAPL": [0.01, 0.02, -0.01, 0.015, 0.01],
            "MSFT": [0.012, 0.018, -0.008, 0.016, 0.009],
        })
        weights = np.array([0.6, 0.4])

        metrics = calculate_portfolio_risk_metrics(returns, weights)
        print(f"✓ calculate_portfolio_risk_metrics: return={metrics['annual_return']:.4f}, sharpe={metrics['sharpe_ratio']:.4f}")
    except Exception as e:
        print(f"✗ calculate_portfolio_risk_metrics 错误: {e}")

    # 测试 PortfolioAnalyzer
    try:
        analyzer = PortfolioAnalyzer(tickers=["600519", "000001"])
        print(f"✓ PortfolioAnalyzer 初始化: tickers={analyzer.tickers}, weights={list(analyzer.weights)}")
    except Exception as e:
        print(f"✗ PortfolioAnalyzer 初始化错误: {e}")

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("测试框架验证")
    print("=" * 60)

    test_imports()
    test_risk_analysis_functions()
    test_risk_monitor()
    test_trading_engine()
    test_portfolio_analyzer()

    print("\n" + "=" * 60)
    print("验证完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()

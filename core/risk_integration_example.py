"""风险管理模块集成示例

展示如何使用风险管理系统的各个组件
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from .risk_types import (
    RiskLimits,
    RiskAction,
    RiskLevel,
    AlertSeverity,
    PositionLimit
)
from .risk_monitor import RiskMonitor
from .position_manager import PositionManager
from .stop_loss_manager import StopLossManager
from .risk_alerting import RiskAlerting
from .account import compute_equity


def create_risk_management_system() -> Dict:
    """
    创建完整的风险管理系统

    Returns:
        包含所有风险管理组件的字典
    """
    # 1. 创建风险限制配置
    risk_limits = RiskLimits(
        max_position_size=0.1,      # 单仓位最大10%
        max_total_exposure=0.95,     # 总敞口最大95%
        max_sector_exposure=0.3,     # 单行业最大30%
        max_single_stock=0.05,      # 单股票最大5%
        max_daily_loss=0.05,        # 单日最大亏损5%
        max_total_loss=0.2,         # 总亏损最大20%
        stop_loss_threshold=0.08    # 止损阈值8%
    )
    
    # 2. 创建行业/市场分类信息（示例）
    from .position_manager import SectorInfo
    sector_info = {
        "159755.SZ": SectorInfo(symbol="159755.SZ", sector="新能源", market="A股"),
        "002611": SectorInfo(symbol="002611", sector="黄金", market="A股"),
        "006810": SectorInfo(symbol="006810", sector="银行", market="A股"),
        "AAPL": SectorInfo(symbol="AAPL", sector="科技", market="美股"),
        "TSLA": SectorInfo(symbol="TSLA", sector="新能源", market="美股"),
    }
    
    # 3. 创建仓位管理器
    position_manager = PositionManager(sector_info=sector_info)
    
    # 设置行业限制
    position_manager.set_sector_limit("新能源", max_weight=0.3)
    position_manager.set_sector_limit("科技", max_weight=0.3)
    position_manager.set_sector_limit("银行", max_weight=0.2)
    
    # 设置市场限制
    position_manager.set_market_limit("A股", max_weight=0.6)
    position_manager.set_market_limit("美股", max_weight=0.4)
    
    # 设置单标的限制
    for symbol in ["159755.SZ", "002611", "006810", "AAPL", "TSLA"]:
        position_manager.add_position_limit(
            PositionLimit(
                symbol=symbol,
                max_position=10000,  # 最大持仓数量
                max_weight=0.05     # 最大权重5%
            )
        )
    
    # 4. 创建风险监控器
    risk_monitor = RiskMonitor(
        risk_limits=risk_limits,
        position_manager=position_manager
    )
    
    # 5. 创建止损止盈管理器
    stop_loss_manager = StopLossManager()
    
    # 6. 创建风险告警系统
    risk_alerting = RiskAlerting(
        # 邮件配置（可选）
        email_config={
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "username": "your_email@example.com",
            "password": "your_password"
        },
        # Webhook配置（可选）
        webhook_url="https://your-webhook-url.com/alerts",
        # 日志文件
        log_file="logs/risk_alerts.log"
    )
    
    # 7. 设置回调函数
    def on_risk_event(event):
        """风险事件回调"""
        print(f"风险事件: {event.event_type} - {event.message}")
        # 发送告警
        risk_alerting.send_alert(
            alert_type=event.event_type,
            severity=event.severity,
            message=event.message,
            data=event.details,
            symbol=event.symbol
        )
    
    risk_monitor.on_risk_event = on_risk_event
    risk_monitor.on_alert = on_risk_event
    
    return {
        "risk_limits": risk_limits,
        "position_manager": position_manager,
        "risk_monitor": risk_monitor,
        "stop_loss_manager": stop_loss_manager,
        "risk_alerting": risk_alerting
    }


def example_order_risk_check():
    """示例：订单风险检查"""
    # 创建风险管理系统
    risk_system = create_risk_management_system()
    risk_monitor = risk_system["risk_monitor"]
    
    # 模拟账户
    portfolio = {
        "initial_capital": 1_000_000.0,
        "cash": 500_000.0,
        "positions": {
            "159755.SZ": 1000,
            "002611": 500
        }
    }
    
    # 当前价格
    current_prices = {
        "159755.SZ": 1.5,
        "002611": 2.0,
        "AAPL": 150.0
    }
    
    # 检查订单风险
    order = {
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": 1000,
        "price": 150.0
    }
    
    result = risk_monitor.check_order_risk(order, portfolio, current_prices)
    
    print(f"订单风险检查结果:")
    print(f"  动作: {result.action.value}")
    print(f"  风险等级: {result.risk_level.value}")
    print(f"  消息: {result.message}")
    if result.violations:
        print(f"  违规项: {result.violations}")
    
    return result


def example_position_management():
    """示例：仓位管理"""
    risk_system = create_risk_management_system()
    position_manager = risk_system["position_manager"]
    
    # 模拟账户
    portfolio = {
        "initial_capital": 1_000_000.0,
        "cash": 500_000.0,
        "positions": {
            "159755.SZ": 1000,
            "002611": 500
        }
    }
    
    # 当前价格
    current_prices = {
        "159755.SZ": 1.5,
        "002611": 2.0,
        "AAPL": 150.0
    }
    
    # 检查仓位限制
    symbol = "AAPL"
    quantity = 100
    passed, msg = position_manager.check_position_limit(
        symbol, quantity, portfolio, current_prices
    )
    
    print(f"仓位检查结果: {'通过' if passed else '拒绝'}")
    if not passed:
        print(f"  原因: {msg}")
    
    # 获取可用仓位
    available = position_manager.get_available_position(
        symbol, portfolio, current_prices
    )
    print(f"可用仓位额度: {available:.2f} 元")
    
    # 获取仓位汇总
    summary = position_manager.get_position_summary(portfolio, current_prices)
    print(f"仓位汇总:")
    print(f"  总权益: {summary['total_equity']:.2f}")
    print(f"  总仓位权重: {summary['total_position_weight']:.2%}")
    print(f"  标的权重: {summary['symbol_weights']}")
    print(f"  行业权重: {summary['sector_weights']}")
    print(f"  市场权重: {summary['market_weights']}")


def example_stop_loss():
    """示例：止损止盈管理"""
    risk_system = create_risk_management_system()
    stop_loss_manager = risk_system["stop_loss_manager"]
    
    # 设置止损
    stop_loss_manager.set_stop_loss(
        symbol="AAPL",
        entry_price=150.0,
        stop_type="percentage",
        stop_percentage=0.05  # 5%止损
    )
    
    # 设置止盈
    stop_loss_manager.set_take_profit(
        symbol="AAPL",
        entry_price=150.0,
        take_profit_type="percentage",
        take_profit_percentage=0.1  # 10%止盈
    )
    
    # 模拟账户
    portfolio = {
        "initial_capital": 1_000_000.0,
        "cash": 850_000.0,
        "positions": {
            "AAPL": 100
        }
    }
    
    # 模拟价格变化
    scenarios = [
        {"AAPL": 140.0},  # 触发止损
        {"AAPL": 165.0},  # 触发止盈
        {"AAPL": 152.0},  # 正常
    ]
    
    for prices in scenarios:
        trades = stop_loss_manager.check_and_execute(
            prices, portfolio, execute_callback=None
        )
        if trades:
            print(f"价格 {prices['AAPL']}: 触发交易 {len(trades)} 笔")
            for trade in trades:
                print(f"  {trade.side} {trade.shares} 股 {trade.ticker} @ {trade.price:.2f}")
        else:
            print(f"价格 {prices['AAPL']}: 无触发")


def example_risk_monitoring():
    """示例：风险监控"""
    risk_system = create_risk_management_system()
    risk_monitor = risk_system["risk_monitor"]
    
    # 模拟账户
    portfolio = {
        "initial_capital": 1_000_000.0,
        "cash": 200_000.0,  # 现金较少，模拟亏损
        "positions": {
            "159755.SZ": 50000,  # 大仓位
            "002611": 10000
        }
    }
    
    # 当前价格
    current_prices = {
        "159755.SZ": 1.5,
        "002611": 2.0
    }
    
    # 启动监控
    risk_monitor.start_monitoring(portfolio, current_prices, interval=1.0)
    
    # 等待一段时间（实际使用中不需要）
    import time
    time.sleep(2)
    
    # 停止监控
    risk_monitor.stop_monitoring()
    
    # 获取风险汇总
    summary = risk_monitor.get_risk_summary()
    print("风险监控汇总:")
    print(f"  紧急停止: {summary['emergency_stop']}")
    print(f"  监控状态: {summary['is_monitoring']}")
    print(f"  总事件数: {summary['total_events']}")
    print(f"  最近事件: {len(summary['recent_events'])} 个")


if __name__ == "__main__":
    print("=" * 60)
    print("风险管理系统集成示例")
    print("=" * 60)
    
    print("\n1. 订单风险检查示例")
    print("-" * 60)
    example_order_risk_check()
    
    print("\n2. 仓位管理示例")
    print("-" * 60)
    example_position_management()
    
    print("\n3. 止损止盈示例")
    print("-" * 60)
    example_stop_loss()
    
    print("\n4. 风险监控示例")
    print("-" * 60)
    example_risk_monitoring()


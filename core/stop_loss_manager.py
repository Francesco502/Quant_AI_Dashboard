"""止损止盈管理系统

职责：
- 管理止损和止盈规则
- 实时监控价格并触发止损/止盈
- 自动执行止损/止盈订单
"""

from __future__ import annotations

from typing import Dict, List, Optional, Callable
from datetime import datetime
import logging

from .risk_types import StopLossRule, TakeProfitRule
from .broker_simulator import Trade


logger = logging.getLogger(__name__)


class StopLossManager:
    """止损止盈管理器"""

    def __init__(self):
        """初始化止损止盈管理器"""
        # 止损规则 {symbol: StopLossRule}
        self.stop_loss_rules: Dict[str, StopLossRule] = {}
        
        # 止盈规则 {symbol: TakeProfitRule}
        self.take_profit_rules: Dict[str, TakeProfitRule] = {}
        
        # 订单执行回调函数
        self.execute_order_callback: Optional[Callable[[Trade], bool]] = None
        
        logger.info("止损止盈管理器初始化完成")

    def set_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        stop_type: str = "fixed",
        stop_price: Optional[float] = None,
        stop_percentage: Optional[float] = None,
        trailing_distance: Optional[float] = None
    ):
        """
        设置止损规则

        Args:
            symbol: 标的代码
            entry_price: 入场价格
            stop_type: 止损类型 ('fixed', 'trailing', 'percentage')
            stop_price: 固定止损价格（stop_type='fixed'时使用）
            stop_percentage: 止损百分比（stop_type='percentage'时使用，如0.05表示5%）
            trailing_distance: 跟踪止损距离（stop_type='trailing'时使用，如0.03表示3%）
        """
        rule = StopLossRule(
            symbol=symbol,
            stop_type=stop_type,
            stop_price=stop_price,
            stop_percentage=stop_percentage,
            trailing_distance=trailing_distance,
            entry_price=entry_price,
            enabled=True
        )
        
        # 根据类型计算止损价格
        if stop_type == "percentage" and stop_percentage:
            rule.stop_price = entry_price * (1 - stop_percentage)
        elif stop_type == "trailing" and trailing_distance:
            rule.stop_price = entry_price * (1 - trailing_distance)
        
        self.stop_loss_rules[symbol] = rule
        logger.info(f"设置止损规则: {symbol}, 类型={stop_type}, 止损价={rule.stop_price:.2f}")

    def set_take_profit(
        self,
        symbol: str,
        entry_price: float,
        take_profit_type: str = "percentage",
        take_profit_price: Optional[float] = None,
        take_profit_percentage: Optional[float] = None
    ):
        """
        设置止盈规则

        Args:
            symbol: 标的代码
            entry_price: 入场价格
            take_profit_type: 止盈类型 ('fixed', 'percentage')
            take_profit_price: 固定止盈价格（take_profit_type='fixed'时使用）
            take_profit_percentage: 止盈百分比（take_profit_type='percentage'时使用，如0.1表示10%）
        """
        rule = TakeProfitRule(
            symbol=symbol,
            take_profit_type=take_profit_type,
            take_profit_price=take_profit_price,
            take_profit_percentage=take_profit_percentage,
            entry_price=entry_price,
            enabled=True
        )
        
        # 根据类型计算止盈价格
        if take_profit_type == "percentage" and take_profit_percentage:
            rule.take_profit_price = entry_price * (1 + take_profit_percentage)
        
        self.take_profit_rules[symbol] = rule
        logger.info(f"设置止盈规则: {symbol}, 类型={take_profit_type}, 止盈价={rule.take_profit_price:.2f}")

    def remove_stop_loss(self, symbol: str):
        """移除止损规则"""
        if symbol in self.stop_loss_rules:
            del self.stop_loss_rules[symbol]
            logger.info(f"移除止损规则: {symbol}")

    def remove_take_profit(self, symbol: str):
        """移除止盈规则"""
        if symbol in self.take_profit_rules:
            del self.take_profit_rules[symbol]
            logger.info(f"移除止盈规则: {symbol}")

    def check_and_execute(
        self,
        current_prices: Dict[str, float],
        portfolio: Dict,
        execute_callback: Optional[Callable[[Trade], bool]] = None
    ) -> List[Trade]:
        """
        检查并执行止损止盈

        Args:
            current_prices: 当前价格字典 {symbol: price}
            portfolio: 账户字典
            execute_callback: 订单执行回调函数，如果提供则使用，否则使用内部回调

        Returns:
            已执行的交易列表
        """
        executed_trades: List[Trade] = []
        positions = portfolio.get("positions", {}) or {}
        
        # 使用提供的回调或内部回调
        callback = execute_callback or self.execute_order_callback
        
        for symbol, price in current_prices.items():
            if symbol not in positions or positions[symbol] == 0:
                continue
            
            position = positions[symbol]
            
            # 检查止损
            if symbol in self.stop_loss_rules:
                rule = self.stop_loss_rules[symbol]
                if rule.enabled and self._should_trigger_stop_loss(rule, price, position):
                    trade = self._execute_stop_loss(symbol, rule, price, position)
                    if trade:
                        executed_trades.append(trade)
                        if callback:
                            callback(trade)
                        logger.warning(f"触发止损: {symbol}, 价格={price:.2f}, 止损价={rule.stop_price:.2f}")
            
            # 检查止盈
            if symbol in self.take_profit_rules:
                rule = self.take_profit_rules[symbol]
                if rule.enabled and self._should_trigger_take_profit(rule, price, position):
                    trade = self._execute_take_profit(symbol, rule, price, position)
                    if trade:
                        executed_trades.append(trade)
                        if callback:
                            callback(trade)
                        logger.info(f"触发止盈: {symbol}, 价格={price:.2f}, 止盈价={rule.take_profit_price:.2f}")
        
        return executed_trades

    def _should_trigger_stop_loss(
        self,
        rule: StopLossRule,
        current_price: float,
        position: int
    ) -> bool:
        """判断是否应该触发止损"""
        if not rule.enabled or rule.stop_price is None:
            return False
        
        # 只有持仓方向与止损方向一致时才触发
        # 多头持仓：价格跌破止损价
        # 空头持仓：价格涨破止损价
        if position > 0:  # 多头
            return current_price <= rule.stop_price
        elif position < 0:  # 空头
            return current_price >= rule.stop_price
        
        return False

    def _should_trigger_take_profit(
        self,
        rule: TakeProfitRule,
        current_price: float,
        position: int
    ) -> bool:
        """判断是否应该触发止盈"""
        if not rule.enabled or rule.take_profit_price is None:
            return False
        
        # 只有持仓方向与止盈方向一致时才触发
        # 多头持仓：价格涨破止盈价
        # 空头持仓：价格跌破止盈价
        if position > 0:  # 多头
            return current_price >= rule.take_profit_price
        elif position < 0:  # 空头
            return current_price <= rule.take_profit_price
        
        return False

    def _execute_stop_loss(
        self,
        symbol: str,
        rule: StopLossRule,
        current_price: float,
        position: int
    ) -> Optional[Trade]:
        """执行止损"""
        if position == 0:
            return None
        
        # 平仓
        side = "SELL" if position > 0 else "BUY"
        shares = abs(position)
        
        trade = Trade(
            ticker=symbol,
            side=side,
            shares=shares,
            price=current_price
        )
        
        # 移除止损规则（已触发）
        self.remove_stop_loss(symbol)
        
        return trade

    def _execute_take_profit(
        self,
        symbol: str,
        rule: TakeProfitRule,
        current_price: float,
        position: int
    ) -> Optional[Trade]:
        """执行止盈"""
        if position == 0:
            return None
        
        # 平仓
        side = "SELL" if position > 0 else "BUY"
        shares = abs(position)
        
        trade = Trade(
            ticker=symbol,
            side=side,
            shares=shares,
            price=current_price
        )
        
        # 移除止盈规则（已触发）
        self.remove_take_profit(symbol)
        
        return trade

    def update_trailing_stop(self, symbol: str, current_price: float, position: int):
        """更新跟踪止损价格（仅对跟踪止损类型有效）"""
        if symbol not in self.stop_loss_rules:
            return
        
        rule = self.stop_loss_rules[symbol]
        if rule.stop_type != "trailing" or not rule.enabled:
            return
        
        if rule.trailing_distance is None:
            return
        
        # 多头：止损价随价格上涨而上移，但不随价格下跌而下移
        # 空头：止损价随价格下跌而下移，但不随价格上涨而上移
        if position > 0:  # 多头
            new_stop_price = current_price * (1 - rule.trailing_distance)
            if new_stop_price > rule.stop_price:
                rule.stop_price = new_stop_price
                logger.debug(f"更新跟踪止损: {symbol}, 新止损价={new_stop_price:.2f}")
        elif position < 0:  # 空头
            new_stop_price = current_price * (1 + rule.trailing_distance)
            if new_stop_price < rule.stop_price or rule.stop_price == 0:
                rule.stop_price = new_stop_price
                logger.debug(f"更新跟踪止损: {symbol}, 新止损价={new_stop_price:.2f}")

    def get_active_rules(self) -> Dict:
        """获取所有活跃的止损止盈规则"""
        return {
            "stop_loss": {
                symbol: {
                    "stop_type": rule.stop_type,
                    "stop_price": rule.stop_price,
                    "entry_price": rule.entry_price,
                    "enabled": rule.enabled
                }
                for symbol, rule in self.stop_loss_rules.items()
            },
            "take_profit": {
                symbol: {
                    "take_profit_type": rule.take_profit_type,
                    "take_profit_price": rule.take_profit_price,
                    "entry_price": rule.entry_price,
                    "enabled": rule.enabled
                }
                for symbol, rule in self.take_profit_rules.items()
            }
        }


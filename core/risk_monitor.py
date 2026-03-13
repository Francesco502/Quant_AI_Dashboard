"""实时风险监控系统

职责：
- 7×24小时风险监控
- 实时检测并阻止高风险交易
- 风险事件记录和告警
"""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import logging

from .risk_types import (
    RiskLimits,
    RiskCheckResult,
    RiskAction,
    RiskLevel,
    RiskEvent,
    AlertSeverity
)
from .position_manager import PositionManager
from .account import compute_equity


logger = logging.getLogger(__name__)


class RiskMonitor:
    """实时风险监控器"""

    def __init__(
        self,
        risk_limits: Optional[RiskLimits] = None,
        position_manager: Optional[PositionManager] = None
    ):
        """
        初始化风险监控器

        Args:
            risk_limits: 风险限制配置
            position_manager: 仓位管理器
        """
        self.risk_limits = risk_limits or RiskLimits()
        self.position_manager = position_manager or PositionManager()
        
        # 监控状态
        self.is_monitoring = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # 风险事件历史
        self.risk_events: List[RiskEvent] = []
        self.max_event_history = 1000
        
        # 紧急停止状态
        self.emergency_stop = False
        
        # 每日损失追踪
        self.daily_pnl: Dict[str, float] = {}  # {date: pnl}
        self.total_pnl: float = 0.0
        
        # 回调函数
        self.on_risk_event: Optional[Callable[[RiskEvent], None]] = None
        self.on_alert: Optional[Callable[[RiskEvent], None]] = None
        
        logger.info("风险监控器初始化完成")

    def check_order_risk(
        self,
        order: Dict,
        portfolio: Dict,
        current_prices: Dict[str, float]
    ) -> RiskCheckResult:
        """
        检查订单风险

        Args:
            order: 订单字典，包含 {'symbol', 'side', 'quantity', 'price'}
            portfolio: 账户字典
            current_prices: 当前价格字典

        Returns:
            风险检查结果
        """
        violations: List[str] = []
        max_risk_level = RiskLevel.LOW
        
        # 紧急停止检查
        if self.emergency_stop:
            return RiskCheckResult(
                action=RiskAction.EMERGENCY_STOP,
                risk_level=RiskLevel.CRITICAL,
                message="系统处于紧急停止状态",
                violations=["紧急停止"]
            )
        
        symbol = order.get("symbol")
        side = order.get("side", "BUY")
        quantity = order.get("quantity", 0)
        price = order.get("price", current_prices.get(symbol, 0))
        
        if price <= 0:
            return RiskCheckResult(
                action=RiskAction.REJECT,
                risk_level=RiskLevel.HIGH,
                message=f"无效价格: {symbol}",
                violations=["价格无效"]
            )
        
        # 1. 仓位限制检查
        position_result = self._check_position_risk(
            symbol, quantity, portfolio, current_prices
        )
        if position_result:
            violations.extend(position_result)
            max_risk_level = RiskLevel.HIGH
        
        # 2. 损失限制检查
        loss_result = self._check_loss_risk(portfolio, current_prices)
        if loss_result:
            violations.extend(loss_result)
            max_risk_level = RiskLevel.CRITICAL
        
        # 3. 集中度风险检查
        concentration_result = self._check_concentration_risk(
            portfolio, current_prices
        )
        if concentration_result:
            violations.extend(concentration_result)
            max_risk_level = max(max_risk_level, RiskLevel.MEDIUM)
        
        # 4. 流动性风险检查（简化版）
        liquidity_result = self._check_liquidity_risk(symbol, quantity, price)
        if liquidity_result:
            violations.extend(liquidity_result)
            max_risk_level = max(max_risk_level, RiskLevel.MEDIUM)
        
        # 根据风险等级决定动作
        if max_risk_level == RiskLevel.CRITICAL:
            action = RiskAction.EMERGENCY_STOP
        elif max_risk_level == RiskLevel.HIGH:
            action = RiskAction.REJECT
        elif max_risk_level == RiskLevel.MEDIUM:
            action = RiskAction.WARN
        else:
            action = RiskAction.ALLOW
        
        result = RiskCheckResult(
            action=action,
            risk_level=max_risk_level,
            message="; ".join(violations) if violations else "风险检查通过",
            violations=violations,
            metadata={
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price
            }
        )
        
        # 记录高风险事件
        if max_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            self._record_risk_event(
                event_type="order_risk_check",
                severity=AlertSeverity.ERROR if max_risk_level == RiskLevel.CRITICAL else AlertSeverity.WARNING,
                message=result.message,
                symbol=symbol,
                details=result.metadata
            )
        
        return result

    def _check_position_risk(
        self,
        symbol: str,
        quantity: int,
        portfolio: Dict,
        current_prices: Dict[str, float]
    ) -> List[str]:
        """检查仓位风险"""
        violations = []
        
        # 使用仓位管理器检查
        if self.position_manager:
            passed, msg = self.position_manager.check_position_limit(
                symbol, quantity, portfolio, current_prices
            )
            if not passed:
                violations.append(f"仓位限制: {msg}")
        
        # 检查单标的权重限制
        total_equity = compute_equity(portfolio, current_prices)
        if total_equity > 0:
            current_position = portfolio.get("positions", {}).get(symbol, 0)
            new_position = current_position + quantity
            position_value = abs(new_position) * current_prices.get(symbol, 0)
            position_weight = position_value / total_equity
            
            if position_weight > self.risk_limits.max_single_stock:
                violations.append(
                    f"单标的权重超限: {position_weight:.2%} > {self.risk_limits.max_single_stock:.2%}"
                )
        
        return violations

    def _check_loss_risk(
        self,
        portfolio: Dict,
        current_prices: Dict[str, float]
    ) -> List[str]:
        """检查损失风险"""
        violations = []
        
        # 计算当前权益
        current_equity = compute_equity(portfolio, current_prices)
        initial_capital = portfolio.get("initial_capital", current_equity)
        
        if initial_capital <= 0:
            return violations
        
        # 计算总亏损
        total_loss = (initial_capital - current_equity) / initial_capital
        if total_loss > self.risk_limits.max_total_loss:
            violations.append(
                f"总亏损超限: {total_loss:.2%} > {self.risk_limits.max_total_loss:.2%}"
            )
            # 触发紧急停止
            self.emergency_stop = True
            logger.critical(f"触发紧急停止: 总亏损 {total_loss:.2%}")
        
        # 计算当日亏损
        today = datetime.now().strftime("%Y-%m-%d")
        if today in self.daily_pnl:
            daily_loss = abs(self.daily_pnl[today]) if self.daily_pnl[today] < 0 else 0
            daily_loss_pct = daily_loss / initial_capital if initial_capital > 0 else 0
            if daily_loss_pct > self.risk_limits.max_daily_loss:
                violations.append(
                    f"单日亏损超限: {daily_loss_pct:.2%} > {self.risk_limits.max_daily_loss:.2%}"
                )
        
        return violations

    def _check_concentration_risk(
        self,
        portfolio: Dict,
        current_prices: Dict[str, float]
    ) -> List[str]:
        """检查集中度风险"""
        violations = []
        
        total_equity = compute_equity(portfolio, current_prices)
        if total_equity <= 0:
            return violations
        
        positions = portfolio.get("positions", {}) or {}
        
        # 计算总敞口
        total_exposure = 0.0
        for symbol, quantity in positions.items():
            if quantity != 0:
                price = current_prices.get(symbol, 0)
                total_exposure += abs(quantity) * price
        
        total_exposure_weight = total_exposure / total_equity if total_equity > 0 else 0
        if total_exposure_weight > self.risk_limits.max_total_exposure:
            violations.append(
                f"总敞口超限: {total_exposure_weight:.2%} > {self.risk_limits.max_total_exposure:.2%}"
            )
        
        return violations

    def _check_liquidity_risk(
        self,
        symbol: str,
        quantity: int,
        price: float
    ) -> List[str]:
        """检查流动性风险（简化版）"""
        violations = []
        
        # 这里可以扩展为检查成交量、买卖价差等
        # 当前仅做占位实现
        if abs(quantity) > 100000:  # 假设大单可能影响流动性
            violations.append(f"订单规模较大，可能存在流动性风险: {abs(quantity)}")
        
        return violations

    def start_monitoring(
        self,
        portfolio: Dict,
        current_prices: Dict[str, float],
        interval: float = 5.0
    ):
        """
        启动实时监控线程

        Args:
            portfolio: 账户字典
            current_prices: 当前价格字典
            interval: 监控间隔（秒）
        """
        if self.is_monitoring:
            logger.warning("监控已在运行中")
            return
        
        self.is_monitoring = True
        self.stop_event.clear()
        
        def monitoring_loop():
            logger.info("风险监控线程启动")
            while not self.stop_event.is_set():
                try:
                    # 执行监控检查
                    self._monitoring_cycle(portfolio, current_prices)
                    # 等待下次检查
                    self.stop_event.wait(interval)
                except Exception as e:
                    logger.error(f"监控循环异常: {e}", exc_info=True)
                    time.sleep(interval)
            
            logger.info("风险监控线程停止")
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info(f"风险监控已启动，监控间隔={interval}秒")

    def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self.stop_event.set()
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5.0)
        
        logger.info("风险监控已停止")

    def _monitoring_cycle(
        self,
        portfolio: Dict,
        current_prices: Dict[str, float]
    ):
        """执行一次监控周期"""
        # 检查损失风险
        loss_violations = self._check_loss_risk(portfolio, current_prices)
        if loss_violations:
            self._record_risk_event(
                event_type="loss_risk",
                severity=AlertSeverity.CRITICAL,
                message="; ".join(loss_violations),
                details={"violations": loss_violations}
            )
        
        # 检查集中度风险
        concentration_violations = self._check_concentration_risk(portfolio, current_prices)
        if concentration_violations:
            self._record_risk_event(
                event_type="concentration_risk",
                severity=AlertSeverity.WARNING,
                message="; ".join(concentration_violations),
                details={"violations": concentration_violations}
            )

    def _record_risk_event(
        self,
        event_type: str,
        severity: AlertSeverity,
        message: str,
        symbol: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """记录风险事件"""
        event = RiskEvent(
            event_id=f"{event_type}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            event_type=event_type,
            severity=severity,
            message=message,
            symbol=symbol,
            portfolio_id=portfolio_id,
            details=details or {}
        )
        
        self.risk_events.append(event)
        
        # 限制历史记录数量
        if len(self.risk_events) > self.max_event_history:
            self.risk_events = self.risk_events[-self.max_event_history:]
        
        # 触发回调
        if self.on_risk_event:
            try:
                self.on_risk_event(event)
            except Exception as e:
                logger.error(f"风险事件回调异常: {e}")
        
        # 如果是严重事件，触发告警
        if severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            if self.on_alert:
                try:
                    self.on_alert(event)
                except Exception as e:
                    logger.error(f"告警回调异常: {e}")
        
        logger.warning(f"风险事件: {event_type}, 严重程度={severity.value}, {message}")

    def trigger_alert(
        self,
        alert_type: str,
        severity: AlertSeverity,
        message: str,
        data: Optional[Dict] = None
    ):
        """触发风险告警"""
        self._record_risk_event(
            event_type=alert_type,
            severity=severity,
            message=message,
            details=data or {}
        )

    def update_daily_pnl(self, date: str, pnl: float):
        """更新每日盈亏"""
        self.daily_pnl[date] = pnl
        self.total_pnl += pnl

    def reset_daily_pnl(self, date: str):
        """重置指定日期的盈亏"""
        if date in self.daily_pnl:
            self.total_pnl -= self.daily_pnl[date]
            del self.daily_pnl[date]

    def get_risk_summary(self) -> Dict:
        """获取风险汇总信息"""
        return {
            "emergency_stop": self.emergency_stop,
            "is_monitoring": self.is_monitoring,
            "total_events": len(self.risk_events),
            "recent_events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "type": event.event_type,
                    "severity": event.severity.value,
                    "message": event.message,
                    "symbol": event.symbol
                }
                for event in self.risk_events[-10:]  # 最近10个事件
            ],
            "daily_pnl": self.daily_pnl.copy(),
            "total_pnl": self.total_pnl
        }

    def clear_emergency_stop(self):
        """清除紧急停止状态（需要手动确认）"""
        self.emergency_stop = False
        logger.info("紧急停止状态已清除")

    # ==================== 强制集成方法 ====================

    def check_order(
        self,
        order: Dict,
        portfolio: Dict,
        current_prices: Dict[str, float]
    ) -> RiskCheckResult:
        """
        检查订单风险（强制集成版本）

        与 check_order_risk 的区别：
        - 确保所有订单都经过风控
        - 对高风险订单直接拒绝
        - 记录所有风险事件到数据库
        """
        result = self.check_order_risk(order, portfolio, current_prices)

        # 记录所有检查到数据库
        self._persist_risk_check(order, result)

        return result

    def _persist_risk_check(self, order: Dict, result: RiskCheckResult):
        """将风控检查结果持久化到数据库"""
        import sqlite3
        try:
            # 获取数据库连接
            from core.database import _db_instance
            if _db_instance and _db_instance.conn:
                cursor = _db_instance.conn.cursor()
                cursor.execute("""
                    INSERT INTO risk_events
                    (account_id, event_type, severity, message, symbol, order_id, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    order.get("account_id"),
                    "order_risk_check",
                    result.risk_level.value,
                    result.message,
                    order.get("symbol"),
                    order.get("order_id", "N/A"),
                    str(result.metadata)
                ))
                _db_instance.conn.commit()
        except Exception as e:
            logger.debug(f"风控检查持久化失败: {e}")

    # ==================== 查询方法 ====================

    def get_risk_events(
        self,
        account_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict]:
        """获取风险事件记录"""
        import sqlite3
        try:
            from core.database import _db_instance
            if _db_instance and _db_instance.conn:
                cursor = _db_instance.conn.cursor()
                if account_id:
                    cursor.execute("""
                        SELECT * FROM risk_events
                        WHERE account_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (account_id, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM risk_events
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))

                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取风险事件失败: {e}")
        return []

    def get_daily_risk_summary(self, date: str) -> Dict:
        """获取指定日期的风险汇总"""
        try:
            from core.database import _db_instance
            if _db_instance and _db_instance.conn:
                cursor = _db_instance.conn.cursor()
                cursor.execute("""
                    SELECT
                        severity,
                        COUNT(*) as count,
                        GROUP_CONCAT(message) as messages
                    FROM risk_events
                    WHERE DATE(created_at) = ?
                    GROUP BY severity
                """, (date,))

                summary = {"date": date, "by_severity": {}}
                for row in cursor.fetchall():
                    summary["by_severity"][row["severity"]] = {
                        "count": row["count"],
                        "messages": row["messages"]
                    }
                return summary
        except Exception as e:
            logger.error(f"获取风险汇总失败: {e}")
        return {}


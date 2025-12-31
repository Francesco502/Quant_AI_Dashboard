"""告警管理器

职责：
- 管理告警规则
- 多通道告警（邮件、SMS、Webhook、Telegram、钉钉等）
- 告警冷却期控制
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from .metrics import MetricsCollector


logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """告警严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComparisonOperator(Enum):
    """比较操作符"""
    GT = ">"  # 大于
    LT = "<"  # 小于
    GTE = ">="  # 大于等于
    LTE = "<="  # 小于等于
    EQ = "=="  # 等于
    NE = "!="  # 不等于


@dataclass
class AlertRule:
    """告警规则"""
    rule_id: str
    name: str
    metric_name: str
    threshold: float
    comparison: ComparisonOperator
    severity: AlertSeverity
    enabled: bool = True
    cooldown_minutes: int = 5
    channels: List[str] = None  # 告警渠道列表
    last_triggered: Optional[datetime] = None
    
    def __post_init__(self):
        if self.channels is None:
            self.channels = ["dashboard"]
    
    def should_trigger(self, value: float) -> bool:
        """检查是否应该触发告警"""
        if not self.enabled:
            return False
        
        # 检查冷却期
        if self.last_triggered:
            elapsed = datetime.now() - self.last_triggered
            if elapsed < timedelta(minutes=self.cooldown_minutes):
                return False
        
        # 检查阈值
        if self.comparison == ComparisonOperator.GT:
            return value > self.threshold
        elif self.comparison == ComparisonOperator.LT:
            return value < self.threshold
        elif self.comparison == ComparisonOperator.GTE:
            return value >= self.threshold
        elif self.comparison == ComparisonOperator.LTE:
            return value <= self.threshold
        elif self.comparison == ComparisonOperator.EQ:
            return abs(value - self.threshold) < 1e-6
        elif self.comparison == ComparisonOperator.NE:
            return abs(value - self.threshold) >= 1e-6
        
        return False


@dataclass
class Alert:
    """告警"""
    alert_id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    timestamp: datetime
    channels: List[str] = None
    
    def __post_init__(self):
        if self.channels is None:
            self.channels = []


class AlertChannel:
    """告警通道基类"""
    
    def send(self, alert: Alert) -> bool:
        """发送告警"""
        raise NotImplementedError


class DashboardChannel(AlertChannel):
    """Dashboard告警通道（记录到日志）"""
    
    def send(self, alert: Alert) -> bool:
        """记录到日志"""
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }.get(alert.severity, logging.INFO)
        
        logger.log(
            log_level,
            f"告警 [{alert.severity.value}]: {alert.rule_name} - {alert.message}"
        )
        return True


class EmailChannel(AlertChannel):
    """邮件告警通道"""
    
    def __init__(self, smtp_server: str = None, smtp_port: int = 587,
                 username: str = None, password: str = None, to_email: str = None):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.to_email = to_email or username
        self.enabled = bool(smtp_server and username and password)
    
    def send(self, alert: Alert) -> bool:
        """发送邮件告警"""
        if not self.enabled:
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = self.to_email
            msg['Subject'] = f"[系统告警] {alert.severity.value.upper()}: {alert.rule_name}"
            
            body = f"""
系统告警详情：
- 时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
- 规则: {alert.rule_name}
- 严重程度: {alert.severity.value}
- 消息: {alert.message}
- 指标: {alert.metric_name} = {alert.metric_value}
- 阈值: {alert.threshold}
            """
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"邮件告警已发送: {alert.rule_name}")
            return True
        except Exception as e:
            logger.error(f"发送邮件告警失败: {e}")
            return False


class WebhookChannel(AlertChannel):
    """Webhook告警通道"""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
    
    def send(self, alert: Alert) -> bool:
        """发送Webhook告警"""
        if not self.enabled:
            return False
        
        try:
            import requests
            
            payload = {
                "alert_id": alert.alert_id,
                "rule_name": alert.rule_name,
                "severity": alert.severity.value,
                "message": alert.message,
                "metric_name": alert.metric_name,
                "metric_value": alert.metric_value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp.isoformat(),
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5
            )
            response.raise_for_status()
            
            logger.info(f"Webhook告警已发送: {alert.rule_name}")
            return True
        except Exception as e:
            logger.error(f"发送Webhook告警失败: {e}")
            return False


class TelegramChannel(AlertChannel):
    """Telegram告警通道"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
    
    def send(self, alert: Alert) -> bool:
        """发送Telegram告警"""
        if not self.enabled:
            return False
        
        try:
            import requests
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            message = (
                f"🚨 *系统告警*\n\n"
                f"*规则*: {alert.rule_name}\n"
                f"*严重程度*: {alert.severity.value.upper()}\n"
                f"*消息*: {alert.message}\n"
                f"*指标*: {alert.metric_name} = {alert.metric_value}\n"
                f"*阈值*: {alert.threshold}\n"
                f"*时间*: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            
            logger.info(f"Telegram告警已发送: {alert.rule_name}")
            return True
        except Exception as e:
            logger.error(f"发送Telegram告警失败: {e}")
            return False


class DingTalkChannel(AlertChannel):
    """钉钉告警通道"""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
    
    def send(self, alert: Alert) -> bool:
        """发送钉钉告警"""
        if not self.enabled:
            return False
        
        try:
            import requests
            
            # 钉钉消息格式
            severity_emoji = {
                AlertSeverity.INFO: "ℹ️",
                AlertSeverity.WARNING: "⚠️",
                AlertSeverity.ERROR: "❌",
                AlertSeverity.CRITICAL: "🚨",
            }
            
            message = {
                "msgtype": "text",
                "text": {
                    "content": (
                        f"{severity_emoji.get(alert.severity, '📢')} 系统告警\n\n"
                        f"规则: {alert.rule_name}\n"
                        f"严重程度: {alert.severity.value}\n"
                        f"消息: {alert.message}\n"
                        f"指标: {alert.metric_name} = {alert.metric_value}\n"
                        f"阈值: {alert.threshold}\n"
                        f"时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                }
            }
            
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=5
            )
            response.raise_for_status()
            
            logger.info(f"钉钉告警已发送: {alert.rule_name}")
            return True
        except Exception as e:
            logger.error(f"发送钉钉告警失败: {e}")
            return False


class AlertManager:
    """告警管理器"""

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        channels: Optional[Dict[str, AlertChannel]] = None,
    ):
        """
        初始化告警管理器

        Args:
            metrics_collector: 指标收集器（可选）
            channels: 告警渠道字典（可选）
        """
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.alert_rules: Dict[str, AlertRule] = {}
        self.alert_history: List[Alert] = []
        self.max_history = 1000
        
        # 告警渠道
        self.channels: Dict[str, AlertChannel] = channels or {}
        if "dashboard" not in self.channels:
            self.channels["dashboard"] = DashboardChannel()
        
        # 回调函数
        self.on_alert: Optional[Callable[[Alert], None]] = None
        
        logger.info("告警管理器初始化完成")

    def add_channel(self, name: str, channel: AlertChannel):
        """添加告警渠道"""
        self.channels[name] = channel
        logger.info(f"添加告警渠道: {name}")

    def add_alert_rule(
        self,
        name: str,
        metric_name: str,
        threshold: float,
        comparison: ComparisonOperator,
        severity: AlertSeverity,
        cooldown_minutes: int = 5,
        channels: Optional[List[str]] = None,
    ) -> str:
        """
        添加告警规则

        Args:
            name: 规则名称
            metric_name: 指标名称
            threshold: 阈值
            comparison: 比较操作符
            severity: 严重程度
            cooldown_minutes: 冷却期（分钟）
            channels: 告警渠道列表

        Returns:
            规则ID
        """
        import uuid
        rule_id = f"RULE_{uuid.uuid4().hex[:8].upper()}"
        
        rule = AlertRule(
            rule_id=rule_id,
            name=name,
            metric_name=metric_name,
            threshold=threshold,
            comparison=comparison,
            severity=severity,
            cooldown_minutes=cooldown_minutes,
            channels=channels or ["dashboard"],
        )
        
        self.alert_rules[rule_id] = rule
        logger.info(f"添加告警规则: {name} ({rule_id})")
        
        return rule_id

    def remove_alert_rule(self, rule_id: str) -> bool:
        """移除告警规则"""
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            logger.info(f"移除告警规则: {rule_id}")
            return True
        return False

    def check_and_trigger(self, metrics: Optional[Dict[str, float]] = None):
        """
        检查指标并触发告警

        Args:
            metrics: 指标字典（可选，如果不提供则从收集器获取）
        """
        if metrics is None:
            # 从收集器获取最新指标
            metrics = {}
            for metric_name in ["cpu_usage", "memory_usage", "disk_usage"]:
                value = self.metrics_collector.get_latest_metric(metric_name)
                if value is not None:
                    metrics[metric_name] = value
        
        for rule_id, rule in self.alert_rules.items():
            if rule.metric_name not in metrics:
                continue
            
            value = metrics[rule.metric_name]
            
            if rule.should_trigger(value):
                # 触发告警
                self._trigger_alert(rule, value)
                rule.last_triggered = datetime.now()

    def _trigger_alert(self, rule: AlertRule, metric_value: float):
        """触发告警"""
        import uuid
        alert_id = f"ALERT_{uuid.uuid4().hex[:8].upper()}"
        
        # 生成告警消息
        comparison_str = {
            ComparisonOperator.GT: ">",
            ComparisonOperator.LT: "<",
            ComparisonOperator.GTE: ">=",
            ComparisonOperator.LTE: "<=",
            ComparisonOperator.EQ: "==",
            ComparisonOperator.NE: "!=",
        }.get(rule.comparison, "?")
        
        message = f"{rule.metric_name} {comparison_str} {rule.threshold} (当前值: {metric_value:.2f})"
        
        alert = Alert(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            rule_name=rule.name,
            severity=rule.severity,
            message=message,
            metric_name=rule.metric_name,
            metric_value=metric_value,
            threshold=rule.threshold,
            timestamp=datetime.now(),
            channels=rule.channels,
        )
        
        # 记录到历史
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        # 发送告警
        success_count = 0
        for channel_name in rule.channels:
            if channel_name in self.channels:
                channel = self.channels[channel_name]
                if channel.send(alert):
                    success_count += 1
        
        # 触发回调
        if self.on_alert:
            try:
                self.on_alert(alert)
            except Exception as e:
                logger.error(f"告警回调异常: {e}")
        
        logger.warning(
            f"告警已触发: {rule.name} [{rule.severity.value}] - {message}, "
            f"发送成功: {success_count}/{len(rule.channels)}"
        )

    def get_alert_history(
        self,
        limit: int = 100,
        severity: Optional[AlertSeverity] = None,
        rule_id: Optional[str] = None,
    ) -> List[Dict]:
        """获取告警历史"""
        filtered = self.alert_history
        
        if severity:
            filtered = [a for a in filtered if a.severity == severity]
        
        if rule_id:
            filtered = [a for a in filtered if a.rule_id == rule_id]
        
        # 按时间倒序
        filtered = sorted(filtered, key=lambda x: x.timestamp, reverse=True)
        
        return [
            {
                "alert_id": alert.alert_id,
                "rule_name": alert.rule_name,
                "severity": alert.severity.value,
                "message": alert.message,
                "metric_name": alert.metric_name,
                "metric_value": alert.metric_value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp.isoformat(),
            }
            for alert in filtered[:limit]
        ]

    def get_alert_statistics(self) -> Dict:
        """获取告警统计信息"""
        return {
            "total_alerts": len(self.alert_history),
            "by_severity": {
                severity.value: sum(1 for a in self.alert_history if a.severity == severity)
                for severity in AlertSeverity
            },
            "by_rule": {
                rule.name: sum(1 for a in self.alert_history if a.rule_id == rule.rule_id)
                for rule in self.alert_rules.values()
            },
            "active_rules": len([r for r in self.alert_rules.values() if r.enabled]),
            "recent_alerts_24h": len([
                a for a in self.alert_history
                if (datetime.now() - a.timestamp) < timedelta(hours=24)
            ]),
        }


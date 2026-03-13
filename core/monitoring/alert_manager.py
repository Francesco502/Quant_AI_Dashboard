"""告警管理器

职责：
- 管理告警规则
- 多通道告警（邮件、飞书、企业微信、Webhook、Telegram、钉钉等）
- 告警冷却期控制
- 告警风暴防护

增强功能：
- 飞书渠道支持
- 企业微信渠道支持
- 告警聚合（减少重复告警）
- 告警频率限制
"""

from __future__ import annotations

import logging
import hashlib
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock


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
    channels: List[str] = field(default_factory=lambda: ["dashboard"])
    last_triggered: Optional[datetime] = None
    # 告警聚合配置
    aggregate_minutes: int = 0  # 聚合窗口（0表示不聚合）
    aggregate_key: Optional[str] = None  # 聚合键

    def should_trigger(self, value: float, current_time: Optional[datetime] = None) -> bool:
        """检查是否应该触发告警"""
        if not self.enabled:
            return False

        current_time = current_time or datetime.now()

        # 检查冷却期
        if self.last_triggered:
            elapsed = current_time - self.last_triggered
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
    channels: List[str] = field(default_factory=lambda: [])
    aggregate_count: int = 1  # 聚合次数
    first_triggered: datetime = field(default_factory=datetime.now)
    last_triggered: datetime = field(default_factory=datetime.now)


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

            severity_colors = {
                AlertSeverity.INFO: "#2196F3",
                AlertSeverity.WARNING: "#FF9800",
                AlertSeverity.ERROR: "#F44336",
                AlertSeverity.CRITICAL: "#9C27B0",
            }

            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: {severity_colors.get(alert.severity, '#333')};">
                    🚨 系统告警 - {alert.severity.value.upper()}
                </h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>规则名称</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{alert.rule_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>严重程度</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{alert.severity.value}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>告警消息</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{alert.message}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>指标名称</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{alert.metric_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>当前值</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{alert.metric_value:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>告警阈值</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{alert.threshold:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>发生时间</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>
                    </tr>
                </table>
                <p style="color: #999; font-size: 12px; margin-top: 20px;">
                    此为系统自动发送的告警邮件，请勿回复。
                </p>
            </div>
            """

            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = self.to_email
            severity_emoji = {
                AlertSeverity.INFO: "ℹ️",
                AlertSeverity.WARNING: "⚠️",
                AlertSeverity.ERROR: "❌",
                AlertSeverity.CRITICAL: "🚨",
            }
            msg['Subject'] = f"[系统告警] {severity_emoji.get(alert.severity, '📢')} {alert.rule_name}"

            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

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

    def __init__(self, webhook_url: str = None, method: str = "POST", headers: Dict = None):
        self.webhook_url = webhook_url
        self.method = method
        self.headers = headers or {"Content-Type": "application/json"}
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
                "aggregate_count": alert.aggregate_count,
            }

            response = requests.request(
                method=self.method,
                url=self.webhook_url,
                json=payload,
                headers=self.headers,
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

    def __init__(self, bot_token: str = None, chat_id: str = None, parse_mode: str = "Markdown"):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.enabled = bool(bot_token and chat_id)

    def send(self, alert: Alert) -> bool:
        """发送Telegram告警"""
        if not self.enabled:
            return False

        try:
            import requests

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            severity_emoji = {
                AlertSeverity.INFO: "ℹ️",
                AlertSeverity.WARNING: "⚠️",
                AlertSeverity.ERROR: "❌",
                AlertSeverity.CRITICAL: "🚨",
            }

            message = (
                f"{severity_emoji.get(alert.severity, '📢')} <b>系统告警</b>\n\n"
                f"<b>规则</b>: {alert.rule_name}\n"
                f"<b>严重程度</b>: {alert.severity.value.upper()}\n"
                f"<b>消息</b>: {alert.message}\n"
                f"<b>指标</b>: {alert.metric_name} = {alert.metric_value:.2f}\n"
                f"<b>阈值</b>: {alert.threshold:.2f}\n"
                f"<b>时间</b>: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            if alert.aggregate_count > 1:
                message += f"\n\n<b>聚合次数</b>: {alert.aggregate_count}"

            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": self.parse_mode
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

    def __init__(self, webhook_url: str = None, secret: str = None):
        self.webhook_url = webhook_url
        self.secret = secret
        self.enabled = bool(webhook_url)

    def send(self, alert: Alert) -> bool:
        """发送钉钉告警"""
        if not self.enabled:
            return False

        try:
            import requests
            import time
            import hmac
            import hashlib
            import base64

            # 如果配置了secret，需要生成签名
            if self.secret:
                timestamp = str(round(time.time() * 1000))
                string_to_sign = f"{timestamp}\n{self.secret}"
                hmac_code = hmac.new(
                    self.secret.encode(),
                    string_to_sign.encode(),
                    hashlib.sha256
                ).digest()
                signature = base64.b64encode(hmac_code).decode()
                webhook_url = f"{self.webhook_url}&timestamp={timestamp}&sign={signature}"
            else:
                webhook_url = self.webhook_url

            severity_emoji = {
                AlertSeverity.INFO: "ℹ️",
                AlertSeverity.WARNING: "⚠️",
                AlertSeverity.ERROR: "❌",
                AlertSeverity.CRITICAL: "🚨",
            }

            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"[系统告警] {alert.severity.value.upper()} - {alert.rule_name}",
                    "text": (
                        f"## {severity_emoji.get(alert.severity, '📢')} 系统告警\n\n"
                        f"> **规则**: {alert.rule_name}\n\n"
                        f"> **严重程度**: {alert.severity.value}\n\n"
                        f"> **消息**: {alert.message}\n\n"
                        f"> **指标**: {alert.metric_name} = {alert.metric_value:.2f}\n\n"
                        f"> **阈值**: {alert.threshold:.2f}\n\n"
                        f"> **时间**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                }
            }

            response = requests.post(
                webhook_url,
                json=message,
                timeout=5
            )
            response.raise_for_status()

            logger.info(f"钉钉告警已发送: {alert.rule_name}")
            return True
        except Exception as e:
            logger.error(f"发送钉钉告警失败: {e}")
            return False


class FeishuChannel(AlertChannel):
    """飞书告警通道（支持机器人消息）"""

    def __init__(self, webhook_url: str = None, secret: str = None):
        self.webhook_url = webhook_url
        self.secret = secret
        self.enabled = bool(webhook_url)

    def send(self, alert: Alert) -> bool:
        """发送飞书告警"""
        if not self.enabled:
            return False

        try:
            import requests
            import time
            import hmac
            import hashlib
            import base64

            # 飞书-signed webhook认证
            if self.secret:
                timestamp = str(int(time.time()))
                string_to_sign = f"{timestamp}\n{self.secret}"
                hmac_code = hmac.new(
                    self.secret.encode(),
                    string_to_sign.encode(),
                    hashlib.sha256
                ).digest()
                sign = base64.b64encode(hmac_code).decode()
                url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
            else:
                url = self.webhook_url

            severity_emoji = {
                AlertSeverity.INFO: "ℹ️",
                AlertSeverity.WARNING: "⚠️",
                AlertSeverity.ERROR: "❌",
                AlertSeverity.CRITICAL: "🚨",
            }

            message = {
                "msg_type": "interactive",
                "card": {
                    "config": {
                        "wide_screen_mode": True
                    },
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"{severity_emoji.get(alert.severity, '📢')} 系统告警"
                        },
                        "template": {
                            AlertSeverity.INFO: "blue",
                            AlertSeverity.WARNING: "orange",
                            AlertSeverity.ERROR: "red",
                            AlertSeverity.CRITICAL: "purple",
                        }.get(alert.severity, "gray")
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"**规则**: {alert.rule_name}\n\n**严重程度**: {alert.severity.value.upper()}\n\n**消息**: {alert.message}"
                            }
                        },
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"**指标**: `{alert.metric_name}` = **{alert.metric_value:.2f}**\n\n**阈值**: **{alert.threshold:.2f}**"
                            }
                        },
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                            }
                        }
                    ]
                }
            }

            response = requests.post(
                url,
                json=message,
                timeout=5
            )
            response.raise_for_status()

            logger.info(f"飞书告警已发送: {alert.rule_name}")
            return True
        except Exception as e:
            logger.error(f"发送飞书告警失败: {e}")
            return False


class WeComChannel(AlertChannel):
    """企业微信告警通道"""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)

    def send(self, alert: Alert) -> bool:
        """发送企业微信告警"""
        if not self.enabled:
            return False

        try:
            import requests

            severity_emoji = {
                AlertSeverity.INFO: "ℹ️",
                AlertSeverity.WARNING: "⚠️",
                AlertSeverity.ERROR: "❌",
                AlertSeverity.CRITICAL: "🚨",
            }

            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": (
                        f"## {severity_emoji.get(alert.severity, '📢')} 系统告警\n\n"
                        f"> **规则**: {alert.rule_name}\n\n"
                        f"> **严重程度**: {alert.severity.value.upper()}\n\n"
                        f"> **消息**: {alert.message}\n\n"
                        f"> **指标**: `{alert.metric_name}` = {alert.metric_value:.2f}\n\n"
                        f"> **阈值**: {alert.threshold:.2f}\n\n"
                        f"> **时间**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                }
            }

            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=5
            )
            response.raise_for_status()

            logger.info(f"企业微信告警已发送: {alert.rule_name}")
            return True
        except Exception as e:
            logger.error(f"发送企业微信告警失败: {e}")
            return False


class AlertManager:
    """告警管理器（增强版）"""

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        channels: Optional[Dict[str, AlertChannel]] = None,
        max_history: int = 1000,
    ):
        """
        初始化告警管理器

        Args:
            metrics_collector: 指标收集器（可选）
            channels: 告警渠道字典（可选）
            max_history: 最大告警历史数量
        """
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.alert_rules: Dict[str, AlertRule] = {}
        self.alert_history: List[Alert] = []
        self.max_history = max_history

        # 告警渠道
        self.channels: Dict[str, AlertChannel] = channels or {}
        if "dashboard" not in self.channels:
            self.channels["dashboard"] = DashboardChannel()

        # 聚合告警队列（用于防告警风暴）
        self._aggregate_queue: Dict[str, Alert] = {}
        self._aggregate_lock = Lock()

        # 告警频率限制
        self._alert_timestamps: List[datetime] = []
        self._max_alerts_per_hour = 10
        self._last_alert_clear_time = datetime.now()

        # 回调函数
        self.on_alert: Optional[Callable[[Alert], None]] = None

        logger.info("告警管理器初始化完成（增强版）")

    def set_alert_frequency_limit(self, max_alerts_per_hour: int = 10):
        """设置告警频率限制"""
        self._max_alerts_per_hour = max_alerts_per_hour

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
        aggregate_minutes: int = 0,
        aggregate_key: Optional[str] = None,
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
            aggregate_minutes: 聚合窗口（分钟），0表示不聚合
            aggregate_key: 聚合键

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
            aggregate_minutes=aggregate_minutes,
            aggregate_key=aggregate_key,
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

    def _check_alert_frequency(self, current_time: datetime) -> bool:
        """检查告警频率限制"""
        # 清理1小时前的告警记录
        if (current_time - self._last_alert_clear_time).hours >= 1:
            self._alert_timestamps = [
                t for t in self._alert_timestamps
                if (current_time - t).hours < 1
            ]
            self._last_alert_clear_time = current_time

        return len(self._alert_timestamps) < self._max_alerts_per_hour

    def _aggregate_alert(self, alert: Alert) -> Optional[Alert]:
        """
        聚合告警（防告警风暴）

        Returns:
            聚合后的告警，None表示不触发
        """
        if not alert.rule.aggregate_minutes:
            return alert

        # 生成聚合键
        key = alert.rule.aggregate_key or alert.rule_id

        with self._aggregate_lock:
            if key in self._aggregate_queue:
                existing = self._aggregate_queue[key]
                existing.aggregate_count += 1
                existing.last_triggered = datetime.now()

                # 聚合窗口到期
                if (datetime.now() - existing.first_triggered).minutes >= alert.rule.aggregate_minutes:
                    # 返回聚合后的告警
                    aggregated = Alert(
                        alert_id=existing.alert_id,
                        rule_id=existing.rule_id,
                        rule_name=existing.rule_name,
                        severity=existing.severity,
                        message=existing.message,
                        metric_name=existing.metric_name,
                        metric_value=existing.metric_value,
                        threshold=existing.threshold,
                        timestamp=existing.first_triggered,
                        channels=existing.channels,
                        aggregate_count=existing.aggregate_count,
                        first_triggered=existing.first_triggered,
                        last_triggered=datetime.now(),
                    )
                    del self._aggregate_queue[key]
                    return aggregated
            else:
                # 新的聚合事件
                self._aggregate_queue[key] = alert

            return None

    def check_and_trigger(self, metrics: Optional[Dict[str, float]] = None):
        """
        检查指标并触发告警

        Args:
            metrics: 指标字典（可选，如果不提供则从收集器获取）
        """
        current_time = datetime.now()

        # 检查告警频率
        if not self._check_alert_frequency(current_time):
            logger.warning("告警频率超过限制，丢弃告警")
            return

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

            if rule.should_trigger(value, current_time):
                # 触发告警
                alert = self._create_alert(rule, value, current_time)

                # 聚合处理
                if rule.aggregate_minutes:
                    aggregated = self._aggregate_alert(alert)
                    if aggregated:
                        self._trigger_alert(aggregated)
                        rule.last_triggered = current_time
                else:
                    self._trigger_alert(alert)
                    rule.last_triggered = current_time

    def _create_alert(self, rule: AlertRule, metric_value: float, timestamp: datetime) -> Alert:
        """创建告警对象"""
        import uuid

        # 生成告警ID
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

        return Alert(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            rule_name=rule.name,
            severity=rule.severity,
            message=message,
            metric_name=rule.metric_name,
            metric_value=metric_value,
            threshold=rule.threshold,
            timestamp=timestamp,
            channels=rule.channels,
            aggregate_count=1,
            first_triggered=timestamp,
            last_triggered=timestamp,
        )

    def _trigger_alert(self, alert: Alert):
        """触发告警"""
        # 记录到历史
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]

        # 更新告警频率记录
        self._alert_timestamps.append(datetime.now())

        # 发送告警
        success_count = 0
        for channel_name in alert.channels:
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

        if alert.aggregate_count > 1:
            logger.warning(
                f"告警已触发（聚合）: {alert.rule_name} [{alert.severity.value}] - {alert.message}, "
                f"聚合次数: {alert.aggregate_count}, 发送成功: {success_count}/{len(alert.channels)}"
            )
        else:
            logger.warning(
                f"告警已触发: {alert.rule_name} [{alert.severity.value}] - {alert.message}, "
                f"发送成功: {success_count}/{len(alert.channels)}"
            )

    def get_alert_history(
        self,
        limit: int = 100,
        severity: Optional[AlertSeverity] = None,
        rule_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
    ) -> List[Dict]:
        """获取告警历史"""
        filtered = self.alert_history

        if severity:
            filtered = [a for a in filtered if a.severity == severity]

        if rule_id:
            filtered = [a for a in filtered if a.rule_id == rule_id]

        if start_time:
            filtered = [a for a in filtered if a.timestamp >= start_time]

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
                "aggregate_count": alert.aggregate_count,
                "channels": alert.channels,
            }
            for alert in filtered[:limit]
        ]

    def get_alert_statistics(self) -> Dict:
        """获取告警统计信息"""
        now = datetime.now()

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
                if (now - a.timestamp).days < 1
            ]),
            "recent_alerts_1h": len([
                a for a in self.alert_history
                if (now - a.timestamp).hours < 1
            ]),
            "alerts_today": len([
                a for a in self.alert_history
                if (now - a.timestamp).days == 0
            ]),
        }

    def clear_old_alerts(self, days: int = 7) -> int:
        """
        清理旧告警

        Args:
            days: 保留天数

        Returns:
            删除的告警数量
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        before_count = len(self.alert_history)
        self.alert_history = [
            a for a in self.alert_history
            if a.timestamp >= cutoff_time
        ]
        after_count = len(self.alert_history)
        removed = before_count - after_count

        if removed > 0:
            logger.info(f"清理旧告警: 删除 {removed} 条（{days}天前）")

        return removed

    def get_channels_status(self) -> Dict[str, bool]:
        """获取各渠道状态"""
        return {
            name: channel.enabled if hasattr(channel, 'enabled') else True
            for name, channel in self.channels.items()
        }

    def get_active_alerts(self) -> List[Dict]:
        """获取当前活跃告警（未恢复）"""
        # 简化实现：返回最近的告警
        return self.get_alert_history(limit=10, severity=AlertSeverity.WARNING)

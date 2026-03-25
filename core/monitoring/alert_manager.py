"""Alert manager and channel integrations for system monitoring."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import smtplib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from threading import Lock
from typing import Callable, Dict, List, Optional

import requests

from .metrics import MetricsCollector


logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComparisonOperator(Enum):
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NE = "!="


@dataclass
class AlertRule:
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
    aggregate_minutes: int = 0
    aggregate_key: Optional[str] = None

    def should_trigger(self, value: float, current_time: Optional[datetime] = None) -> bool:
        if not self.enabled:
            return False

        now = current_time or datetime.now()
        if self.last_triggered and now - self.last_triggered < timedelta(minutes=self.cooldown_minutes):
            return False

        if self.comparison == ComparisonOperator.GT:
            return value > self.threshold
        if self.comparison == ComparisonOperator.LT:
            return value < self.threshold
        if self.comparison == ComparisonOperator.GTE:
            return value >= self.threshold
        if self.comparison == ComparisonOperator.LTE:
            return value <= self.threshold
        if self.comparison == ComparisonOperator.EQ:
            return abs(value - self.threshold) < 1e-6
        if self.comparison == ComparisonOperator.NE:
            return abs(value - self.threshold) >= 1e-6
        return False


@dataclass
class Alert:
    alert_id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    timestamp: datetime
    channels: List[str] = field(default_factory=list)
    aggregate_count: int = 1
    first_triggered: datetime = field(default_factory=datetime.now)
    last_triggered: datetime = field(default_factory=datetime.now)
    aggregate_minutes: int = 0
    aggregate_key: Optional[str] = None


class AlertChannel:
    enabled: bool = True

    def send(self, alert: Alert) -> bool:
        raise NotImplementedError


class DashboardChannel(AlertChannel):
    def __init__(self) -> None:
        self.enabled = True

    def send(self, alert: Alert) -> bool:
        level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }.get(alert.severity, logging.INFO)
        logger.log(level, "Alert [%s] %s - %s", alert.severity.value, alert.rule_name, alert.message)
        return True


class EmailChannel(AlertChannel):
    def __init__(
        self,
        smtp_server: Optional[str] = None,
        smtp_port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        to_email: Optional[str] = None,
    ) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.to_email = to_email or username
        self.enabled = bool(smtp_server and username and password and self.to_email)

    def send(self, alert: Alert) -> bool:
        if not self.enabled:
            return False
        try:
            msg = MIMEMultipart()
            msg["From"] = self.username or ""
            msg["To"] = self.to_email or ""
            msg["Subject"] = f"[Monitoring] {alert.severity.value.upper()} {alert.rule_name}"
            body = (
                f"Rule: {alert.rule_name}\n"
                f"Severity: {alert.severity.value}\n"
                f"Message: {alert.message}\n"
                f"Metric: {alert.metric_name}={alert.metric_value:.2f}\n"
                f"Threshold: {alert.threshold:.2f}\n"
                f"Timestamp: {alert.timestamp.isoformat()}\n"
            )
            msg.attach(MIMEText(body, "plain", "utf-8"))
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.username or "", self.password or "")
                server.send_message(msg)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to send email alert: %s", exc)
            return False


class WebhookChannel(AlertChannel):
    def __init__(self, webhook_url: Optional[str] = None, method: str = "POST", headers: Optional[Dict[str, str]] = None):
        self.webhook_url = webhook_url
        self.method = method
        self.headers = headers or {"Content-Type": "application/json"}
        self.enabled = bool(webhook_url)

    def send(self, alert: Alert) -> bool:
        if not self.enabled or not self.webhook_url:
            return False
        try:
            requests.request(
                method=self.method,
                url=self.webhook_url,
                json={
                    "alert_id": alert.alert_id,
                    "rule_name": alert.rule_name,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "metric_name": alert.metric_name,
                    "metric_value": alert.metric_value,
                    "threshold": alert.threshold,
                    "timestamp": alert.timestamp.isoformat(),
                    "aggregate_count": alert.aggregate_count,
                },
                headers=self.headers,
                timeout=10,
            ).raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to send webhook alert: %s", exc)
            return False


class TelegramChannel(AlertChannel):
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None, parse_mode: str = "HTML") -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.enabled = bool(bot_token and chat_id)

    def send(self, alert: Alert) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": (
                        f"<b>Monitoring Alert</b>\n"
                        f"Rule: {alert.rule_name}\n"
                        f"Severity: {alert.severity.value.upper()}\n"
                        f"Message: {alert.message}"
                    ),
                    "parse_mode": self.parse_mode,
                },
                timeout=10,
            ).raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to send Telegram alert: %s", exc)
            return False


def _sign_url(secret: Optional[str], url: Optional[str], *, milliseconds: bool) -> Optional[str]:
    if not secret or not url:
        return url
    timestamp = str(round(time.time() * 1000)) if milliseconds else str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode("utf-8")
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}timestamp={timestamp}&sign={signature}"


class DingTalkChannel(AlertChannel):
    def __init__(self, webhook_url: Optional[str] = None, secret: Optional[str] = None) -> None:
        self.webhook_url = webhook_url
        self.secret = secret
        self.enabled = bool(webhook_url)

    def send(self, alert: Alert) -> bool:
        if not self.enabled or not self.webhook_url:
            return False
        try:
            requests.post(
                _sign_url(self.secret, self.webhook_url, milliseconds=True),
                json={
                    "msgtype": "markdown",
                    "markdown": {
                        "title": f"{alert.severity.value.upper()} {alert.rule_name}",
                        "text": (
                            f"## Monitoring Alert\n\n"
                            f"> Rule: {alert.rule_name}\n\n"
                            f"> Severity: {alert.severity.value}\n\n"
                            f"> Message: {alert.message}\n\n"
                            f"> Metric: {alert.metric_name}={alert.metric_value:.2f}\n\n"
                            f"> Threshold: {alert.threshold:.2f}"
                        ),
                    },
                },
                timeout=10,
            ).raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to send DingTalk alert: %s", exc)
            return False


class FeishuChannel(AlertChannel):
    def __init__(self, webhook_url: Optional[str] = None, secret: Optional[str] = None) -> None:
        self.webhook_url = webhook_url
        self.secret = secret
        self.enabled = bool(webhook_url)

    def send(self, alert: Alert) -> bool:
        if not self.enabled or not self.webhook_url:
            return False
        try:
            requests.post(
                _sign_url(self.secret, self.webhook_url, milliseconds=False),
                json={
                    "msg_type": "interactive",
                    "card": {
                        "header": {
                            "title": {"tag": "plain_text", "content": "Monitoring Alert"},
                            "template": "red" if alert.severity in {AlertSeverity.ERROR, AlertSeverity.CRITICAL} else "blue",
                        },
                        "elements": [
                            {"tag": "div", "text": {"tag": "lark_md", "content": f"**Rule**: {alert.rule_name}"}},
                            {"tag": "div", "text": {"tag": "lark_md", "content": f"**Message**: {alert.message}"}},
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**Metric**: `{alert.metric_name}` = **{alert.metric_value:.2f}**",
                                },
                            },
                        ],
                    },
                },
                timeout=10,
            ).raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to send Feishu alert: %s", exc)
            return False


class WeComChannel(AlertChannel):
    def __init__(self, webhook_url: Optional[str] = None) -> None:
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)

    def send(self, alert: Alert) -> bool:
        if not self.enabled or not self.webhook_url:
            return False
        try:
            requests.post(
                self.webhook_url,
                json={
                    "msgtype": "markdown",
                    "markdown": {
                        "content": (
                            f"## Monitoring Alert\n\n"
                            f"> Rule: {alert.rule_name}\n\n"
                            f"> Severity: {alert.severity.value.upper()}\n\n"
                            f"> Message: {alert.message}"
                        )
                    },
                },
                timeout=10,
            ).raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to send WeCom alert: %s", exc)
            return False


class AlertManager:
    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        channels: Optional[Dict[str, AlertChannel]] = None,
        max_history: int = 1000,
    ) -> None:
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.alert_rules: Dict[str, AlertRule] = {}
        self.alert_history: List[Alert] = []
        self.max_history = max_history
        self.channels: Dict[str, AlertChannel] = channels or {"dashboard": DashboardChannel()}
        if "dashboard" not in self.channels:
            self.channels["dashboard"] = DashboardChannel()
        self._aggregate_queue: Dict[str, Alert] = {}
        self._aggregate_lock = Lock()
        self._alert_timestamps: List[datetime] = []
        self._max_alerts_per_hour = 10
        self._last_alert_clear_time = datetime.now()
        self.on_alert: Optional[Callable[[Alert], None]] = None

    def set_alert_frequency_limit(self, max_alerts_per_hour: int = 10) -> None:
        self._max_alerts_per_hour = max_alerts_per_hour

    def add_channel(self, name: str, channel: AlertChannel) -> None:
        self.channels[name] = channel

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
        import uuid

        rule_id = f"RULE_{uuid.uuid4().hex[:8].upper()}"
        self.alert_rules[rule_id] = AlertRule(
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
        return rule_id

    def remove_alert_rule(self, rule_id: str) -> bool:
        if rule_id not in self.alert_rules:
            return False
        del self.alert_rules[rule_id]
        return True

    def _check_alert_frequency(self, current_time: datetime) -> bool:
        if (current_time - self._last_alert_clear_time).total_seconds() >= 3600:
            self._alert_timestamps = [
                ts for ts in self._alert_timestamps if (current_time - ts).total_seconds() < 3600
            ]
            self._last_alert_clear_time = current_time
        return len(self._alert_timestamps) < self._max_alerts_per_hour

    def _aggregate_alert(self, alert: Alert) -> Optional[Alert]:
        if not alert.aggregate_minutes:
            return alert

        key = alert.aggregate_key or alert.rule_id
        with self._aggregate_lock:
            existing = self._aggregate_queue.get(key)
            if existing is None:
                self._aggregate_queue[key] = alert
                return None

            existing.aggregate_count += 1
            existing.last_triggered = datetime.now()
            if (datetime.now() - existing.first_triggered).total_seconds() < alert.aggregate_minutes * 60:
                return None

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
                aggregate_minutes=existing.aggregate_minutes,
                aggregate_key=existing.aggregate_key,
            )
            del self._aggregate_queue[key]
            return aggregated

    def check_and_trigger(self, metrics: Optional[Dict[str, float]] = None) -> None:
        now = datetime.now()
        if not self._check_alert_frequency(now):
            logger.warning("Alert frequency limit reached. Dropping alerts for this interval.")
            return

        if metrics is None:
            metrics = {}
            for metric_name in ("cpu_usage", "memory_usage", "disk_usage"):
                value = self.metrics_collector.get_latest_metric(metric_name)
                if value is not None:
                    metrics[metric_name] = value

        for rule in self.alert_rules.values():
            if rule.metric_name not in metrics:
                continue
            value = metrics[rule.metric_name]
            if not rule.should_trigger(value, now):
                continue

            alert = self._create_alert(rule, value, now)
            aggregated = self._aggregate_alert(alert)
            if aggregated is None:
                continue
            self._trigger_alert(aggregated)
            rule.last_triggered = now

    def _create_alert(self, rule: AlertRule, metric_value: float, timestamp: datetime) -> Alert:
        import uuid

        op = rule.comparison.value
        message = f"{rule.metric_name} {op} {rule.threshold} (current={metric_value:.2f})"
        return Alert(
            alert_id=f"ALERT_{uuid.uuid4().hex[:8].upper()}",
            rule_id=rule.rule_id,
            rule_name=rule.name,
            severity=rule.severity,
            message=message,
            metric_name=rule.metric_name,
            metric_value=metric_value,
            threshold=rule.threshold,
            timestamp=timestamp,
            channels=list(rule.channels),
            aggregate_count=1,
            first_triggered=timestamp,
            last_triggered=timestamp,
            aggregate_minutes=rule.aggregate_minutes,
            aggregate_key=rule.aggregate_key,
        )

    def _trigger_alert(self, alert: Alert) -> None:
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history :]

        self._alert_timestamps.append(datetime.now())

        success_count = 0
        for channel_name in alert.channels:
            channel = self.channels.get(channel_name)
            if channel and channel.send(alert):
                success_count += 1

        if self.on_alert:
            try:
                self.on_alert(alert)
            except Exception as exc:  # noqa: BLE001
                logger.error("Alert callback failed: %s", exc)

        logger.warning(
            "Alert triggered: %s [%s] success=%s/%s aggregate_count=%s",
            alert.rule_name,
            alert.severity.value,
            success_count,
            len(alert.channels),
            alert.aggregate_count,
        )

    def get_alert_history(
        self,
        limit: int = 100,
        severity: Optional[AlertSeverity] = None,
        rule_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
    ) -> List[Dict[str, object]]:
        items = self.alert_history
        if severity is not None:
            items = [alert for alert in items if alert.severity == severity]
        if rule_id is not None:
            items = [alert for alert in items if alert.rule_id == rule_id]
        if start_time is not None:
            items = [alert for alert in items if alert.timestamp >= start_time]
        items = sorted(items, key=lambda alert: alert.timestamp, reverse=True)
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
            for alert in items[:limit]
        ]

    def get_alert_statistics(self) -> Dict[str, object]:
        now = datetime.now()
        return {
            "total_alerts": len(self.alert_history),
            "by_severity": {
                severity.value: sum(1 for alert in self.alert_history if alert.severity == severity)
                for severity in AlertSeverity
            },
            "by_rule": {
                rule.name: sum(1 for alert in self.alert_history if alert.rule_id == rule.rule_id)
                for rule in self.alert_rules.values()
            },
            "active_rules": len([rule for rule in self.alert_rules.values() if rule.enabled]),
            "recent_alerts_24h": len(
                [alert for alert in self.alert_history if now - alert.timestamp < timedelta(hours=24)]
            ),
            "recent_alerts_1h": len(
                [alert for alert in self.alert_history if now - alert.timestamp < timedelta(hours=1)]
            ),
            "alerts_today": len([alert for alert in self.alert_history if alert.timestamp.date() == now.date()]),
        }

    def clear_old_alerts(self, days: int = 7) -> int:
        cutoff = datetime.now() - timedelta(days=days)
        before = len(self.alert_history)
        self.alert_history = [alert for alert in self.alert_history if alert.timestamp >= cutoff]
        return before - len(self.alert_history)

    def get_channels_status(self) -> Dict[str, bool]:
        return {name: bool(getattr(channel, "enabled", True)) for name, channel in self.channels.items()}

    def get_active_alerts(self) -> List[Dict[str, object]]:
        recent = [
            alert
            for alert in self.alert_history
            if alert.severity in {AlertSeverity.WARNING, AlertSeverity.ERROR, AlertSeverity.CRITICAL}
        ]
        recent = sorted(recent, key=lambda alert: alert.timestamp, reverse=True)
        return [
            {
                "alert_id": alert.alert_id,
                "rule_name": alert.rule_name,
                "severity": alert.severity.value,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
            }
            for alert in recent[:10]
        ]

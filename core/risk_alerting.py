"""风险告警系统

职责：
- 多通道风险告警（邮件、SMS、Webhook、Dashboard等）
- 告警历史管理
- 告警冷却期控制（防止告警风暴）
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict

from .risk_types import RiskEvent, AlertSeverity


logger = logging.getLogger(__name__)


class AlertChannel:
    """告警通道基类"""
    
    def send(self, event: RiskEvent) -> bool:
        """发送告警"""
        raise NotImplementedError


class EmailNotifier(AlertChannel):
    """邮件通知器"""
    
    def __init__(self, smtp_server: str = None, smtp_port: int = 587, 
                 username: str = None, password: str = None):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.enabled = bool(smtp_server and username and password)
    
    def send(self, event: RiskEvent) -> bool:
        """发送邮件告警"""
        if not self.enabled:
            logger.debug("邮件通知未配置，跳过发送")
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = self.username  # 可以配置接收邮箱
            msg['Subject'] = f"[风险告警] {event.severity.value.upper()}: {event.event_type}"
            
            body = f"""
风险告警详情：
- 时间: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
- 类型: {event.event_type}
- 严重程度: {event.severity.value}
- 消息: {event.message}
- 标的: {event.symbol or 'N/A'}
- 详情: {json.dumps(event.details, ensure_ascii=False, indent=2)}
            """
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"邮件告警已发送: {event.event_type}")
            return True
        except Exception as e:
            logger.error(f"发送邮件告警失败: {e}")
            return False


class SMSNotifier(AlertChannel):
    """短信通知器（Twilio REST API）"""

    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        provider: str = "twilio",
        from_number: str = None,
        to_numbers: Optional[List[str] | str] = None,
        api_base_url: str = None,
        timeout: int = 5,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.provider = (provider or "twilio").strip().lower()
        self.from_number = (from_number or "").strip()
        self.to_numbers = self._normalize_recipients(to_numbers)
        self.api_base_url = (api_base_url or "https://api.twilio.com").rstrip("/")
        self.timeout = timeout
        self.enabled = bool(
            self.provider == "twilio"
            and self.api_key
            and self.api_secret
            and self.from_number
            and self.to_numbers
        )

    @staticmethod
    def _normalize_recipients(to_numbers: Optional[List[str] | str]) -> List[str]:
        if isinstance(to_numbers, str):
            items = to_numbers.split(",")
        else:
            items = to_numbers or []
        return [item.strip() for item in items if item and item.strip()]

    def _build_message(self, event: RiskEvent) -> str:
        symbol = f" {event.symbol}" if event.symbol else ""
        return (
            f"[{event.severity.value.upper()}] {event.event_type}{symbol}: "
            f"{event.message}"
        )

    def send(self, event: RiskEvent) -> bool:
        """发送短信告警"""
        if not self.enabled:
            logger.debug("短信通知未配置，跳过发送")
            return False

        if self.provider != "twilio":
            logger.error("不支持的短信提供商: %s", self.provider)
            return False

        try:
            import requests

            message = self._build_message(event)
            endpoint = f"{self.api_base_url}/2010-04-01/Accounts/{self.api_key}/Messages.json"
            success_count = 0

            for recipient in self.to_numbers:
                response = requests.post(
                    endpoint,
                    data={
                        "From": self.from_number,
                        "To": recipient,
                        "Body": message,
                    },
                    auth=(self.api_key, self.api_secret),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                success_count += 1

            logger.info(
                "短信告警已发送: %s, recipients=%s",
                event.event_type,
                ",".join(self.to_numbers),
            )
            return success_count == len(self.to_numbers)
        except Exception as e:
            logger.error(f"发送短信告警失败: {e}")
            return False


class WebhookNotifier(AlertChannel):
    """Webhook通知器"""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
    
    def send(self, event: RiskEvent) -> bool:
        """发送Webhook告警"""
        if not self.enabled:
            logger.debug("Webhook未配置，跳过发送")
            return False
        
        try:
            import requests
            
            payload = {
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "severity": event.severity.value,
                "message": event.message,
                "symbol": event.symbol,
                "details": event.details
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5
            )
            response.raise_for_status()
            
            logger.info(f"Webhook告警已发送: {event.event_type}")
            return True
        except Exception as e:
            logger.error(f"发送Webhook告警失败: {e}")
            return False


class DashboardNotifier(AlertChannel):
    """Dashboard通知器（将告警记录到日志或数据库）"""
    
    def __init__(self, log_file: str = None):
        self.log_file = log_file
        self.enabled = True
    
    def send(self, event: RiskEvent) -> bool:
        """记录Dashboard告警"""
        try:
            # 记录到日志
            log_level = {
                AlertSeverity.INFO: logging.INFO,
                AlertSeverity.WARNING: logging.WARNING,
                AlertSeverity.ERROR: logging.ERROR,
                AlertSeverity.CRITICAL: logging.CRITICAL
            }.get(event.severity, logging.INFO)
            
            logger.log(
                log_level,
                f"风险告警 [{event.severity.value}]: {event.event_type} - {event.message}"
            )
            
            # 如果指定了日志文件，也可以写入文件
            if self.log_file:
                try:
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(f"{event.timestamp.isoformat()} [{event.severity.value}] {event.event_type}: {event.message}\n")
                except Exception as e:
                    logger.error(f"写入告警日志文件失败: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Dashboard告警记录失败: {e}")
            return False


class RiskAlerting:
    """风险告警系统"""

    def __init__(
        self,
        email_config: Dict = None,
        sms_config: Dict = None,
        webhook_url: str = None,
        log_file: str = None
    ):
        """
        初始化风险告警系统

        Args:
            email_config: 邮件配置 {'smtp_server', 'smtp_port', 'username', 'password'}
            sms_config: 短信配置 {'api_key', 'api_secret', 'provider', 'from_number', 'to_numbers'}
            webhook_url: Webhook URL
            log_file: 告警日志文件路径
        """
        # 初始化告警通道
        self.alert_channels: Dict[str, AlertChannel] = {}
        
        # 邮件通知
        if email_config:
            self.alert_channels['email'] = EmailNotifier(**email_config)
        
        # 短信通知
        if sms_config:
            self.alert_channels['sms'] = SMSNotifier(**sms_config)
        
        # Webhook通知
        if webhook_url:
            self.alert_channels['webhook'] = WebhookNotifier(webhook_url)
        
        # Dashboard通知（总是启用）
        self.alert_channels['dashboard'] = DashboardNotifier(log_file)
        
        # 告警历史
        self.alert_history: List[RiskEvent] = []
        self.max_history = 1000
        
        # 告警冷却期（防止告警风暴）
        self.cooldown_periods: Dict[str, timedelta] = {
            AlertSeverity.INFO: timedelta(minutes=30),
            AlertSeverity.WARNING: timedelta(minutes=10),
            AlertSeverity.ERROR: timedelta(minutes=5),
            AlertSeverity.CRITICAL: timedelta(minutes=0)  # 严重告警不设冷却期
        }
        
        # 上次告警时间 {alert_key: datetime}
        self.last_alert_times: Dict[str, datetime] = {}
        
        # 告警统计
        self.alert_stats = defaultdict(int)
        
        logger.info(f"风险告警系统初始化完成，已启用通道: {list(self.alert_channels.keys())}")

    def send_alert(
        self,
        alert_type: str,
        severity: AlertSeverity,
        message: str,
        data: Optional[Dict] = None,
        symbol: Optional[str] = None,
        portfolio_id: Optional[str] = None
    ):
        """
        发送告警

        Args:
            alert_type: 告警类型
            severity: 严重程度
            message: 告警消息
            data: 附加数据
            symbol: 标的代码
            portfolio_id: 组合ID
        """
        # 创建风险事件
        event = RiskEvent(
            event_id=f"{alert_type}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            event_type=alert_type,
            severity=severity,
            message=message,
            symbol=symbol,
            portfolio_id=portfolio_id,
            details=data or {}
        )
        
        # 检查冷却期
        alert_key = f"{alert_type}_{symbol or 'global'}"
        if not self._should_send_alert(event, alert_key):
            logger.debug(f"告警在冷却期内，跳过: {alert_key}")
            return
        
        # 记录告警历史
        self.alert_history.append(event)
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        # 更新统计
        self.alert_stats[alert_type] += 1
        self.last_alert_times[alert_key] = datetime.now()
        
        # 根据严重程度选择通知渠道
        channels_to_use = self._select_channels(severity)
        
        # 发送告警
        success_count = 0
        for channel_name in channels_to_use:
            if channel_name in self.alert_channels:
                channel = self.alert_channels[channel_name]
                if channel.send(event):
                    success_count += 1
        
        logger.info(
            f"告警已发送: {alert_type} [{severity.value}], "
            f"通道={channels_to_use}, 成功={success_count}/{len(channels_to_use)}"
        )

    def _should_send_alert(self, event: RiskEvent, alert_key: str) -> bool:
        """判断是否应该发送告警（考虑冷却期）"""
        # 严重告警不设冷却期
        if event.severity == AlertSeverity.CRITICAL:
            return True
        
        # 检查冷却期
        cooldown = self.cooldown_periods.get(event.severity, timedelta(minutes=10))
        if cooldown.total_seconds() == 0:
            return True
        
        last_time = self.last_alert_times.get(alert_key)
        if last_time is None:
            return True
        
        elapsed = datetime.now() - last_time
        return elapsed >= cooldown

    def _select_channels(self, severity: AlertSeverity) -> List[str]:
        """根据严重程度选择通知渠道"""
        # 总是使用Dashboard
        channels = ['dashboard']
        
        # 根据严重程度添加其他渠道
        if severity == AlertSeverity.CRITICAL:
            # 严重告警：所有渠道
            channels.extend(['email', 'sms', 'webhook'])
        elif severity == AlertSeverity.ERROR:
            # 错误告警：邮件和Webhook
            channels.extend(['email', 'webhook'])
        elif severity == AlertSeverity.WARNING:
            # 警告：仅邮件
            channels.append('email')
        # INFO级别仅使用Dashboard
        
        # 过滤掉未配置的渠道
        return [ch for ch in channels if ch in self.alert_channels]

    def get_alert_history(
        self,
        limit: int = 100,
        severity: Optional[AlertSeverity] = None,
        event_type: Optional[str] = None
    ) -> List[Dict]:
        """
        获取告警历史

        Args:
            limit: 返回数量限制
            severity: 过滤严重程度
            event_type: 过滤事件类型

        Returns:
            告警历史列表
        """
        filtered = self.alert_history
        
        if severity:
            filtered = [e for e in filtered if e.severity == severity]
        
        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]
        
        # 按时间倒序
        filtered = sorted(filtered, key=lambda x: x.timestamp, reverse=True)
        
        return [
            {
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "severity": event.severity.value,
                "message": event.message,
                "symbol": event.symbol,
                "details": event.details
            }
            for event in filtered[:limit]
        ]

    def get_alert_stats(self) -> Dict:
        """获取告警统计信息"""
        return {
            "total_alerts": len(self.alert_history),
            "by_type": dict(self.alert_stats),
            "by_severity": {
                severity.value: sum(1 for e in self.alert_history if e.severity == severity)
                for severity in AlertSeverity
            },
            "recent_alerts": len([
                e for e in self.alert_history
                if (datetime.now() - e.timestamp) < timedelta(hours=24)
            ])
        }

    def clear_alert_history(self):
        """清空告警历史"""
        self.alert_history.clear()
        self.last_alert_times.clear()
        self.alert_stats.clear()
        logger.info("告警历史已清空")

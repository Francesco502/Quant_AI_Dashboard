"""监控配置模块

职责：
- 监控系统配置管理
- 告警规则配置
- 数据保存和清理策略
"""

from __future__ import annotations

import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """告警严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthCheckInterval(Enum):
    """健康检查间隔"""
    IMMEDIATE = "immediate"     # 立即
    FAST = "fast"               # 快速 (30秒)
    NORMAL = "normal"           # 正常 (60秒)
    SLOW = "slow"               # 缓慢 (300秒)


@dataclass
class SystemMonitorConfig:
    """系统监控配置"""
    # 指标收集间隔（秒）
    collection_interval: float = 60.0

    # 是否启用系统指标收集
    enabled: bool = True

    # 系统指标阈值
    cpu_warning_threshold: float = 70.0      # CPU警告阈值（百分比）
    cpu_critical_threshold: float = 90.0     # CPU严重阈值
    memory_warning_threshold: float = 70.0   # 内存警告阈值
    memory_critical_threshold: float = 85.0  # 内存严重阈值
    disk_warning_threshold: float = 80.0     # 磁盘警告阈值
    disk_critical_threshold: float = 90.0    # 磁盘严重阈值

    # 2GB低配服务器优化配置
    memory_limit_mb: int = 1800  # 预留200MB给系统
    gc_cleanup_threshold: float = 0.75  # 超过75%内存时触发GC

    def is_under_memory_pressure(self, memory_percent: float) -> bool:
        """判断是否处于内存压力状态"""
        return memory_percent >= self.gc_cleanup_threshold * 100


@dataclass
class AlertRuleConfig:
    """告警规则配置"""
    name: str
    metric_name: str
    severity: AlertSeverity
    threshold: float
    comparison: str  # "gt", "lt", "gte", "lte"
    cooldown_minutes: int = 5
    enabled: bool = True
    channels: List[str] = field(default_factory=lambda: ["dashboard"])


@dataclass
class AlertChannelConfig:
    """告警渠道配置"""
    name: str
    enabled: bool = True
    type: str = "dashboard"  # dashboard, email, webhook, telegram, dingtalk,Feishu

    # 邮件配置
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    to_email: Optional[str] = None

    # Webhook配置
    webhook_url: Optional[str] = None

    # Telegram配置
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # 钉钉配置
    dingtalk_webhook_url: Optional[str] = None

    # 飞书配置
    feishu_webhook_url: Optional[str] = None
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None

    # 企业微信配置
    wecom_webhook_url: Optional[str] = None


@dataclass
class MonitoringConfig:
    """监控系统总配置"""
    # 系统监控配置
    system: SystemMonitorConfig = field(default_factory=SystemMonitorConfig)

    # 告警规则
    alert_rules: List[AlertRuleConfig] = field(default_factory=list)

    # 告警渠道
    alert_channels: Dict[str, AlertChannelConfig] = field(default_factory=dict)

    # 健康检查配置
    health_check_interval: int = 60  # 秒
    health_check_timeout: int = 10   # 秒

    # 告警风暴防护
    alert_cooldown_default: int = 5  # 默认冷却期（分钟）
    max_alerts_per_hour: int = 10    # 每小时最大告警数

    # 数据保留策略
    max_alert_history: int = 1000
    max_metric_history_hours: int = 24

    # 数据源健康检查配置
    data_source_check_enabled: bool = True
    data_source_timeout: int = 30  # 秒

    def __post_init__(self):
        """初始化默认配置"""
        if not self.alert_rules:
            self._init_default_rules()

        if not self.alert_channels:
            self._init_default_channels()

    def _init_default_rules(self) -> None:
        """初始化默认告警规则"""
        self.alert_rules = [
            AlertRuleConfig(
                name="CPU使用率过高",
                metric_name="cpu_usage",
                severity=AlertSeverity.WARNING,
                threshold=70.0,
                comparison="gt",
                cooldown_minutes=10,
                channels=["dashboard"]
            ),
            AlertRuleConfig(
                name="CPU使用率严重过高",
                metric_name="cpu_usage",
                severity=AlertSeverity.CRITICAL,
                threshold=90.0,
                comparison="gt",
                cooldown_minutes=5,
                channels=["dashboard"]
            ),
            AlertRuleConfig(
                name="内存使用率过高",
                metric_name="memory_usage",
                severity=AlertSeverity.WARNING,
                threshold=70.0,
                comparison="gt",
                cooldown_minutes=10,
                channels=["dashboard"]
            ),
            AlertRuleConfig(
                name="内存使用率严重过高",
                metric_name="memory_usage",
                severity=AlertSeverity.CRITICAL,
                threshold=85.0,
                comparison="gt",
                cooldown_minutes=5,
                channels=["dashboard"]
            ),
            AlertRuleConfig(
                name="磁盘空间不足",
                metric_name="disk_usage",
                severity=AlertSeverity.WARNING,
                threshold=80.0,
                comparison="gt",
                cooldown_minutes=60,
                channels=["dashboard"]
            ),
            AlertRuleConfig(
                name="磁盘空间严重不足",
                metric_name="disk_usage",
                severity=AlertSeverity.CRITICAL,
                threshold=90.0,
                comparison="gt",
                cooldown_minutes=30,
                channels=["dashboard"]
            ),
            AlertRuleConfig(
                name="数据更新延迟",
                metric_name="data_update_latency",
                severity=AlertSeverity.WARNING,
                threshold=300.0,  # 5分钟
                comparison="gt",
                cooldown_minutes=15,
                channels=["dashboard"]
            ),
            AlertRuleConfig(
                name="API响应时间过长",
                metric_name="api_response_time",
                severity=AlertSeverity.WARNING,
                threshold=5.0,  # 5秒
                comparison="gt",
                cooldown_minutes=10,
                channels=["dashboard"]
            ),
        ]

    def _init_default_channels(self) -> None:
        """初始化默认告警渠道"""
        # 默认dashboard渠道始终启用
        self.alert_channels["dashboard"] = AlertChannelConfig(
            name="Dashboard",
            enabled=True,
            type="dashboard"
        )

        # 从环境变量读取其他渠道配置
        self._load_channels_from_env()

    def _load_channels_from_env(self) -> None:
        """从环境变量加载渠道配置"""
        # 邮件渠道
        smtp_server = os.getenv("ALERT_EMAIL_SMTP_SERVER")
        if smtp_server:
            self.alert_channels["email"] = AlertChannelConfig(
                name="Email",
                enabled=True,
                type="email",
                smtp_server=smtp_server,
                smtp_port=int(os.getenv("ALERT_EMAIL_SMTP_PORT", "587")),
                username=os.getenv("ALERT_EMAIL_USERNAME"),
                password=os.getenv("ALERT_EMAIL_PASSWORD"),
                to_email=os.getenv("ALERT_EMAIL_TO", os.getenv("ALERT_EMAIL_USERNAME"))
            )
            logger.info("已配置邮件告警渠道")

        # Webhook渠道
        webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        if webhook_url:
            self.alert_channels["webhook"] = AlertChannelConfig(
                name="Webhook",
                enabled=True,
                type="webhook",
                webhook_url=webhook_url
            )
            logger.info("已配置Webhook告警渠道")

        # Telegram渠道
        tg_token = os.getenv("ALERT_TELEGRAM_BOT_TOKEN")
        tg_chat_id = os.getenv("ALERT_TELEGRAM_CHAT_ID")
        if tg_token and tg_chat_id:
            self.alert_channels["telegram"] = AlertChannelConfig(
                name="Telegram",
                enabled=True,
                type="telegram",
                telegram_bot_token=tg_token,
                telegram_chat_id=tg_chat_id
            )
            logger.info("已配置Telegram告警渠道")

        # 飞书渠道
        feishu_url = os.getenv("ALERT_FEISHU_WEBHOOK_URL")
        if feishu_url:
            self.alert_channels["feishu"] = AlertChannelConfig(
                name="Feishu",
                enabled=True,
                type="feishu",
                feishu_webhook_url=feishu_url
            )
            logger.info("已配置飞书告警渠道")

        # 企业微信渠道
        wecom_url = os.getenv("ALERT_WECOM_WEBHOOK_URL")
        if wecom_url:
            self.alert_channels["wecom"] = AlertChannelConfig(
                name="WeCom",
                enabled=True,
                type="wecom",
                wecom_webhook_url=wecom_url
            )
            logger.info("已配置企业微信告警渠道")


# 全局配置实例
_global_config: Optional[MonitoringConfig] = None


def get_monitoring_config() -> MonitoringConfig:
    """获取全局监控配置"""
    global _global_config
    if _global_config is None:
        _global_config = MonitoringConfig()
    return _global_config


def reload_monitoring_config() -> MonitoringConfig:
    """重新加载监控配置"""
    global _global_config
    _global_config = MonitoringConfig()
    return _global_config

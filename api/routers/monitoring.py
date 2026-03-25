"""Monitoring and alert management routes."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.monitoring import (
    Alert,
    AlertChannel,
    AlertManager,
    AlertSeverity,
    ComparisonOperator,
    DashboardChannel,
    DingTalkChannel,
    EmailChannel,
    FeishuChannel,
    TelegramChannel,
    WebhookChannel,
    WeComChannel,
    get_monitoring_config,
    get_system_monitor,
    restart_system_monitor,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["system-monitoring"])

_alert_manager: Optional[AlertManager] = None


class AlertChannelTestRequest(BaseModel):
    channel_type: str = Field(..., description="email/webhook/telegram/dingtalk/feishu/wecom")
    config: Dict[str, Any] = Field(default_factory=dict)


def _comparison_from_config(value: str) -> ComparisonOperator:
    mapping = {
        "gt": ComparisonOperator.GT,
        "lt": ComparisonOperator.LT,
        "gte": ComparisonOperator.GTE,
        "lte": ComparisonOperator.LTE,
        ">": ComparisonOperator.GT,
        "<": ComparisonOperator.LT,
        ">=": ComparisonOperator.GTE,
        "<=": ComparisonOperator.LTE,
        "==": ComparisonOperator.EQ,
        "eq": ComparisonOperator.EQ,
        "!=": ComparisonOperator.NE,
        "ne": ComparisonOperator.NE,
    }
    return mapping.get((value or "").strip().lower(), ComparisonOperator.GT)


def _build_channel(channel_type: str, config: Dict[str, Any]) -> AlertChannel:
    kind = (channel_type or "").strip().lower()
    if kind == "email":
        return EmailChannel(
            smtp_server=config.get("smtp_server"),
            smtp_port=int(config.get("smtp_port", 587)),
            username=config.get("username"),
            password=config.get("password"),
            to_email=config.get("to_email"),
        )
    if kind == "webhook":
        return WebhookChannel(webhook_url=config.get("webhook_url"))
    if kind == "telegram":
        return TelegramChannel(
            bot_token=config.get("bot_token"),
            chat_id=config.get("chat_id"),
        )
    if kind == "dingtalk":
        return DingTalkChannel(
            webhook_url=config.get("webhook_url"),
            secret=config.get("secret"),
        )
    if kind == "feishu":
        return FeishuChannel(
            webhook_url=config.get("webhook_url"),
            secret=config.get("secret"),
        )
    if kind == "wecom":
        return WeComChannel(webhook_url=config.get("webhook_url"))
    raise HTTPException(status_code=400, detail=f"Unknown alert channel type: {channel_type}")


def _get_alert_manager() -> AlertManager:
    global _alert_manager
    if _alert_manager is not None:
        return _alert_manager

    config = get_monitoring_config()
    manager = AlertManager(max_history=config.max_alert_history)
    manager.set_alert_frequency_limit(config.max_alerts_per_hour)

    for rule in config.alert_rules:
        manager.add_alert_rule(
            name=rule.name,
            metric_name=rule.metric_name,
            threshold=rule.threshold,
            comparison=_comparison_from_config(rule.comparison),
            severity=rule.severity,
            cooldown_minutes=rule.cooldown_minutes,
            channels=rule.channels,
        )

    _alert_manager = manager
    return manager


@router.get("/health")
async def get_health_status() -> Dict[str, Any]:
    try:
        return {"status": "success", "data": get_system_monitor().check_health()}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get monitoring health: %s", exc)
        raise HTTPException(status_code=500, detail=f"Health check failed: {exc}") from exc


@router.get("/metrics")
async def get_system_metrics() -> Dict[str, Any]:
    try:
        return {"status": "success", "data": get_system_monitor().collect_metrics()}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to collect system metrics: %s", exc)
        raise HTTPException(status_code=500, detail=f"Metrics collection failed: {exc}") from exc


@router.get("/metrics/detailed")
async def get_detailed_metrics() -> Dict[str, Any]:
    try:
        return {"status": "success", "data": get_system_monitor().collect_detailed_metrics()}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to collect detailed system metrics: %s", exc)
        raise HTTPException(status_code=500, detail=f"Detailed metrics collection failed: {exc}") from exc


@router.get("/metrics/history")
async def get_metrics_history(metric_name: str, minutes: int = 60) -> Dict[str, Any]:
    try:
        history = get_system_monitor().get_metrics_history(metric_name, minutes)
        return {
            "status": "success",
            "data": {
                "metric_name": metric_name,
                "minutes": minutes,
                "history": history,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get metrics history for %s: %s", metric_name, exc)
        raise HTTPException(status_code=500, detail=f"Metrics history retrieval failed: {exc}") from exc


@router.get("/metrics/statistics")
async def get_metric_statistics(window_minutes: int = 60) -> Dict[str, Any]:
    try:
        stats = get_system_monitor().get_all_metric_statistics(window_minutes)
        return {"status": "success", "data": stats}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get metric statistics: %s", exc)
        raise HTTPException(status_code=500, detail=f"Metric statistics retrieval failed: {exc}") from exc


@router.get("/summary")
async def get_system_summary() -> Dict[str, Any]:
    try:
        return {"status": "success", "data": get_system_monitor().get_system_summary()}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get monitoring summary: %s", exc)
        raise HTTPException(status_code=500, detail=f"System summary retrieval failed: {exc}") from exc


@router.get("/status")
async def get_monitoring_status() -> Dict[str, Any]:
    try:
        status = get_system_monitor().get_monitoring_status()
        return {
            "status": "success",
            "data": {
                "is_monitoring": status.is_monitoring,
                "uptime_seconds": status.uptime_seconds,
                "metrics_collected": status.metrics_collected,
                "health_checks": status.health_checks_performed,
                "last_metric_time": status.last_metric_time.isoformat() if status.last_metric_time else None,
                "last_health_check_time": (
                    status.last_health_check_time.isoformat() if status.last_health_check_time else None
                ),
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get monitoring status: %s", exc)
        raise HTTPException(status_code=500, detail=f"Monitoring status retrieval failed: {exc}") from exc


@router.get("/alert/rules")
async def get_alert_rules() -> Dict[str, Any]:
    try:
        config = get_monitoring_config()
        rules = [
            {
                "name": rule.name,
                "metric_name": rule.metric_name,
                "severity": rule.severity.value,
                "threshold": rule.threshold,
                "comparison": rule.comparison,
                "cooldown_minutes": rule.cooldown_minutes,
                "enabled": rule.enabled,
                "channels": rule.channels,
            }
            for rule in config.alert_rules
        ]
        return {"status": "success", "data": rules}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get alert rules: %s", exc)
        raise HTTPException(status_code=500, detail=f"Alert rules retrieval failed: {exc}") from exc


@router.get("/alert/channels")
async def get_alert_channels() -> Dict[str, Any]:
    try:
        config = get_monitoring_config()
        channels = [
            {
                "name": channel.name,
                "enabled": channel.enabled,
                "type": channel.type,
                "smtp_server": channel.smtp_server if channel.type == "email" else None,
                "webhook_url": (
                    channel.webhook_url
                    if channel.type in {"webhook", "dingtalk", "feishu", "wecom"}
                    else None
                ),
            }
            for channel in config.alert_channels.values()
        ]
        return {"status": "success", "data": channels}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get alert channels: %s", exc)
        raise HTTPException(status_code=500, detail=f"Alert channels retrieval failed: {exc}") from exc


@router.post("/alert/test")
async def test_alert_channel(payload: AlertChannelTestRequest) -> Dict[str, Any]:
    try:
        channel = _build_channel(payload.channel_type, payload.config)
        if not getattr(channel, "enabled", True):
            raise HTTPException(status_code=400, detail="Alert channel is not enabled")

        test_alert = Alert(
            alert_id="TEST_ALERT",
            rule_id="TEST_RULE",
            rule_name="Test Alert",
            severity=AlertSeverity.INFO,
            message="This is a monitoring test alert.",
            metric_name="test_metric",
            metric_value=100.0,
            threshold=50.0,
            timestamp=datetime.now(),
            channels=[payload.channel_type],
        )

        if not channel.send(test_alert):
            raise HTTPException(status_code=500, detail="Failed to send test alert")

        return {
            "status": "success",
            "message": "Test alert sent successfully.",
            "data": {"success": True},
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send test alert: %s", exc)
        raise HTTPException(status_code=500, detail=f"Test alert failed: {exc}") from exc


@router.get("/alert/history")
async def get_alert_history(limit: int = 100, severity: Optional[str] = None) -> Dict[str, Any]:
    try:
        severity_enum = None
        if severity:
            try:
                severity_enum = AlertSeverity(severity.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Unknown severity: {severity}") from None

        history = _get_alert_manager().get_alert_history(limit=limit, severity=severity_enum)
        return {"status": "success", "data": history}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get alert history: %s", exc)
        raise HTTPException(status_code=500, detail=f"Alert history retrieval failed: {exc}") from exc


@router.get("/alert/statistics")
async def get_alert_statistics() -> Dict[str, Any]:
    try:
        return {"status": "success", "data": _get_alert_manager().get_alert_statistics()}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get alert statistics: %s", exc)
        raise HTTPException(status_code=500, detail=f"Alert statistics retrieval failed: {exc}") from exc


@router.post("/restart")
async def restart_monitoring() -> Dict[str, Any]:
    try:
        monitor = restart_system_monitor()
        return {
            "status": "success",
            "message": "Monitoring restarted successfully.",
            "data": {
                "is_monitoring": monitor.is_monitoring,
                "uptime_seconds": 0,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to restart monitoring: %s", exc)
        raise HTTPException(status_code=500, detail=f"Monitoring restart failed: {exc}") from exc


@router.get("/config")
async def get_monitoring_config_api() -> Dict[str, Any]:
    try:
        config = get_monitoring_config()
        return {
            "status": "success",
            "data": {
                "collection_interval": config.system.collection_interval,
                "cpu_warning_threshold": config.system.cpu_warning_threshold,
                "cpu_critical_threshold": config.system.cpu_critical_threshold,
                "memory_warning_threshold": config.system.memory_warning_threshold,
                "memory_critical_threshold": config.system.memory_critical_threshold,
                "disk_warning_threshold": config.system.disk_warning_threshold,
                "disk_critical_threshold": config.system.disk_critical_threshold,
                "health_check_interval": config.health_check_interval,
                "max_alerts_per_hour": config.max_alerts_per_hour,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get monitoring config: %s", exc)
        raise HTTPException(status_code=500, detail=f"Monitoring config retrieval failed: {exc}") from exc

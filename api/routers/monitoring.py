"""监控和告警API路由

提供系统监控和告警管理的RESTful API接口
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, List, Optional
from datetime import datetime
import logging

from core.monitoring import (
    get_system_monitor,
    get_monitoring_config,
    AlertManager,
    AlertSeverity,
    ComparisonOperator,
    DashboardChannel,
    EmailChannel,
    WebhookChannel,
    TelegramChannel,
    DingTalkChannel,
    FeishuChannel,
    WeComChannel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["系统监控"])


@router.get("/health")
async def get_health_status():
    """
    获取健康检查状态

    Returns:
        健康状态和各项检查结果
    """
    try:
        monitor = get_system_monitor()
        health_status = monitor.check_health()

        return {
            "status": "success",
            "data": health_status,
        }
    except Exception as e:
        logger.error(f"获取健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")


@router.get("/metrics")
async def get_system_metrics():
    """
    获取系统指标

    Returns:
        系统指标数据
    """
    try:
        monitor = get_system_monitor()
        metrics = monitor.collect_metrics()

        return {
            "status": "success",
            "data": metrics,
        }
    except Exception as e:
        logger.error(f"获取系统指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"指标收集失败: {str(e)}")


@router.get("/metrics/detailed")
async def get_detailed_metrics():
    """
    获取详细系统指标（用于监控页面）

    Returns:
        详细系统指标数据
    """
    try:
        monitor = get_system_monitor()
        metrics = monitor.collect_detailed_metrics()

        return {
            "status": "success",
            "data": metrics,
        }
    except Exception as e:
        logger.error(f"获取详细系统指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"详细指标收集失败: {str(e)}")


@router.get("/metrics/history")
async def get_metrics_history(
    metric_name: str,
    minutes: int = 60,
):
    """
    获取指标历史数据

    Args:
        metric_name: 指标名称 (cpu_usage, memory_usage, disk_usage等)
        minutes: 时间范围（分钟）

    Returns:
        指标历史数据
    """
    try:
        monitor = get_system_monitor()
        history = monitor.get_metrics_history(metric_name, minutes)

        return {
            "status": "success",
            "data": {
                "metric_name": metric_name,
                "minutes": minutes,
                "history": history,
            },
        }
    except Exception as e:
        logger.error(f"获取指标历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"历史数据获取失败: {str(e)}")


@router.get("/metrics/statistics")
async def get_metric_statistics(
    window_minutes: int = 60,
):
    """
    获取指标统计信息

    Args:
        window_minutes: 时间窗口（分钟）

    Returns:
        指标统计信息
    """
    try:
        monitor = get_system_monitor()
        stats = monitor.get_all_metric_statistics(window_minutes)

        return {
            "status": "success",
            "data": stats,
        }
    except Exception as e:
        logger.error(f"获取指标统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"统计信息获取失败: {str(e)}")


@router.get("/summary")
async def get_system_summary():
    """
    获取系统汇总信息

    Returns:
        系统汇总数据
    """
    try:
        monitor = get_system_monitor()
        summary = monitor.get_system_summary()

        return {
            "status": "success",
            "data": summary,
        }
    except Exception as e:
        logger.error(f"获取系统汇总失败: {e}")
        raise HTTPException(status_code=500, detail=f"汇总信息获取失败: {str(e)}")


@router.get("/status")
async def get_monitoring_status():
    """
    获取监控状态

    Returns:
        监控运行状态
    """
    try:
        monitor = get_system_monitor()
        status = monitor.get_monitoring_status()

        return {
            "status": "success",
            "data": {
                "is_monitoring": status.is_monitoring,
                "uptime_seconds": status.uptime_seconds,
                "metrics_collected": status.metrics_collected,
                "health_checks": status.health_checks,
                "last_metric_time": status.last_metric_time.isoformat() if status.last_metric_time else None,
            },
        }
    except Exception as e:
        logger.error(f"获取监控状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"监控状态获取失败: {str(e)}")


# 告警配置和管理相关API

@router.get("/alert/rules")
async def get_alert_rules():
    """
    获取告警规则列表

    Returns:
        告警规则列表
    """
    try:
        config = get_monitoring_config()
        rules = []

        for rule in config.alert_rules:
            rules.append({
                "name": rule.name,
                "metric_name": rule.metric_name,
                "severity": rule.severity.value,
                "threshold": rule.threshold,
                "comparison": rule.comparison,
                "cooldown_minutes": rule.cooldown_minutes,
                "enabled": rule.enabled,
                "channels": rule.channels,
            })

        return {
            "status": "success",
            "data": rules,
        }
    except Exception as e:
        logger.error(f"获取告警规则失败: {e}")
        raise HTTPException(status_code=500, detail=f"告警规则获取失败: {str(e)}")


@router.get("/alert/channels")
async def get_alert_channels():
    """
    获取告警渠道配置

    Returns:
        告警渠道配置列表
    """
    try:
        config = get_monitoring_config()
        channels = []

        for name, channel in config.alert_channels.items():
            channels.append({
                "name": channel.name,
                "enabled": channel.enabled,
                "type": channel.type,
                # 不返回敏感信息
                "smtp_server": channel.smtp_server if channel.type == "email" else None,
                "webhook_url": channel.webhook_url if channel.type in ["webhook", "dingtalk", "feishu", "wecom"] else None,
            })

        return {
            "status": "success",
            "data": channels,
        }
    except Exception as e:
        logger.error(f"获取告警渠道失败: {e}")
        raise HTTPException(status_code=500, detail=f"告警渠道获取失败: {str(e)}")


@router.post("/alert/test")
async def test_alert_channel(
    channel_type: str,
    config: Dict,
):
    """
    测试告警渠道配置

    Args:
        channel_type: 渠道类型 (email, webhook, telegram, dingtalk, feishu, wecom)
        config: 渠道配置

    Returns:
        测试结果
    """
    try:
        channel: Optional[AlertChannel] = None

        if channel_type == "email":
            channel = EmailChannel(
                smtp_server=config.get("smtp_server"),
                smtp_port=config.get("smtp_port", 587),
                username=config.get("username"),
                password=config.get("password"),
                to_email=config.get("to_email"),
            )
        elif channel_type == "webhook":
            channel = WebhookChannel(webhook_url=config.get("webhook_url"))
        elif channel_type == "telegram":
            channel = TelegramChannel(
                bot_token=config.get("bot_token"),
                chat_id=config.get("chat_id"),
            )
        elif channel_type == "dingtalk":
            channel = DingTalkChannel(
                webhook_url=config.get("webhook_url"),
                secret=config.get("secret"),
            )
        elif channel_type == "feishu":
            channel = FeishuChannel(
                webhook_url=config.get("webhook_url"),
                secret=config.get("secret"),
            )
        elif channel_type == "wecom":
            channel = WeComChannel(webhook_url=config.get("webhook_url"))
        else:
            raise HTTPException(status_code=400, detail=f"未知的告警渠道类型: {channel_type}")

        if not channel.enabled:
            raise HTTPException(status_code=400, detail="告警渠道未启用")

        # 创建测试告警
        from core.monitoring import Alert, AlertSeverity
        test_alert = Alert(
            alert_id="TEST_ALERT",
            rule_id="TEST_RULE",
            rule_name="测试告警",
            severity=AlertSeverity.INFO,
            message="这是一条测试告警消息。如果您收到此消息，说明告警渠道配置正确。",
            metric_name="test_metric",
            metric_value=100.0,
            threshold=50.0,
            timestamp=datetime.now(),
            channels=[channel_type],
        )

        success = channel.send(test_alert)

        if success:
            return {
                "status": "success",
                "message": "测试告警发送成功，请检查您的接收端",
                "data": {"success": True},
            }
        else:
            raise HTTPException(status_code=500, detail="测试告警发送失败，请检查配置")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试告警渠道失败: {e}")
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


@router.get("/alert/history")
async def get_alert_history(
    limit: int = 100,
    severity: Optional[str] = None,
):
    """
    获取告警历史

    Args:
        limit: 返回数量限制
        severity: 严重程度过滤 (info, warning, error, critical)

    Returns:
        告警历史数据
    """
    try:
        from core.monitoring import get_monitoring_config

        config = get_monitoring_config()
        alert_manager = AlertManager()

        # 模拟告警管理器获取历史
        severity_enum = None
        if severity:
            try:
                severity_enum = AlertSeverity(severity)
            except ValueError:
                pass

        history = alert_manager.get_alert_history(
            limit=limit,
            severity=severity_enum,
        )

        return {
            "status": "success",
            "data": history,
        }
    except Exception as e:
        logger.error(f"获取告警历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"告警历史获取失败: {str(e)}")


@router.get("/alert/statistics")
async def get_alert_statistics():
    """
    获取告警统计信息

    Returns:
        告警统计信息
    """
    try:
        from core.monitoring import get_monitoring_config

        config = get_monitoring_config()
        alert_manager = AlertManager()

        stats = alert_manager.get_alert_statistics()

        return {
            "status": "success",
            "data": stats,
        }
    except Exception as e:
        logger.error(f"获取告警统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"告警统计获取失败: {str(e)}")


@router.post("/restart")
async def restart_monitoring():
    """
    重启监控系统

    Returns:
        重启结果
    """
    try:
        from core.monitoring import restart_system_monitor

        monitor = restart_system_monitor()

        return {
            "status": "success",
            "message": "监控系统已重启",
            "data": {
                "is_monitoring": monitor.is_monitoring,
                "uptime_seconds": 0,
            },
        }
    except Exception as e:
        logger.error(f"重启监控系统失败: {e}")
        raise HTTPException(status_code=500, detail=f"重启失败: {str(e)}")


@router.get("/config")
async def get_monitoring_config_api():
    """
    获取监控配置

    Returns:
        监控配置
    """
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
    except Exception as e:
        logger.error(f"获取监控配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置获取失败: {str(e)}")

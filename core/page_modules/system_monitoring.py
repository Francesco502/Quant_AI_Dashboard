"""
系统监控页面模块
"""
import streamlit as st
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime, timedelta
from typing import Dict, Any

from core.monitoring import (
    SystemMonitor,
    MetricsCollector,
    HealthChecker,
    AlertManager,
    AlertSeverity,
    ComparisonOperator,
    EmailChannel,
    WebhookChannel,
    TelegramChannel,
    DingTalkChannel,
)
from core.apple_ui import get_apple_chart_layout, APPLE_COLORS


def render_system_monitoring_page():
    """渲染系统监控页面"""
    st.markdown("### 系统监控")
    st.caption("实时监控系统运行状态、性能指标和健康状态。")
    
    # 初始化监控组件
    if "system_monitor" not in st.session_state:
        metrics_collector = MetricsCollector()
        health_checker = HealthChecker()
        alert_manager = AlertManager(metrics_collector=metrics_collector)
        
        st.session_state.system_monitor = SystemMonitor(
            metrics_collector=metrics_collector,
            health_checker=health_checker,
            collection_interval=60.0,
        )
        st.session_state.alert_manager = alert_manager
    
    system_monitor = st.session_state.system_monitor
    alert_manager = st.session_state.alert_manager
    
    # 创建标签页
    tab_overview, tab_metrics, tab_health, tab_alerts, tab_config = st.tabs([
        "概览",
        "性能指标",
        "健康检查",
        "告警管理",
        "告警配置"
    ])
    
    # ========== 标签页：概览 ==========
    with tab_overview:
        render_overview_tab(system_monitor, alert_manager)
    
    # ========== 标签页：性能指标 ==========
    with tab_metrics:
        render_metrics_tab(system_monitor)
    
    # ========== 标签页：健康检查 ==========
    with tab_health:
        render_health_tab(system_monitor)
    
    # ========== 标签页：告警管理 ==========
    with tab_alerts:
        render_alerts_tab(alert_manager)
    
    # ========== 标签页：告警配置 ==========
    with tab_config:
        render_alert_config_tab(alert_manager)


def render_overview_tab(system_monitor: SystemMonitor, alert_manager: AlertManager):
    """渲染概览标签页"""
    st.markdown("#### 系统概览")
    st.caption("系统运行状态和关键指标概览。")
    
    # 收集最新指标
    metrics = system_monitor.collect_metrics()
    
    # 显示关键指标
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        cpu_usage = metrics.get("cpu_usage", 0)
        st.metric("CPU使用率", f"{cpu_usage:.1f}%")
    
    with col2:
        memory_usage = metrics.get("memory_usage", 0)
        st.metric("内存使用率", f"{memory_usage:.1f}%")
    
    with col3:
        disk_usage = metrics.get("disk_usage", 0)
        st.metric("磁盘使用率", f"{disk_usage:.1f}%")
    
    with col4:
        health_status = system_monitor.check_health()
        status_emoji = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unhealthy": "❌",
            "unknown": "❓"
        }
        st.metric(
            "健康状态",
            health_status["status"].upper(),
            delta=status_emoji.get(health_status["status"], "❓")
        )
    
    # 业务指标
    st.markdown("#### 业务指标")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        data_latency = metrics.get("data_update_latency", 0)
        st.metric("数据更新延迟", f"{data_latency:.1f} 秒")
    
    with col2:
        order_latency = metrics.get("order_execution_latency", 0)
        st.metric("订单执行延迟", f"{order_latency:.3f} 秒")
    
    with col3:
        api_response = metrics.get("api_response_time", 0)
        st.metric("API响应时间", f"{api_response:.3f} 秒")
    
    # 告警统计
    st.markdown("#### 告警统计")
    alert_stats = alert_manager.get_alert_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总告警数", alert_stats["total_alerts"])
    with col2:
        st.metric("活跃规则", alert_stats["active_rules"])
    with col3:
        st.metric("24小时告警", alert_stats["recent_alerts_24h"])
    with col4:
        critical_count = alert_stats["by_severity"].get("critical", 0)
        st.metric("严重告警", critical_count, delta="🚨" if critical_count > 0 else "✓")
    
    # 监控控制
    st.markdown("#### 监控控制")
    col1, col2 = st.columns(2)
    
    with col1:
        if system_monitor.is_monitoring:
            if st.button("停止监控", type="secondary"):
                system_monitor.stop_monitoring()
                st.rerun()
        else:
            if st.button("启动监控", type="primary"):
                system_monitor.start_monitoring()
                st.rerun()
    
    with col2:
        if st.button("手动收集指标"):
            system_monitor.collect_metrics()
            st.success("指标已收集")


def render_metrics_tab(system_monitor: SystemMonitor):
    """渲染性能指标标签页"""
    st.markdown("#### 性能指标")
    st.caption("查看系统性能指标的历史趋势。")
    
    # 选择指标
    available_metrics = list(system_monitor.metrics_collector.metrics.keys())
    if not available_metrics:
        st.info("暂无指标数据，请先启动监控并收集指标")
        return
    
    selected_metrics = st.multiselect(
        "选择要查看的指标",
        available_metrics,
        default=available_metrics[:3] if len(available_metrics) >= 3 else available_metrics,
    )
    
    if not selected_metrics:
        st.info("请至少选择一个指标")
        return
    
    # 获取指标数据
    window_minutes = st.slider("时间窗口（分钟）", 5, 1440, 60, 5)
    start_time = datetime.now() - timedelta(minutes=window_minutes)
    
    # 绘制图表
    fig = go.Figure()
    
    for metric_name in selected_metrics:
        points = system_monitor.metrics_collector.get_metric(metric_name, start_time)
        if points:
            timestamps = [p.timestamp for p in points]
            values = [p.value for p in points]
            
            fig.add_trace(go.Scatter(
                x=timestamps,
                y=values,
                mode='lines',
                name=metric_name,
                line=dict(width=2),
            ))
    
    fig.update_layout(
        title="性能指标趋势",
        xaxis_title="时间",
        yaxis_title="值",
        hovermode='x unified',
        height=500,
    )
    
    st.plotly_chart(fig, width='stretch')
    
    # 显示统计信息
    st.markdown("#### 指标统计")
    stats_data = []
    for metric_name in selected_metrics:
        stats = system_monitor.metrics_collector.get_metric_statistics(metric_name, window_minutes)
        if stats:
            stats_data.append({
                "指标": metric_name,
                "最新值": f"{stats['latest']:.2f}",
                "平均值": f"{stats['mean']:.2f}",
                "最小值": f"{stats['min']:.2f}",
                "最大值": f"{stats['max']:.2f}",
                "数据点数": stats['count'],
            })
    
    if stats_data:
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, hide_index=True, width='stretch')


def render_health_tab(system_monitor: SystemMonitor):
    """渲染健康检查标签页"""
    st.markdown("#### 健康检查")
    st.caption("查看系统各组件的健康状态。")
    
    # 执行健康检查
    if st.button("执行健康检查", type="primary"):
        health_status = system_monitor.check_health()
        st.session_state.last_health_check = health_status
    
    if "last_health_check" not in st.session_state:
        st.info("点击上方按钮执行健康检查")
        return
    
    health_status = st.session_state.last_health_check
    
    # 显示整体状态
    status_emoji = {
        "healthy": "✅",
        "degraded": "⚠️",
        "unhealthy": "❌",
        "unknown": "❓"
    }
    status_color = {
        "healthy": "green",
        "degraded": "orange",
        "unhealthy": "red",
        "unknown": "gray"
    }
    
    st.markdown(f"#### 整体状态: {status_emoji.get(health_status['status'], '❓')} {health_status['status'].upper()}")
    
    # 显示各项检查结果
    checks = health_status.get("checks", {})
    
    for check_name, check_result in checks.items():
        with st.expander(f"{check_name.upper()}: {check_result['status'].upper()}", expanded=False):
            st.write(f"**状态**: {check_result['status']}")
            st.write(f"**消息**: {check_result['message']}")
            
            if check_result.get("details"):
                st.write("**详情**:")
                st.json(check_result["details"])


def render_alerts_tab(alert_manager: AlertManager):
    """渲染告警管理标签页"""
    st.markdown("#### 告警历史")
    st.caption("查看历史告警记录。")
    
    # 告警规则列表
    st.markdown("##### 告警规则")
    if alert_manager.alert_rules:
        rules_data = []
        for rule_id, rule in alert_manager.alert_rules.items():
            rules_data.append({
                "规则ID": rule_id,
                "名称": rule.name,
                "指标": rule.metric_name,
                "阈值": f"{rule.comparison.value} {rule.threshold}",
                "严重程度": rule.severity.value,
                "启用": "是" if rule.enabled else "否",
                "冷却期": f"{rule.cooldown_minutes} 分钟",
            })
        
        rules_df = pd.DataFrame(rules_data)
        st.dataframe(rules_df, hide_index=True, width='stretch')
    else:
        st.info("暂无告警规则，请在'告警配置'标签页添加规则")
    
    # 告警历史
    st.markdown("##### 告警历史")
    
    col1, col2 = st.columns(2)
    with col1:
        limit = st.number_input("显示数量", min_value=10, max_value=1000, value=100, step=10)
    with col2:
        severity_filter = st.selectbox(
            "过滤严重程度",
            ["全部", "info", "warning", "error", "critical"],
        )
    
    severity = None if severity_filter == "全部" else AlertSeverity[severity_filter.upper()]
    history = alert_manager.get_alert_history(limit=limit, severity=severity)
    
    if history:
        history_df = pd.DataFrame(history)
        st.dataframe(history_df, hide_index=True, width='stretch')
    else:
        st.info("暂无告警记录")


def render_alert_config_tab(alert_manager: AlertManager):
    """渲染告警配置标签页"""
    st.markdown("#### 告警规则配置")
    st.caption("添加和管理告警规则。")
    
    # 添加告警规则
    with st.expander("添加告警规则", expanded=True):
        rule_name = st.text_input("规则名称", key="new_rule_name")
        
        col1, col2 = st.columns(2)
        with col1:
            metric_name = st.selectbox(
                "指标名称",
                ["cpu_usage", "memory_usage", "disk_usage", "data_update_latency", "order_execution_latency"],
                key="new_metric_name"
            )
        with col2:
            comparison = st.selectbox(
                "比较操作符",
                [">", ">=", "<", "<=", "==", "!="],
                key="new_comparison"
            )
        
        threshold = st.number_input("阈值", value=80.0, step=0.1, key="new_threshold")
        
        col1, col2 = st.columns(2)
        with col1:
            severity = st.selectbox(
                "严重程度",
                ["info", "warning", "error", "critical"],
                key="new_severity"
            )
        with col2:
            cooldown = st.number_input("冷却期（分钟）", min_value=0, value=5, step=1, key="new_cooldown")
        
        channels = st.multiselect(
            "告警渠道",
            ["dashboard", "email", "webhook", "telegram", "dingtalk"],
            default=["dashboard"],
            key="new_channels"
        )
        
        if st.button("添加规则", type="primary"):
            comparison_op = ComparisonOperator(comparison)
            severity_enum = AlertSeverity[severity.upper()]
            
            rule_id = alert_manager.add_alert_rule(
                name=rule_name,
                metric_name=metric_name,
                threshold=threshold,
                comparison=comparison_op,
                severity=severity_enum,
                cooldown_minutes=cooldown,
                channels=channels,
            )
            st.success(f"告警规则已添加: {rule_id}")
            st.rerun()
    
    # 告警渠道配置
    st.markdown("#### 告警渠道配置")
    
    with st.expander("邮件配置"):
        email_enabled = st.checkbox("启用邮件告警", key="email_enabled")
        if email_enabled:
            col1, col2 = st.columns(2)
            with col1:
                smtp_server = st.text_input("SMTP服务器", key="email_smtp")
                smtp_port = st.number_input("SMTP端口", value=587, key="email_port")
            with col2:
                username = st.text_input("用户名", key="email_user")
                password = st.text_input("密码", type="password", key="email_pass")
            
            if st.button("保存邮件配置"):
                channel = EmailChannel(
                    smtp_server=smtp_server,
                    smtp_port=smtp_port,
                    username=username,
                    password=password,
                )
                alert_manager.add_channel("email", channel)
                st.success("邮件渠道已配置")
    
    with st.expander("Webhook配置"):
        webhook_url = st.text_input("Webhook URL", key="webhook_url")
        if st.button("保存Webhook配置"):
            channel = WebhookChannel(webhook_url=webhook_url)
            alert_manager.add_channel("webhook", channel)
            st.success("Webhook渠道已配置")
    
    with st.expander("Telegram配置"):
        bot_token = st.text_input("Bot Token", type="password", key="telegram_token")
        chat_id = st.text_input("Chat ID", key="telegram_chat_id")
        if st.button("保存Telegram配置"):
            channel = TelegramChannel(bot_token=bot_token, chat_id=chat_id)
            alert_manager.add_channel("telegram", channel)
            st.success("Telegram渠道已配置")
    
    with st.expander("钉钉配置"):
        dingtalk_url = st.text_input("钉钉Webhook URL", key="dingtalk_url")
        if st.button("保存钉钉配置"):
            channel = DingTalkChannel(webhook_url=dingtalk_url)
            alert_manager.add_channel("dingtalk", channel)
            st.success("钉钉渠道已配置")


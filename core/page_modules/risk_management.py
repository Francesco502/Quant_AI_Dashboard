"""
风险管理页面模块
"""
import streamlit as st
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime
from typing import Dict, Any

from core.page_utils import get_ticker_names, get_selected_tickers, get_data
from core.account import ensure_account_dict, compute_equity
from core.risk_config import (
    load_risk_config,
    save_risk_config,
    config_to_risk_limits,
    config_to_sector_info,
    config_to_position_limits,
    risk_limits_to_config,
    sector_info_to_config,
    position_limits_to_config,
)
from core.risk_types import RiskLimits, PositionLimit, AlertSeverity
from core.risk_monitor import RiskMonitor
from core.position_manager import PositionManager, SectorInfo
from core.stop_loss_manager import StopLossManager
from core.risk_alerting import RiskAlerting
from core.apple_ui import get_apple_chart_layout, APPLE_COLORS


def render_risk_management_page():
    """渲染风险管理页面"""
    ticker_names = get_ticker_names()
    tickers = get_selected_tickers()
    data = get_data()
    
    st.markdown("### 风险管理")
    st.caption("配置和管理风险限制、仓位限制、止损止盈规则，监控风险指标。")
    
    # 加载配置
    if "risk_config" not in st.session_state:
        st.session_state.risk_config = load_risk_config()
    
    config = st.session_state.risk_config
    
    # 创建标签页
    tab_config, tab_monitoring, tab_positions, tab_stop_loss, tab_alerts = st.tabs([
        "风险配置",
        "风险监控",
        "仓位管理",
        "止损止盈",
        "告警设置"
    ])
    
    # ========== 标签页：风险配置 ==========
    with tab_config:
        render_risk_config_tab(config)
    
    # ========== 标签页：风险监控 ==========
    with tab_monitoring:
        render_risk_monitoring_tab(tickers, data)
    
    # ========== 标签页：仓位管理 ==========
    with tab_positions:
        render_position_management_tab(tickers, data)
    
    # ========== 标签页：止损止盈 ==========
    with tab_stop_loss:
        render_stop_loss_tab(tickers, data)
    
    # ========== 标签页：告警设置 ==========
    with tab_alerts:
        render_alert_config_tab(config)


def render_risk_config_tab(config: Dict[str, Any]):
    """渲染风险配置标签页"""
    st.markdown("#### 风险限制配置")
    st.caption("设置各种风险限制参数，用于风险检查和监控。")
    
    risk_limits_config = config.get("risk_limits", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        max_position_size = st.slider(
            "单仓位最大比例",
            min_value=0.01,
            max_value=0.5,
            value=risk_limits_config.get("max_position_size", 0.1),
            step=0.01,
            help="单个仓位占组合总资产的最大比例"
        )
        
        max_single_stock = st.slider(
            "单股票最大比例",
            min_value=0.01,
            max_value=0.2,
            value=risk_limits_config.get("max_single_stock", 0.05),
            step=0.01,
            help="单个股票占组合总资产的最大比例"
        )
        
        max_total_exposure = st.slider(
            "总敞口最大比例",
            min_value=0.5,
            max_value=1.0,
            value=risk_limits_config.get("max_total_exposure", 0.95),
            step=0.01,
            help="所有持仓占组合总资产的最大比例"
        )
    
    with col2:
        max_daily_loss = st.slider(
            "单日最大亏损比例",
            min_value=0.01,
            max_value=0.2,
            value=risk_limits_config.get("max_daily_loss", 0.05),
            step=0.01,
            help="单日最大允许亏损占初始资金的比例"
        )
        
        max_total_loss = st.slider(
            "总亏损最大比例",
            min_value=0.05,
            max_value=0.5,
            value=risk_limits_config.get("max_total_loss", 0.2),
            step=0.01,
            help="总亏损占初始资金的最大比例，超过将触发紧急停止"
        )
        
        stop_loss_threshold = st.slider(
            "止损阈值",
            min_value=0.01,
            max_value=0.2,
            value=risk_limits_config.get("stop_loss_threshold", 0.08),
            step=0.01,
            help="默认止损比例"
        )
    
    # 保存配置
    if st.button("保存风险配置", type="primary"):
        config["risk_limits"] = {
            "max_position_size": max_position_size,
            "max_single_stock": max_single_stock,
            "max_total_exposure": max_total_exposure,
            "max_daily_loss": max_daily_loss,
            "max_total_loss": max_total_loss,
            "stop_loss_threshold": stop_loss_threshold,
            "max_sector_exposure": risk_limits_config.get("max_sector_exposure", 0.3),
            "max_correlation": risk_limits_config.get("max_correlation", 0.8),
            "min_liquidity_ratio": risk_limits_config.get("min_liquidity_ratio", 0.1),
        }
        
        if save_risk_config(config):
            st.session_state.risk_config = config
            st.success("风险配置已保存")
        else:
            st.error("保存失败，请检查文件权限")


def render_risk_monitoring_tab(tickers: list, data: pd.DataFrame):
    """渲染风险监控标签页"""
    st.markdown("#### 实时风险监控")
    st.caption("查看当前组合的风险指标和风险事件。")
    
    if data.empty or len(tickers) == 0:
        st.info("请先选择资产并加载数据")
        return
    
    # 获取账户
    account = st.session_state.get("paper_account")
    if not account:
        st.info("请先在'模拟账户'页面初始化账户")
        return
    
    # 计算当前价格
    current_prices = {}
    for t in tickers:
        if t in data.columns:
            current_prices[t] = float(data[t].iloc[-1])
    
    # 创建风险监控器
    config = st.session_state.risk_config
    risk_limits = config_to_risk_limits(config)
    sector_info = config_to_sector_info(config)
    position_manager = PositionManager(sector_info=sector_info)
    risk_monitor = RiskMonitor(risk_limits=risk_limits, position_manager=position_manager)
    
    # 计算当前权益
    equity = compute_equity(account, current_prices)
    initial_capital = account.get("initial_capital", equity)
    
    # 计算盈亏金额和比例
    pnl = equity - initial_capital
    pnl_pct = pnl / initial_capital if initial_capital > 0 else 0
    
    # 计算亏损比例（只有亏损时才为正，盈利时为0）
    total_loss = max(0, (initial_capital - equity) / initial_capital) if initial_capital > 0 else 0
    
    # 显示风险指标
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总权益", f"{equity:,.0f} 元")
    
    with col2:
        # 盈亏显示正确的盈亏比例（正数表示盈利，负数表示亏损）
        pnl_sign = "+" if pnl_pct > 0 else ""
        st.metric("盈亏", f"{pnl:,.0f} 元", delta=f"{pnl_sign}{pnl_pct:.2%}")
    
    with col3:
        loss_status = "正常" if total_loss < risk_limits.max_total_loss else "⚠️ 超限"
        st.metric("总亏损比例", f"{total_loss:.2%}", delta=loss_status)
    
    with col4:
        emergency_stop = total_loss >= risk_limits.max_total_loss
        st.metric("紧急停止", "是" if emergency_stop else "否", delta="⚠️" if emergency_stop else "✓")
    
    # 风险汇总
    if "risk_monitor" not in st.session_state:
        st.session_state.risk_monitor = risk_monitor
    
    summary = risk_monitor.get_risk_summary()
    
    st.markdown("#### 风险事件历史")
    if summary["recent_events"]:
        events_df = pd.DataFrame(summary["recent_events"])
        st.dataframe(events_df, hide_index=True, width='stretch')
    else:
        st.info("暂无风险事件")


def render_position_management_tab(tickers: list, data: pd.DataFrame):
    """渲染仓位管理标签页"""
    st.markdown("#### 仓位限制管理")
    st.caption("设置单标的、行业、市场的仓位限制。")
    
    if data.empty or len(tickers) == 0:
        st.info("请先选择资产并加载数据")
        return
    
    config = st.session_state.risk_config
    sector_info = config_to_sector_info(config)
    position_manager = PositionManager(sector_info=sector_info)
    
    # 加载仓位限制
    position_limits = config_to_position_limits(config)
    for symbol, limit in position_limits.items():
        position_manager.add_position_limit(limit)
    
    # 设置行业限制
    sector_limits = config.get("sector_limits", {})
    for sector, max_weight in sector_limits.items():
        position_manager.set_sector_limit(sector, max_weight)
    
    # 设置市场限制
    market_limits = config.get("market_limits", {})
    for market, max_weight in market_limits.items():
        position_manager.set_market_limit(market, max_weight)
    
    # 显示当前仓位汇总
    account = st.session_state.get("paper_account")
    if account:
        current_prices = {}
        for t in tickers:
            if t in data.columns:
                current_prices[t] = float(data[t].iloc[-1])
        
        summary = position_manager.get_position_summary(account, current_prices)
        
        st.markdown("##### 当前仓位汇总")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("总权益", f"{summary['total_equity']:,.0f} 元")
            st.metric("总仓位权重", f"{summary['total_position_weight']:.2%}")
        with col2:
            st.metric("持仓市值", f"{summary['total_position_value']:,.0f} 元")
        
        if summary["symbol_weights"]:
            st.markdown("##### 标的权重分布")
            weights_df = pd.DataFrame([
                {"标的": symbol, "权重": f"{weight:.2%}"}
                for symbol, weight in summary["symbol_weights"].items()
            ])
            st.dataframe(weights_df, hide_index=True, width='stretch')
    
    # 配置仓位限制
    st.markdown("##### 配置仓位限制")
    selected_ticker = st.selectbox("选择标的", tickers)
    
    col1, col2 = st.columns(2)
    with col1:
        max_position = st.number_input("最大持仓数量", min_value=0, value=10000, step=100)
    with col2:
        max_weight = st.slider("最大权重", min_value=0.01, max_value=0.5, value=0.05, step=0.01)
    
    if st.button("保存仓位限制"):
        limit = PositionLimit(
            symbol=selected_ticker,
            max_position=max_position,
            max_weight=max_weight
        )
        position_limits[selected_ticker] = limit
        config["position_limits"] = position_limits_to_config(position_limits)
        if save_risk_config(config):
            st.success("仓位限制已保存")
            st.session_state.risk_config = config


def render_stop_loss_tab(tickers: list, data: pd.DataFrame):
    """渲染止损止盈标签页"""
    st.markdown("#### 止损止盈管理")
    st.caption("为持仓设置止损和止盈规则。")
    
    if data.empty or len(tickers) == 0:
        st.info("请先选择资产并加载数据")
        return
    
    # 初始化止损止盈管理器
    if "stop_loss_manager" not in st.session_state:
        st.session_state.stop_loss_manager = StopLossManager()
    
    stop_loss_manager = st.session_state.stop_loss_manager
    
    # 显示当前规则
    active_rules = stop_loss_manager.get_active_rules()
    
    if active_rules["stop_loss"] or active_rules["take_profit"]:
        st.markdown("##### 当前活跃规则")
        
        if active_rules["stop_loss"]:
            st.markdown("**止损规则：**")
            stop_loss_df = pd.DataFrame([
                {
                    "标的": symbol,
                    "类型": rule["stop_type"],
                    "止损价": f"{rule['stop_price']:.2f}" if rule["stop_price"] else "N/A",
                    "入场价": f"{rule['entry_price']:.2f}",
                    "启用": "是" if rule["enabled"] else "否"
                }
                for symbol, rule in active_rules["stop_loss"].items()
            ])
            st.dataframe(stop_loss_df, hide_index=True, width='stretch')
        
        if active_rules["take_profit"]:
            st.markdown("**止盈规则：**")
            take_profit_df = pd.DataFrame([
                {
                    "标的": symbol,
                    "类型": rule["take_profit_type"],
                    "止盈价": f"{rule['take_profit_price']:.2f}" if rule["take_profit_price"] else "N/A",
                    "入场价": f"{rule['entry_price']:.2f}",
                    "启用": "是" if rule["enabled"] else "否"
                }
                for symbol, rule in active_rules["take_profit"].items()
            ])
            st.dataframe(take_profit_df, hide_index=True, width='stretch')
    
    # 设置新规则
    st.markdown("##### 设置止损止盈规则")
    
    selected_ticker = st.selectbox("选择标的", tickers, key="stop_loss_ticker")
    
    if selected_ticker in data.columns:
        current_price = float(data[selected_ticker].iloc[-1])
        st.info(f"当前价格: {current_price:.2f}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**止损设置**")
            stop_type = st.selectbox("止损类型", ["percentage", "fixed", "trailing"], key="stop_type")
            
            if stop_type == "percentage":
                stop_percentage = st.slider("止损百分比", 0.01, 0.2, 0.05, 0.01)
                stop_loss_manager.set_stop_loss(
                    symbol=selected_ticker,
                    entry_price=current_price,
                    stop_type="percentage",
                    stop_percentage=stop_percentage
                )
            elif stop_type == "fixed":
                stop_price = st.number_input("止损价格", value=current_price * 0.95, step=0.01)
                stop_loss_manager.set_stop_loss(
                    symbol=selected_ticker,
                    entry_price=current_price,
                    stop_type="fixed",
                    stop_price=stop_price
                )
        
        with col2:
            st.markdown("**止盈设置**")
            take_profit_type = st.selectbox("止盈类型", ["percentage", "fixed"], key="take_profit_type")
            
            if take_profit_type == "percentage":
                take_profit_percentage = st.slider("止盈百分比", 0.01, 0.5, 0.1, 0.01)
                stop_loss_manager.set_take_profit(
                    symbol=selected_ticker,
                    entry_price=current_price,
                    take_profit_type="percentage",
                    take_profit_percentage=take_profit_percentage
                )
            elif take_profit_type == "fixed":
                take_profit_price = st.number_input("止盈价格", value=current_price * 1.1, step=0.01)
                stop_loss_manager.set_take_profit(
                    symbol=selected_ticker,
                    entry_price=current_price,
                    take_profit_type="fixed",
                    take_profit_price=take_profit_price
                )
        
        if st.button("保存规则"):
            st.success("止损止盈规则已设置")


def render_alert_config_tab(config: Dict[str, Any]):
    """渲染告警设置标签页"""
    st.markdown("#### 告警配置")
    st.caption("配置风险告警的通知渠道。")
    
    alert_config = config.get("alert_config", {})
    
    # 邮件配置
    st.markdown("##### 邮件告警")
    email_config = alert_config.get("email", {})
    
    email_enabled = st.checkbox("启用邮件告警", value=email_config.get("enabled", False))
    
    if email_enabled:
        col1, col2 = st.columns(2)
        with col1:
            smtp_server = st.text_input("SMTP服务器", value=email_config.get("smtp_server", ""))
            smtp_port = st.number_input("SMTP端口", value=email_config.get("smtp_port", 587), step=1)
        with col2:
            username = st.text_input("用户名", value=email_config.get("username", ""))
            password = st.text_input("密码", value=email_config.get("password", ""), type="password")
        
        alert_config["email"] = {
            "enabled": email_enabled,
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "username": username,
            "password": password,
        }
    
    # Webhook配置
    st.markdown("##### Webhook告警")
    webhook_config = alert_config.get("webhook", {})
    
    webhook_enabled = st.checkbox("启用Webhook告警", value=webhook_config.get("enabled", False))
    
    if webhook_enabled:
        webhook_url = st.text_input("Webhook URL", value=webhook_config.get("url", ""))
        alert_config["webhook"] = {
            "enabled": webhook_enabled,
            "url": webhook_url,
        }
    
    # 保存配置
    if st.button("保存告警配置", type="primary"):
        config["alert_config"] = alert_config
        if save_risk_config(config):
            st.session_state.risk_config = config
            st.success("告警配置已保存")
        else:
            st.error("保存失败，请检查文件权限")


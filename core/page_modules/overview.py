"""
概览页面模块
显示资产历史走势和快速概览指标
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from core.apple_ui import (
    get_apple_chart_layout,
    get_apple_line_colors,
    render_section_divider,
    render_section_header,
)
from core.portfolio import optimize_portfolio_markowitz
from core.page_utils import get_ticker_names, get_selected_tickers, get_data

def render_overview_page():
    """渲染概览页面"""
    ticker_names = get_ticker_names()
    tickers = get_selected_tickers()
    data = get_data()

    # 如果数据为空，说明数据还未加载，这通常发生在页面首次加载时
    # 此时应该显示提示，但不需要阻止页面渲染（因为数据会在主函数中加载）
    if data.empty or len(tickers) == 0:
        st.info("💡 提示：数据正在加载中，如果长时间未显示，请检查资产选择和数据源配置。")
        return
    
    st.markdown("### 资产历史走势")
    st.caption(
        "显示选定资产的历史价格走势图，用于观察价格变化趋势。"
        "左侧「历史回看天数」会决定这里展示的时间窗口，也会影响后续的收益率、波动率和预测结果。"
    )
    
    # 数据源显示
    data_sources_display = st.session_state.get("data_sources", [])
    if data_sources_display:
        data_source_text = "、".join(data_sources_display)
        st.caption(f"**数据源：** {data_source_text}")
    else:
        st.caption("**数据源：** 未选择")
    
    # 当前资产显示
    selected_tickers_display = st.session_state.get("selected_tickers", tickers)
    if selected_tickers_display:
        asset_names = [ticker_names.get(t, t) for t in selected_tickers_display if t in ticker_names]
        if asset_names:
            st.caption(f"**当前资产：** {', '.join(asset_names)}")
    
    if st.session_state.get("last_data_fetch_time"):
        st.caption(f"最近获取数据时间：{st.session_state.last_data_fetch_time}")
    
    # 资产走势图
    has_chinese_asset = any(".SZ" in t or ".SS" in t for t in tickers) or any(t.isdigit() and len(t) == 6 for t in tickers)
    has_us_asset = any(t in ["BTC-USD", "ETH-USD", "AAPL", "TSLA", "NVDA"] for t in tickers)
    yaxis_title = "价格 (USD / CNY)" if (has_chinese_asset and has_us_asset) else ("价格 (CNY)" if has_chinese_asset else "价格 (USD)")
    
    if not data.empty:
        fig_hist = go.Figure()
        colors = get_apple_line_colors()
        for i, ticker in enumerate(tickers):
            if ticker in data.columns:
                display_name = ticker_names.get(ticker, ticker)
                fig_hist.add_trace(go.Scatter(
                    x=data.index, y=data[ticker],
                    mode='lines', name=display_name,
                    line=dict(width=2.5, color=colors[i % len(colors)]),
                    hovertemplate='%{y:,.2f}<extra></extra>',
                ))
        
        fig_hist.update_layout(**get_apple_chart_layout(
            title="资产历史走势",
            height=380,
            xaxis_title="日期",
            yaxis_title=yaxis_title,
        ))
        st.plotly_chart(fig_hist, width='stretch', key="chart_hist")
    
    # 快速概览指标卡片
    render_section_divider()
    render_section_header("快速概览", "关键投资组合指标一览")
    
    overview_col1, overview_col2, overview_col3, overview_col4 = st.columns([1, 1, 1, 1], gap="medium")
    
    # 计算概览指标
    if not data.empty and len(tickers) > 0:
        log_ret = np.log(data / data.shift(1)).dropna()
        
        # 近期收益
        recent_returns = data.pct_change().iloc[-5:].mean()
        avg_5d_return = recent_returns.mean() if len(recent_returns) > 0 else 0
        
        # 波动率
        volatility = log_ret.std() * np.sqrt(252)
        avg_vol = volatility.mean() if len(volatility) > 0 else 0
        
        # 最大回撤
        max_dd = 0
        for ticker in tickers:
            if ticker in data.columns:
                rolling_max = data[ticker].expanding().max()
                drawdown = (data[ticker] - rolling_max) / rolling_max
                ticker_max_dd = drawdown.min()
                if ticker_max_dd < max_dd:
                    max_dd = ticker_max_dd
        
        with overview_col1:
            st.metric("资产数量", f"{len(tickers)}", help="当前选中的资产数量")
        with overview_col2:
            display_5d = f"{avg_5d_return:.2%}"
            if avg_5d_return > 0:
                display_5d = f"+{display_5d}"
            st.metric("近5日平均收益", display_5d, help="所有资产近5个交易日的平均收益率")
        with overview_col3:
            st.metric("平均年化波动率", f"{avg_vol:.2%}", help="所有资产的平均年化波动率，衡量整体风险水平")
        with overview_col4:
            st.metric("最大回撤", f"{max_dd:.2%}", help="所有资产中最大的历史回撤幅度")
    
    # 智能仓位建议
    render_section_divider()
    render_section_header("智能仓位建议", "Markowitz 均值-方差优化算法，平衡收益与风险")
    
    if st.button("运行组合优化算法", key="opt_btn"):
        st.session_state.portfolio_optimized = True
        with st.spinner("正在优化资产组合..."):
            try:
                log_ret = np.log(data / data.shift(1)).dropna()
                opt_weights, exp_return, exp_vol, sharpe = optimize_portfolio_markowitz(log_ret, risk_free_rate=0.02)
                st.session_state.opt_weights = opt_weights
                st.session_state.opt_exp_return = exp_return
                st.session_state.opt_exp_vol = exp_vol
                st.session_state.opt_sharpe = sharpe
            except Exception as e:
                st.error(f"优化时出现问题：{e}")
                st.session_state.portfolio_optimized = False
    
    # 显示优化结果
    if st.session_state.get("portfolio_optimized", False) and "opt_weights" in st.session_state:
        opt_weights = st.session_state.opt_weights
        exp_return = st.session_state.opt_exp_return
        exp_vol = st.session_state.opt_exp_vol
        sharpe = st.session_state.opt_sharpe
        
        opt_col1, opt_col2 = st.columns([1, 1])
        
        with opt_col1:
            st.markdown("#### 建议仓位分配")
            asset_names = [ticker_names.get(t, t) for t in tickers]
            weight_df = pd.DataFrame({
                "资产": asset_names,
                "权重": [f"{w:.2%}" for w in opt_weights]
            })
            st.dataframe(weight_df, width="stretch", hide_index=True)
        
        with opt_col2:
            st.markdown("#### 预期表现")
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                st.metric("年化收益", f"{exp_return:.2%}")
            with metric_col2:
                st.metric("年化波动", f"{exp_vol:.2%}")
            with metric_col3:
                st.metric("夏普比率", f"{sharpe:.2f}")
            st.caption("* 风险自由利率假设为 2%")


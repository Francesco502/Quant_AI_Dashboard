"""
风险分析页面模块
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from core.page_utils import get_ticker_names, get_selected_tickers, get_data
from core.cache_utils import calculate_returns_cached, calculate_correlation_matrix_cached
from core.risk_analysis import (
    calculate_var,
    calculate_cvar,
    calculate_max_drawdown,
    calculate_portfolio_risk_metrics,
    calculate_risk_contribution,
    find_highly_correlated_pairs,
)
from core.portfolio import optimize_portfolio_markowitz
from core.apple_ui import get_apple_chart_layout, APPLE_COLORS


def render_risk_analysis_page():
    """渲染风险分析页面"""
    ticker_names = get_ticker_names()
    tickers = get_selected_tickers()
    data = get_data()
    
    if data.empty or len(tickers) == 0:
        st.info("💡 提示：数据正在加载中，如果长时间未显示，请检查资产选择和数据源配置。")
        return
    
    st.markdown("### 风险分析")
    st.caption("从'组合'和'单个资产'两个层面量化风险水平，帮助识别潜在损失和风险来源。")

    # ===== 组合层面：相关性 + 组合风险 =====
    st.markdown("#### 组合风险与相关性（多资产）")
    st.caption("先选择要纳入组合分析的资产，然后查看它们之间的相关性和整体组合的风险指标。")

    risk_assets = st.multiselect(
        "选择参与组合风险分析的资产",
        tickers,
        default=tickers,
        help="至少选择 2 个资产，用于计算相关性矩阵和组合风险指标。",
        key="risk_assets",
    )

    if len(risk_assets) < 2:
        st.info("请选择至少 2 个资产以进行组合风险与相关性分析。")
    else:
        log_ret = calculate_returns_cached(data)
        log_ret_subset = log_ret[risk_assets]

        # 相关性矩阵热力图（强制使用类别型坐标，避免缩放错位）
        corr_matrix = calculate_correlation_matrix_cached(log_ret_subset)
        st.markdown("##### 资产相关性矩阵")
        st.caption("颜色和数字共同表示资产之间的相关系数：红色偏正相关，蓝色偏负相关，越接近 1（-1）相关性越强。")

        corr_cols = list(corr_matrix.columns)
        corr_idx = list(corr_matrix.index)
        z = corr_matrix.values
        text = [[f"{val:.2f}" for val in row] for row in z]

        fig_corr = go.Figure(
            data=go.Heatmap(
                z=z,
                x=list(range(len(corr_cols))),
                y=list(range(len(corr_idx))),
                colorscale="RdBu",
                zmin=-1,
                zmax=1,
                zmid=0,
                text=text,
                texttemplate="%{text}",
                colorbar=dict(title="相关系数"),
            )
        )
        fig_corr.update_xaxes(
            tickmode="array",
            tickvals=list(range(len(corr_cols))),
            ticktext=corr_cols,
        )
        fig_corr.update_yaxes(
            tickmode="array",
            tickvals=list(range(len(corr_idx))),
            ticktext=corr_idx,
            autorange="reversed",
        )
        fig_corr.update_layout(
            height=400,
            margin=dict(l=60, r=30, t=50, b=50),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(
                family="SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif",
                size=12,
            ),
        )
        st.plotly_chart(fig_corr, width='stretch', key="chart_corr")

        # 高度相关资产对
        high_corr = find_highly_correlated_pairs(corr_matrix, threshold=0.7)
        if not high_corr.empty:
            st.markdown("##### 高度相关资产对 (|相关系数| ≥ 0.7)")
            st.caption("高度正/负相关的资产组合在分散风险或做对冲时需要特别注意。")
            st.dataframe(high_corr, width="stretch", hide_index=True)

        # 组合整体风险指标
        st.markdown("##### 组合整体风险指标（基于最优权重）")
        try:
            opt_weights, _, _, _ = optimize_portfolio_markowitz(
                log_ret_subset, risk_free_rate=0.02
            )
            risk_metrics = calculate_portfolio_risk_metrics(
                log_ret_subset, opt_weights, risk_free_rate=0.02
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("VaR (95%)", f"{risk_metrics['var_95']:.2%}")
                st.caption("在 95% 的情况下，单日损失不会超过该比例（越小越安全）。")
                st.metric("CVaR (95%)", f"{risk_metrics['cvar_95']:.2%}")
                st.caption("当损失超过 VaR 时，平均损失水平。")
            with col2:
                st.metric("最大回撤", f"{risk_metrics['max_drawdown']:.2%}")
                st.caption("历史上从高点到低点的最大跌幅，用于衡量极端下行风险。")
                st.metric("年化波动率", f"{risk_metrics['annual_volatility']:.2%}")
                st.caption("组合收益的年化标准差，反映整体波动大小。")
            with col3:
                st.metric("夏普比率", f"{risk_metrics['sharpe_ratio']:.2f}")
                st.caption("每承担一单位波动风险获得的超额收益，>1 为良好，>2 为优秀。")
                st.metric("索提诺比率", f"{risk_metrics['sortino_ratio']:.2f}")
                st.caption("只用下行波动测风险的'改进版'夏普比率。")

            # 风险贡献条形图
            st.markdown("##### 组合风险贡献度")
            st.caption("显示每个资产对组合总体波动的贡献比例，便于识别'风险来源重仓'。")
            risk_contrib = calculate_risk_contribution(opt_weights, log_ret_subset)
            fig_risk = go.Figure(
                data=[go.Bar(
                    x=risk_contrib.index,
                    y=risk_contrib.values,
                    marker_color=APPLE_COLORS['blue'],
                    marker_line_width=0,
                    hovertemplate='%{y:.2f}%<extra></extra>',
                )]
            )
            # 组合风险贡献度图：显式设置标题，并适当缩小高度，保证完整显示边框
            fig_risk.update_layout(**get_apple_chart_layout(
                title="组合风险贡献度",
                height=380,
                show_legend=False,
                xaxis_title="资产",
                yaxis_title="风险贡献度 (%)",
            ))
            st.plotly_chart(fig_risk, width='stretch', key="chart_risk")
        except Exception as e:
            st.warning(f"组合风险分析失败: {e}")

    # ===== 单资产层面：风险指标 + 回撤曲线 =====
    st.markdown("---")
    st.markdown("#### 单个资产风险指标")
    st.caption("选择一只资产，查看其历史回撤、波动率和尾部风险指标（VaR / CVaR）。")

    selected_ticker = st.selectbox("选择资产", tickers, key="risk_ticker")
    log_ret = calculate_returns_cached(data)
    asset_returns = log_ret[selected_ticker]
    price_series = data[selected_ticker]
    
    var_95 = calculate_var(asset_returns, 0.05)
    cvar_95 = calculate_cvar(asset_returns, 0.05)
    max_dd, dd_series = calculate_max_drawdown(price_series)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("VaR (95%)", f"{var_95:.2%}")
        st.caption("95%置信度下的最大可能损失")
    with col2:
        st.metric("CVaR (95%)", f"{cvar_95:.2%}")
        st.caption("超过VaR的损失的期望值")
    with col3:
        st.metric("最大回撤", f"{max_dd:.2%}")
        st.caption("从历史最高点到最低点的最大跌幅")
    with col4:
        annual_vol = asset_returns.std() * np.sqrt(252)
        st.metric("年化波动率", f"{annual_vol:.2%}")
        st.caption("衡量价格波动程度")
    
    # 回撤曲线
    fig_dd = go.Figure()
    fig_dd.add_trace(
        go.Scatter(
            x=dd_series.index,
            y=dd_series.values * 100,
            fill="tozeroy",
            name="回撤",
            line=dict(color="red"),
        )
    )
    fig_dd.update_layout(
        height=400,
        margin=dict(l=60, r=30, t=50, b=50),
        title=dict(text="回撤曲线", font=dict(size=16, color='#1D1D1F')),
        xaxis_title="日期",
        yaxis_title="回撤 (%)",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif", size=12),
        xaxis=dict(showgrid=True, gridcolor='#E5E5E7', gridwidth=1),
        yaxis=dict(showgrid=True, gridcolor='#E5E5E7', gridwidth=1)
    )
    st.plotly_chart(fig_dd, width='stretch', key="chart_drawdown")


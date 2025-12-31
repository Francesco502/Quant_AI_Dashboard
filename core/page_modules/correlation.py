"""
相关性分析页面模块
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from core.page_utils import get_ticker_names, get_selected_tickers, get_data
from core.cache_utils import calculate_returns_cached, calculate_correlation_matrix_cached
from core.correlation import calculate_rolling_correlation


def render_correlation_page():
    """渲染相关性分析页面"""
    ticker_names = get_ticker_names()
    tickers = get_selected_tickers()
    data = get_data()
    
    if data.empty or len(tickers) == 0:
        st.info("💡 提示：数据正在加载中，如果长时间未显示，请检查资产选择和数据源配置。")
        return
    
    st.markdown("### 相关性分析")
    st.caption("这里侧重'横截面'的资产关系：包括整体相关性结构、指定资产对的滚动相关性，以及相关性分布统计。")

    if len(tickers) < 2:
        st.warning("需要至少 2 个资产才能进行相关性分析。")
    else:
        # 选择参与相关性分析的资产子集
        st.markdown("#### 相关性矩阵（多资产）")
        corr_assets = st.multiselect(
            "选择要分析相关性的资产",
            tickers,
            default=tickers,
            help="可选择全部资产，或只选择某一组资产观察它们之间的相关性结构。",
            key="corr_assets",
        )

        if len(corr_assets) < 2:
            st.info("请选择至少 2 个资产以绘制相关性矩阵。")
        else:
            log_ret = calculate_returns_cached(data)
            corr_matrix = calculate_correlation_matrix_cached(log_ret[corr_assets])

            corr_cols = list(corr_matrix.columns)
            corr_idx = list(corr_matrix.index)
            z = corr_matrix.values
            text = [[f"{val:.2f}" for val in row] for row in z]

            fig_corr2 = go.Figure(
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
            fig_corr2.update_xaxes(
                tickmode="array",
                tickvals=list(range(len(corr_cols))),
                ticktext=corr_cols,
            )
            fig_corr2.update_yaxes(
                tickmode="array",
                tickvals=list(range(len(corr_idx))),
                ticktext=corr_idx,
                autorange="reversed",
            )
            fig_corr2.update_layout(
                height=400,
                margin=dict(l=60, r=30, t=50, b=50),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(
                    family="SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif",
                    size=12,
                ),
            )
            st.plotly_chart(fig_corr2, width='stretch', key="chart_corr2")

            # 指定资产对的滚动相关性
            st.markdown("#### 指定资产对的滚动相关性（60 日窗口）")
            st.caption("选择两只资产，观察它们的相关性在时间维度上的变化，用于识别结构性变化。")
            pair_col1, pair_col2 = st.columns(2)
            with pair_col1:
                corr_a = st.selectbox(
                    "资产 A",
                    corr_assets,
                    index=0,
                    key="corr_pair_a",
                )
            with pair_col2:
                # 默认选择不同的资产 B
                default_b_idx = 1 if len(corr_assets) > 1 else 0
                corr_b = st.selectbox(
                    "资产 B",
                    corr_assets,
                    index=default_b_idx,
                    key="corr_pair_b",
                )

            if corr_a == corr_b:
                st.info("请为 A 和 B 选择不同的资产，以便计算两者的相关性。")
            else:
                from core.correlation import calculate_rolling_correlation
                rolling_corr = calculate_rolling_correlation(
                    log_ret[corr_a], log_ret[corr_b], window=60
                )
                fig_roll = go.Figure()
                fig_roll.add_trace(
                    go.Scatter(
                        x=rolling_corr.index,
                        y=rolling_corr.values,
                        name="滚动相关性",
                        line=dict(color="blue"),
                    )
                )
                fig_roll.add_hline(y=0, line_dash="dash", line_color="gray")
                fig_roll.update_layout(
                    height=400,
                    margin=dict(l=60, r=30, t=50, b=50),
                    title=dict(
                        text=f"{ticker_names.get(corr_a, corr_a)} vs {ticker_names.get(corr_b, corr_b)}",
                        font=dict(size=16, color="#1D1D1F"),
                    ),
                    xaxis_title="日期",
                    yaxis_title="相关系数",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(
                        family="SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif",
                        size=12,
                    ),
                    xaxis=dict(showgrid=True, gridcolor="#E5E5E7", gridwidth=1),
                    yaxis=dict(showgrid=True, gridcolor="#E5E5E7", gridwidth=1, range=[-1, 1]),
                )
                st.plotly_chart(fig_roll, width='stretch', key="chart_rolling_corr")

            # 相关性统计
            st.markdown("#### 相关性统计")
            st.caption("从整体上看这组资产的相关性结构：是否总体相关性较高、是否存在明显的对冲资产等。")
            corr_values = corr_matrix.values[
                np.triu_indices_from(corr_matrix.values, k=1)
            ]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("平均相关系数", f"{np.mean(corr_values):.3f}")
                st.caption("所有资产对相关系数的平均值，越低代表整体分散化越好。")
            with col2:
                st.metric("最大相关系数", f"{np.max(corr_values):.3f}")
                st.caption("最相关的资产对，通常代表同一行业或高度联动资产。")
            with col3:
                st.metric("最小相关系数", f"{np.min(corr_values):.3f}")
                st.caption("最不相关甚至负相关的资产对，是构建对冲和分散风险的重要候选。")


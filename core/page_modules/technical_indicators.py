"""
技术指标分析页面模块
"""
import streamlit as st
import pandas as pd
import plotly.graph_objs as go
from core.page_utils import get_ticker_names, get_selected_tickers, get_data
from core.technical_indicators import calculate_all_indicators, get_trading_signals
from core.cache_utils import calculate_indicators_cached, get_trading_signals_cached
from core.apple_ui import get_apple_chart_layout, APPLE_COLORS


def render_technical_indicators_page():
    """渲染技术指标分析页面"""
    ticker_names = get_ticker_names()
    tickers = get_selected_tickers()
    data = get_data()
    
    if data.empty or len(tickers) == 0:
        st.info("💡 提示：数据正在加载中，如果长时间未显示，请检查资产选择和数据源配置。")
        return
    
    st.markdown("### 技术指标分析")
    st.caption(
        "技术指标是量化分析的重要工具，通过数学公式计算价格和成交量的变化，"
        "帮助识别趋势、超买超卖状态和交易信号。"
    )
    
    selected_ticker = st.selectbox("选择资产", tickers, key="tech_ticker")
    price_series = data[selected_ticker]
    
    # 计算技术指标（使用缓存）
    indicators = calculate_indicators_cached(price_series)
    signals = get_trading_signals_cached(price_series, indicators)
    
    # 检查指标和信号是否有效
    if not isinstance(indicators, pd.DataFrame) or indicators.empty:
        st.warning("⚠️ 无法计算技术指标，请确保数据量足够（至少需要50个交易日）。")
        return
    
    if not isinstance(signals, pd.DataFrame) or signals.empty:
        st.warning("⚠️ 无法生成交易信号，请确保数据量足够。")
        return
    
    # 检查必要的列是否存在
    required_indicators = ['sma_20', 'sma_50', 'rsi', 'macd', 'macd_signal', 'macd_histogram']
    missing_cols = [col for col in required_indicators if col not in indicators.columns]
    if missing_cols:
        st.warning(f"⚠️ 缺少必要的技术指标列：{', '.join(missing_cols)}")
        return
    
    if 'combined_signal' not in signals.columns:
        st.warning("⚠️ 缺少交易信号列：combined_signal")
        return
    
    # 价格与移动平均线
    st.markdown("#### 价格与移动平均线")
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(
        x=price_series.index, y=price_series.values,
        mode='lines', name='价格',
        line=dict(width=2, color=APPLE_COLORS['blue'])
    ))
    fig_price.add_trace(go.Scatter(
        x=indicators['sma_20'].index, y=indicators['sma_20'].values,
        mode='lines', name='SMA 20',
        line=dict(width=1.5, color=APPLE_COLORS['orange'])
    ))
    fig_price.add_trace(go.Scatter(
        x=indicators['sma_50'].index, y=indicators['sma_50'].values,
        mode='lines', name='SMA 50',
        line=dict(width=1.5, color=APPLE_COLORS['green'])
    ))
    fig_price.update_layout(**get_apple_chart_layout(
        title="价格与移动平均线",
        height=380,
        xaxis_title="日期",
        yaxis_title="价格",
    ))
    st.plotly_chart(fig_price, width='stretch', key="chart_price_ma")
    st.markdown("""
    **移动平均线 (Moving Average)**
    - **SMA (Simple Moving Average - 简单移动平均)**：过去N天的收盘价平均值，用于平滑价格波动，识别趋势
    - **用途**：当短期均线（如SMA 20）向上穿越长期均线（如SMA 50）时，通常表示上升趋势；向下穿越时表示下降趋势
    """)
    
    # RSI指标
    st.markdown("#### RSI (相对强弱指标)")
    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(
        x=indicators['rsi'].index, y=indicators['rsi'].values,
        mode='lines', name='RSI',
        line=dict(width=2, color=APPLE_COLORS['blue'])
    ))
    fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="超买 (70)")
    fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="超卖 (30)")
    fig_rsi.update_layout(**get_apple_chart_layout(
        title="RSI 相对强弱指标",
        height=380,
        xaxis_title="日期",
        yaxis_title="RSI",
    ))
    fig_rsi.update_layout(yaxis=dict(range=[0, 100]))
    st.plotly_chart(fig_rsi, width='stretch', key="chart_rsi")
    st.markdown("""
    **RSI (Relative Strength Index - 相对强弱指标)**
    - **计算方法**：RSI = 100 - (100 / (1 + RS))，其中RS = 平均上涨幅度 / 平均下跌幅度
    - **用途**：RSI > 70 通常表示超买（可能回调），RSI < 30 通常表示超卖（可能反弹）
    """)
    
    # MACD指标
    st.markdown("#### MACD (指数平滑异同移动平均线)")
    fig_macd = go.Figure()
    fig_macd.add_trace(go.Scatter(
        x=indicators['macd'].index, y=indicators['macd'].values,
        mode='lines', name='MACD',
        line=dict(width=2, color=APPLE_COLORS['blue'])
    ))
    fig_macd.add_trace(go.Scatter(
        x=indicators['macd_signal'].index, y=indicators['macd_signal'].values,
        mode='lines', name='信号线',
        line=dict(width=2, color=APPLE_COLORS['orange'])
    ))
    fig_macd.add_trace(go.Bar(
        x=indicators['macd_histogram'].index, y=indicators['macd_histogram'].values,
        name='柱状图',
        marker_color=APPLE_COLORS['gray_400']
    ))
    fig_macd.add_hline(y=0, line_dash="dot", line_color="gray")
    fig_macd.update_layout(**get_apple_chart_layout(
        title="MACD 指标",
        height=380,
        xaxis_title="日期",
        yaxis_title="MACD",
    ))
    fig_macd.update_layout(
        xaxis=dict(showgrid=True, gridcolor='#E5E5E7', gridwidth=1),
        yaxis=dict(showgrid=True, gridcolor='#E5E5E7', gridwidth=1),
        legend=dict(bgcolor='rgba(255,255,255,0.9)', bordercolor='#E5E5E7', borderwidth=1)
    )
    st.plotly_chart(fig_macd, width='stretch', key="chart_macd")
    st.markdown("""
    **MACD (Moving Average Convergence Divergence - 指数平滑异同移动平均线)**
    - **计算方法**：MACD = EMA(12) - EMA(26)，信号线 = EMA(MACD, 9)，其中EMA为指数移动平均
    - **用途**：通过快慢均线的分离与聚合来判断趋势变化。当MACD线向上穿越信号线时，通常表示买入信号；向下穿越时表示卖出信号
    """)
    
    # 交易信号
    latest_signal = signals['combined_signal'].iloc[-1]
    signal_text = "买入" if latest_signal > 0.3 else ("卖出" if latest_signal < -0.3 else "持有")
    signal_col = st.columns(1)[0]
    with signal_col:
        st.metric("交易信号", f"{signal_text} ({latest_signal:.2f})")
        st.caption("综合信号 = (均线交叉信号 + RSI信号 + MACD信号) / 3，范围[-1,1]，>0.3买入，<-0.3卖出")
    
    # 当前指标值
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("RSI", f"{indicators['rsi'].iloc[-1]:.2f}")
    with col2:
        st.metric("SMA 20", f"{indicators['sma_20'].iloc[-1]:.2f}")
    with col3:
        st.metric("SMA 50", f"{indicators['sma_50'].iloc[-1]:.2f}")
    with col4:
        st.metric("MACD", f"{indicators['macd'].iloc[-1]:.4f}")


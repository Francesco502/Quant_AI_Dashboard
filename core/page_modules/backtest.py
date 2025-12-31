"""
回测页面模块
"""
import streamlit as st
import pandas as pd
import plotly.graph_objs as go
from core.page_utils import get_ticker_names, get_selected_tickers, get_data
from core.backtest import SimpleBacktest, simple_ma_strategy
from core.technical_indicators import calculate_all_indicators, get_trading_signals
from core.data_service import load_ohlcv_data
from core.stocktradebyz_adapter import (
    generate_selector_signals_for_series,
    STOCKTRADEBYZ_AVAILABLE,
)

# 尝试导入高级预测模块
try:
    from core.advanced_forecasting import (
        generate_ai_signals_for_series,
        ADVANCED_FORECASTING_AVAILABLE,
        XGBOOST_AVAILABLE,
    )
except ImportError:
    ADVANCED_FORECASTING_AVAILABLE = False
    XGBOOST_AVAILABLE = False


def render_backtest_page():
    """渲染回测页面"""
    ticker_names = get_ticker_names()
    tickers = get_selected_tickers()
    data = get_data()
    
    if data.empty or len(tickers) == 0:
        st.info("💡 提示：数据正在加载中，如果长时间未显示，请检查资产选择和数据源配置。")
        return
    
    st.markdown("### 策略回测")
    st.caption("回测是用历史数据验证交易策略的表现，模拟策略在过去的表现，但不能保证未来收益")
    
    strategy = st.selectbox(
        "选择策略",
        [
            "移动平均交叉",
            "RSI超买超卖",
            "MACD信号",
            "AI预测信号 (XGBoost T+1)",
            "Z战法 - BBIKDJ",
            "Z战法 - SuperB1",
            "Z战法 - 填坑 (PeakKDJ)",
        ],
        key="strategy",
    )
    backtest_ticker = st.selectbox("选择资产", tickers, key="backtest_ticker")
    price_series = data[backtest_ticker]
    
    # 初始化session_state用于保存回测结果
    if "backtest_results" not in st.session_state:
        st.session_state.backtest_results = None
    if "backtest_trades" not in st.session_state:
        st.session_state.backtest_trades = None
    if "backtest_config" not in st.session_state:
        st.session_state.backtest_config = None
    
    # 生成交易信号
    if strategy == "移动平均交叉":
        signals_series = simple_ma_strategy(price_series)
    elif strategy in ["RSI超买超卖", "MACD信号"]:
        indicators = calculate_all_indicators(price_series)
        signals = get_trading_signals(price_series, indicators)
        if strategy == "RSI超买超卖":
            signals_series = signals["rsi_signal"]
        else:  # MACD
            signals_series = signals["macd_signal"]
    elif strategy == "AI预测信号 (XGBoost T+1)":
        if not (ADVANCED_FORECASTING_AVAILABLE and XGBOOST_AVAILABLE):
            st.warning("AI 预测回测依赖 XGBoost 等高级模型，请先在环境中安装相关依赖。已回退到简单均线策略。")
            signals_series = simple_ma_strategy(price_series)
        else:
            st.info("AI 预测信号：基于滚动训练的 XGBoost 模型，对未来 T+1 涨跌进行预测，正向为买入，负向为卖出。")
            with st.spinner("正在生成基于 XGBoost 的 AI 预测信号（可能稍慢）..."):
                ai_signals = generate_ai_signals_for_series(
                    price_series,
                    horizon=1,
                    model_type="xgboost",
                    use_enhanced_features=True,
                    min_train_size=60,
                )
            if ai_signals.empty:
                st.warning("AI 预测信号生成失败或数据不足，已回退到简单均线策略。")
                signals_series = simple_ma_strategy(price_series)
            else:
                # 将 AI 信号对齐到价格索引，空缺填 0
                signals_series = ai_signals.reindex(price_series.index).fillna(0.0)
    elif strategy in ["Z战法 - BBIKDJ", "Z战法 - SuperB1", "Z战法 - 填坑 (PeakKDJ)"]:
        if not STOCKTRADEBYZ_AVAILABLE:
            st.warning("Z 战法回测依赖 StockTradebyZ 项目及其依赖（如 scipy），当前未检测到，已回退到简单均线策略。")
            signals_series = simple_ma_strategy(price_series)
        else:
            selector_name_map = {
                "Z战法 - BBIKDJ": "BBIKDJSelector",
                "Z战法 - SuperB1": "SuperB1Selector",
                "Z战法 - 填坑 (PeakKDJ)": "PeakKDJSelector",
            }
            selector_name = selector_name_map.get(strategy)
            if selector_name is None:
                signals_series = simple_ma_strategy(price_series)
            else:
                st.info(f"当前策略：{strategy}（{selector_name}），采用'触发买入 + 固定持有期后卖出'的简化模型。")
                with st.status("正在生成 Z 战法回测信号...", expanded=False) as status:
                    st.write("📊 正在加载 OHLCV 数据...")
                    try:
                        # 为战法信号获取足够的 OHLCV 历史
                        ohlcv_map = load_ohlcv_data([backtest_ticker], days=len(price_series) + 200)
                        ohlcv_df = ohlcv_map.get(backtest_ticker)
                        if ohlcv_df is None or ohlcv_df.empty:
                            status.update(label="OHLCV 数据加载失败", state="error")
                            st.warning("未能为该资产加载足够的 OHLCV 数据，已回退到简单均线策略。")
                            signals_series = simple_ma_strategy(price_series)
                        else:
                            st.write("🔍 正在生成交易信号...")
                            # 复用选股页面配置的参数覆盖（如有）
                            selector_param_overrides = st.session_state.get("z_selector_params", {})
                            sel_params = selector_param_overrides.get(selector_name)
                            z_signals = generate_selector_signals_for_series(
                                ohlcv_df,
                                selector_name=selector_name,
                                params=sel_params,
                                hold_days=5,
                            )
                            # 对齐到回测价格索引，空缺填 0
                            signals_series = z_signals.reindex(price_series.index).fillna(0).astype(int)
                            status.update(label="信号生成完成", state="complete")
                    except Exception as e:
                        status.update(label="信号生成失败", state="error")
                        st.error(f"生成 Z 战法回测信号时出错：{e}，已回退到简单均线策略。")
                        signals_series = simple_ma_strategy(price_series)
    else:
        # 兜底：未知策略名时退回简单均线
        signals_series = simple_ma_strategy(price_series)
    
    signals_df = pd.DataFrame({backtest_ticker: signals_series})
    price_df = pd.DataFrame({backtest_ticker: price_series})
    
    # 检查是否需要重新运行回测（配置改变时）
    current_config = (strategy, backtest_ticker, len(price_series))
    if st.session_state.backtest_config != current_config:
        st.session_state.backtest_results = None
        st.session_state.backtest_trades = None
    
    # 运行回测按钮
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("运行回测", key="backtest_btn"):
        with st.status("正在运行回测...", expanded=False) as status:
            st.write(f"📊 资产: {ticker_names.get(backtest_ticker, backtest_ticker)}")
            st.write(f"📅 回测期间: {price_series.index.min().date()} 至 {price_series.index.max().date()}")
            st.write(f"💰 初始资金: ¥100,000")
            st.write("🔄 正在执行回测计算...")
            backtest = SimpleBacktest(initial_capital=100000)
            results = backtest.run_backtest(price_df, signals_df)
            status.update(label="回测完成！", state="complete")
            
            # 保存结果到session_state
            st.session_state.backtest_results = results
            st.session_state.backtest_trades = backtest.trades
            st.session_state.backtest_config = current_config
            
        # 显示成功提示，并提示用户结果已保存
        st.success("回测完成！结果已保存，请向下滚动查看。")
        st.markdown("<br>", unsafe_allow_html=True)
    
    # 显示回测结果（如果有）
    if st.session_state.backtest_results is not None and st.session_state.backtest_config == current_config:
        results = st.session_state.backtest_results
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总收益率", f"{results['total_return']:.2%}")
            st.caption("回测期间的总收益百分比")
        with col2:
            st.metric("年化收益率", f"{results['annual_return']:.2%}")
            st.caption("将总收益率按年化计算")
        with col3:
            st.metric("夏普比率", f"{results['sharpe_ratio']:.2f}")
            st.caption("风险调整后收益，>1为良好")
        with col4:
            st.metric("最大回撤", f"{results['max_drawdown']:.2%}")
            st.caption("从最高点到最低点的最大跌幅")
        
        # 净值曲线
        fig_equity = go.Figure()
        fig_equity.add_trace(go.Scatter(
            x=results['equity_curve'].index,
            y=results['equity_curve']['equity'],
            name="组合净值",
            line=dict(color='blue', width=2)
        ))
        fig_equity.add_hline(y=100000, line_dash="dash", line_color="#86868B", annotation_text="初始资金")
        fig_equity.update_layout(
            height=400,
            margin=dict(l=60, r=30, t=50, b=50),
            title=dict(text="回测净值曲线", font=dict(size=18, color='#1D1D1F')),
            xaxis_title="日期",
            yaxis_title="净值",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif", size=12),
            xaxis=dict(showgrid=True, gridcolor='#E5E5E7', gridwidth=1),
            yaxis=dict(showgrid=True, gridcolor='#E5E5E7', gridwidth=1)
        )
        st.plotly_chart(fig_equity, width='stretch', key="chart_backtest_equity")
        
        # 交易记录
        if st.session_state.backtest_trades and len(st.session_state.backtest_trades) > 0:
            st.markdown("#### 交易记录（最近20笔）")
            trades_df = pd.DataFrame(st.session_state.backtest_trades)
            st.dataframe(trades_df.tail(20))
        else:
            st.info("本次回测没有产生交易")
    else:
        st.info('请点击上方"运行回测"按钮开始回测')


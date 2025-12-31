"""
交易信号页面模块
"""
import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict
from datetime import datetime
from core.page_utils import get_ticker_names, get_selected_tickers, get_data
from core.strategy_engine import generate_multi_asset_signals, _interpret_action
from core.data_service import load_price_data
from core.paper_trading import generate_equal_weight_plan

# 延迟导入避免循环导入
def _get_save_paper_account():
    from app import save_paper_account
    return save_paper_account

# 尝试导入高级预测模块
try:
    from core.advanced_forecasting import (
        advanced_price_forecast,
        ADVANCED_FORECASTING_AVAILABLE,
    )
except ImportError:
    ADVANCED_FORECASTING_AVAILABLE = False


def render_trading_signals_page():
    """渲染交易信号页面"""
    ticker_names = get_ticker_names()
    tickers = get_selected_tickers()
    data = get_data()
    
    if data.empty or len(tickers) == 0:
        st.info("💡 提示：数据正在加载中，如果长时间未显示，请检查资产选择和数据源配置。")
        return
    
    # 获取预测天数（从侧边栏或默认值）
    forecast_horizon = st.session_state.get("forecast_horizon", 3)
    
    # 信号中心子标签页
    signal_subtab1, signal_subtab2 = st.tabs(["📡 信号中心", "📊 技术指标信号"])
    
    # ========= 信号中心页面 =========
    with signal_subtab1:
        st.markdown("### 📡 信号中心")
        st.caption(
            "统一管理来自策略框架的信号，支持筛选、执行和追踪。"
            "信号来自AI预测、技术指标策略或混合策略。"
        )
        
        try:
            from core.signal_store import get_signal_store
            from core.strategy_manager import get_strategy_manager
            from core.strategy_framework import BaseStrategy
            from core.signal_executor import get_signal_executor
            
            signal_store = get_signal_store()
            strategy_manager = get_strategy_manager()
            signal_executor = get_signal_executor()
            
            # 筛选控制
            col_filter1, col_filter2, col_filter3 = st.columns(3)
            with col_filter1:
                # 策略选择
                strategies = strategy_manager.list_strategies()
                strategy_options = ["全部"] + [s["strategy_id"] for s in strategies]
                selected_strategy = st.selectbox("策略筛选", strategy_options, key="signal_center_strategy")
            
            with col_filter2:
                # 状态筛选
                status_options = ["全部", "pending", "executed", "expired"]
                selected_status = st.selectbox("状态筛选", status_options, key="signal_center_status")
            
            with col_filter3:
                # 日期选择
                from datetime import timedelta
                date_options = ["今天", "最近7天", "最近30天"]
                selected_date_range = st.selectbox("时间范围", date_options, key="signal_center_date")
            
            # 加载信号
            if selected_date_range == "今天":
                signals_df = signal_store.load_signals(
                    date=None,
                    ticker=None,
                    model_id=None,
                    status=selected_status if selected_status != "全部" else None
                )
            else:
                n_days = 7 if selected_date_range == "最近7天" else 30
                signals_df = signal_store.get_latest_signals(ticker=None, n_days=n_days)
                if selected_status != "全部":
                    signals_df = signals_df[signals_df["status"] == selected_status]
            
            # 策略筛选
            if selected_strategy != "全部" and not signals_df.empty:
                # 注意：信号中可能没有strategy_id字段，需要从model_id或其他方式推断
                # 这里简化处理，假设可以通过其他方式关联
                pass
            
            if signals_df.empty:
                st.info("暂无信号数据。信号会在策略执行或AI预测时自动生成。")
            else:
                # 显示信号表格
                st.markdown("#### 信号列表")
                
                # 格式化显示
                display_df = signals_df.copy()
                if "timestamp" in display_df.columns:
                    display_df["时间"] = pd.to_datetime(display_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
                if "prediction" in display_df.columns:
                    display_df["预测收益"] = (display_df["prediction"] * 100).round(2).astype(str) + "%"
                if "confidence" in display_df.columns:
                    display_df["置信度"] = (display_df["confidence"] * 100).round(0).astype(int).astype(str) + "%"
                
                # 信号方向图标
                def format_signal(row):
                    direction = row.get("direction", 0)
                    if direction > 0:
                        return "🟢 买入"
                    elif direction < 0:
                        return "🔴 卖出"
                    else:
                        return "⚪ 持有"
                
                if "direction" in display_df.columns:
                    display_df["信号"] = display_df.apply(format_signal, axis=1)
                
                # 状态格式化
                def format_status(status):
                    status_map = {
                        "pending": "⏳ 待执行",
                        "executed": "✅ 已执行",
                        "expired": "❌ 已过期"
                    }
                    return status_map.get(status, status)
                
                if "status" in display_df.columns:
                    display_df["状态"] = display_df["status"].apply(format_status)
                
                # 选择显示的列
                display_cols = ["时间", "ticker", "信号", "预测收益", "置信度", "状态"]
                available_cols = [col for col in display_cols if col in display_df.columns]
                st.dataframe(display_df[available_cols], width='stretch', hide_index=True)
                
                # 执行控制
                st.markdown("---")
                st.markdown("#### 信号执行")
                
                col_exec1, col_exec2 = st.columns([2, 1])
                with col_exec1:
                    total_capital = st.number_input(
                        "总资金",
                        min_value=10000.0,
                        value=1000000.0,
                        step=10000.0,
                        format="%.0f",
                        key="signal_exec_capital"
                    )
                    max_positions = st.number_input(
                        "最大持仓数",
                        min_value=1,
                        max_value=20,
                        value=5,
                        key="signal_exec_max_pos"
                    )
                
                with col_exec2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("执行选中信号", type="primary", key="signal_exec_btn"):
                        # 获取待执行的信号
                        pending_signals = signals_df[signals_df["status"] == "pending"].copy()
                        
                        if pending_signals.empty:
                            st.warning("没有待执行的信号")
                        else:
                            # 转换为策略信号格式
                            strategy_signals = []
                            for _, row in pending_signals.iterrows():
                                strategy_signals.append({
                                    "ticker": row["ticker"],
                                    "signal": row.get("prediction", 0),
                                    "direction": row.get("direction", 0),
                                    "confidence": row.get("confidence", 0),
                                    "action": "买入" if row.get("direction", 0) > 0 else ("卖出" if row.get("direction", 0) < 0 else "持有"),
                                    "reason": f"模型ID: {row.get('model_id', 'unknown')}",
                                    "model_id": row.get("model_id", "unknown"),
                                })
                            
                            signals_for_exec = pd.DataFrame(strategy_signals)
                            
                            # 获取标的列表
                            tickers_list = signals_for_exec["ticker"].unique().tolist()
                            
                            # 加载价格数据
                            with st.spinner("正在执行信号..."):
                                price_data = load_price_data(
                                    tickers=tickers_list,
                                    days=365,
                                    data_sources=st.session_state.data_sources,
                                    alpha_vantage_key=st.session_state.get("alpha_vantage_key"),
                                    tushare_token=st.session_state.get("tushare_token"),
                                )
                                
                                if price_data is not None and not price_data.empty:
                                    account, msg, details = signal_executor.execute_signals(
                                        signals=signals_for_exec,
                                        strategy_id="signal_center",
                                        total_capital=total_capital,
                                        max_positions=max_positions,
                                        price_data=price_data,
                                        tickers=tickers_list,
                                    )
                                    
                                    st.success(f"执行完成: {msg}")
                                    
                                    # 显示执行摘要
                                    summary = signal_executor.get_execution_summary(signals_for_exec, details)
                                    st.json(summary)
                                    
                                    # 刷新信号列表
                                    st.rerun()
                                else:
                                    st.error("无法加载价格数据，执行失败")
                
                # 导出和历史查看
                col_export1, col_export2 = st.columns(2)
                with col_export1:
                    if st.button("导出信号", key="signal_export_btn"):
                        csv = signals_df.to_csv(index=False)
                        st.download_button(
                            label="下载CSV",
                            data=csv,
                            file_name=f"signals_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                            key="signal_download_btn"
                        )
                
                with col_export2:
                    if st.button("查看历史", key="signal_history_btn"):
                        st.info("历史信号查看功能开发中...")
        
        except ImportError as e:
            st.warning(f"信号中心功能需要相关模块支持: {e}")
        except Exception as e:
            st.error(f"加载信号中心失败: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # ========= 原有技术指标信号页面 =========
    with signal_subtab2:
        st.markdown("### 多资产交易信号总览")
        st.caption(
            "基于技术指标（均线、RSI、MACD）为当前选中的所有资产生成统一的买入/卖出/观望建议，"
            "可作为初步选股与仓位决策的参考。"
        )

        # --- 信号参数控制 ---
        st.markdown("#### 信号阈值设置")
        col_th1, col_th2 = st.columns(2)
        with col_th1:
            buy_threshold = st.slider(
                "买入阈值（combined ≥）",
                0.0,
                1.0,
                0.3,
                0.05,
                help="综合信号分数高于该值时给出'买入'建议（默认 0.30）",
            )
            strong_buy_threshold = st.slider(
                "强烈买入阈值（combined ≥）",
                0.0,
                1.0,
                0.7,
                0.05,
                help="综合信号分数高于该值时给出'强烈买入'建议（默认 0.70）",
            )
            # 保证强烈买入阈值不小于买入阈值
            strong_buy_threshold = max(strong_buy_threshold, buy_threshold)
        with col_th2:
            strong_sell_threshold = st.slider(
                "强烈卖出阈值（combined ≤）",
                -1.0,
                0.0,
                -0.7,
                0.05,
                help="综合信号分数低于该值时给出'强烈卖出'建议（默认 -0.70）",
            )
            sell_threshold = st.slider(
                "卖出阈值（combined ≤）",
                -1.0,
                0.0,
                -0.3,
                0.05,
                help="综合信号分数低于该值时给出'卖出'建议（默认 -0.30）",
            )
            # 保证普通卖出阈值不高于强烈卖出阈值
            strong_sell_threshold = min(strong_sell_threshold, sell_threshold)

        # --- AI 预测加权（可选） ---
        ai_adjust_enabled = False
        ai_weight = 0.3
        ai_horizon = forecast_horizon
        if ADVANCED_FORECASTING_AVAILABLE:
            st.markdown("#### AI 预测加权（可选）")
            ai_col1, ai_col2, ai_col3 = st.columns([1.5, 1, 1])
            with ai_col1:
                ai_adjust_enabled = st.checkbox(
                    "使用 AI 趋势预测调整综合信号",
                    value=False,
                    help="结合未来 T+N 预测涨跌幅，对技术面综合信号进行加权放大或削弱。",
                )
            with ai_col2:
                if ai_adjust_enabled:
                    ai_weight = st.slider(
                        "AI 权重",
                        0.0,
                        1.0,
                        0.3,
                        0.05,
                        help="AI 预测信号在最终综合评分中的占比，0=仅技术面，1=仅AI。",
                    )
            with ai_col3:
                if ai_adjust_enabled:
                    ai_horizon = st.select_slider(
                        "AI 预测天数（T+）",
                        options=[1, 3, 5],
                        value=forecast_horizon,
                        help="用于生成 AI 加权的预测周期，通常与左侧'预测天数'保持一致。",
                    )

        # 使用价格数据为所有资产生成综合信号（带阈值）
        with st.spinner("正在为所有资产生成交易信号..."):
            signal_table = generate_multi_asset_signals(
                data[tickers],
                min_history=60,
                buy_threshold=buy_threshold,
                strong_buy_threshold=strong_buy_threshold,
                sell_threshold=sell_threshold,
                strong_sell_threshold=strong_sell_threshold,
            )

            # 使用 AI 预测对综合信号进行加权调整
            if ai_adjust_enabled:
                try:
                    # 优先尝试集成模型，否则退回 auto
                    try:
                        ai_forecast_df = advanced_price_forecast(
                            data[tickers],
                            horizon=ai_horizon,
                            model_type="ensemble",
                            use_enhanced_features=True,
                        )
                    except Exception:
                        ai_forecast_df = advanced_price_forecast(
                            data[tickers],
                            horizon=ai_horizon,
                            model_type="auto",
                            use_enhanced_features=True,
                        )

                    last_row_all = data.iloc[-1]
                    ai_scores: Dict[str, float] = {}
                    for t in tickers:
                        if t in ai_forecast_df.columns and t in last_row_all.index:
                            last_p = float(last_row_all[t])
                            if last_p <= 0 or np.isnan(last_p):
                                continue
                            pred_last = float(ai_forecast_df[t].iloc[-1])
                            ai_ret = (pred_last - last_p) / last_p
                            # 以 ±10% 涨跌对应 ±1 分，限制在 [-1, 1]
                            ai_score = float(np.clip(ai_ret / 0.1, -1.0, 1.0))
                            ai_scores[t] = ai_score

                    if ai_scores:
                        signal_table["combined_signal_raw"] = signal_table[
                            "combined_signal"
                        ]
                        signal_table["ai_score"] = signal_table["ticker"].map(
                            ai_scores
                        ).fillna(0.0)
                        signal_table["combined_signal"] = (
                            (1 - ai_weight) * signal_table["combined_signal"]
                            + ai_weight * signal_table["ai_score"]
                        )
                        # 使用调整后的综合信号重新生成 action
                        signal_table["action"] = [
                            _interpret_action(
                                float(score),
                                buy_threshold=buy_threshold,
                                strong_buy_threshold=strong_buy_threshold,
                                sell_threshold=sell_threshold,
                                strong_sell_threshold=strong_sell_threshold,
                            )
                            for score in signal_table["combined_signal"]
                        ]
                except Exception as e:
                    st.warning(f"AI 预测加权失败：{e}（已回退为纯技术面信号）")

        if signal_table.empty:
            st.info("当前可用数据不足，暂时无法生成多资产交易信号。请适当延长历史回看天数或检查资产代码。")
        else:
            # --- 结果筛选控制 ---
            st.markdown("#### 结果筛选")
            view_mode = st.radio(
                "显示范围",
                ["显示全部", "只看买入候选", "只看卖出候选"],
                index=0,
                horizontal=True,
                help="买入候选包括'买入/强烈买入'，卖出候选包括'卖出/强烈卖出'。",
            )

            filtered_signals = signal_table.copy()
            if view_mode == "只看买入候选":
                filtered_signals = filtered_signals[
                    filtered_signals["action"].isin(["买入", "强烈买入"])
                ]
            elif view_mode == "只看卖出候选":
                filtered_signals = filtered_signals[
                    filtered_signals["action"].isin(["卖出", "强烈卖出"])
                ]

            if filtered_signals.empty:
                st.warning("在当前阈值与筛选条件下，没有符合条件的资产。可以适当放宽阈值或切换显示范围。")
                # 即使过滤结果为空，下面统计仍基于原始 signal_table，方便整体把握
                base_for_stats = signal_table
            else:
                base_for_stats = filtered_signals

            # 增加显示名称与简单解释列
            display_names = [ticker_names.get(t, t) for t in filtered_signals["ticker"]]
            signal_table_display = filtered_signals.copy()
            signal_table_display.insert(0, "资产", display_names)

            # 最新价格货币符号
            def _format_price(row):
                t = row["ticker"]
                p = row["last_price"]
                currency = "¥" if (".SZ" in t or ".SS" in t or (t.isdigit() and len(t) == 6)) else "$"
                return f"{currency}{p:,.2f}"

            signal_table_display["最新价格"] = signal_table_display.apply(_format_price, axis=1)

            # 数值格式化列（RSI / 均线 / 风险）
            signal_table_display["RSI值"] = signal_table_display["rsi_value"]
            signal_table_display["SMA20"] = signal_table_display["sma_20"]
            signal_table_display["SMA50"] = signal_table_display["sma_50"]
            # 将波动率和回撤转换为百分比数值，便于统一格式化显示
            signal_table_display["年化波动率"] = signal_table_display["annual_volatility"] * 100.0
            signal_table_display["最大回撤"] = signal_table_display["max_drawdown"] * 100.0
            signal_table_display["因子理由"] = signal_table_display["reason"]

            # 简洁 / 详细 两种展示模式以减少列宽
            st.markdown("#### 显示模式")
            display_mode = st.radio(
                "表格列显示",
                ["简洁模式", "详细模式"],
                index=0,
                horizontal=True,
                help="简洁模式仅展示核心信号与风险信息；详细模式展示全部技术细节列。",
            )

            if display_mode == "简洁模式":
                cols_to_show = [
                    "资产",
                    "ticker",
                    "最新价格",
                    "combined_signal",
                    "RSI值",
                    "年化波动率",
                    "最大回撤",
                    "action",
                    "因子理由",
                ]
            else:
                cols_to_show = [
                    "资产",
                    "ticker",
                    "最新价格",
                    "combined_signal",
                    "RSI值",
                    "SMA20",
                    "SMA50",
                    "ma_cross",
                    "rsi_signal",
                    "macd_signal",
                    "年化波动率",
                    "最大回撤",
                    "action",
                    "因子理由",
                ]

            signal_table_display = signal_table_display[cols_to_show]

            st.markdown("#### 策略信号列表（已按综合信号由高到低排序）")
            st.dataframe(
                signal_table_display,
                width="stretch",
                hide_index=True,
                column_config={
                    "资产": st.column_config.TextColumn("资产", help="资产名称（可在资产池标签页中自定义）"),
                    "ticker": st.column_config.TextColumn("代码", help="交易代码，如 600519.SS、AAPL、BTC-USD 等"),
                    "最新价格": st.column_config.TextColumn("最新价格", help="最近一个交易日的收盘价或净值"),
                    "combined_signal": st.column_config.NumberColumn(
                        "综合信号",
                        help="综合均线、RSI、MACD 得到的信号分数，范围约为 [-1, 1]，越高越偏多",
                        format="%.2f",
                    ),
                    "RSI值": st.column_config.NumberColumn(
                        "RSI值",
                        help="最新 RSI 数值：<30 通常视为超卖，>70 通常视为超买",
                        format="%.1f",
                    ),
                    "SMA20": st.column_config.NumberColumn(
                        "SMA20",
                        help="20日简单移动平均，用于反映短中期价格趋势",
                        format="%.2f",
                    ),
                    "SMA50": st.column_config.NumberColumn(
                        "SMA50",
                        help="50日简单移动平均，用于反映中期价格趋势",
                        format="%.2f",
                    ),
                    "ma_cross": st.column_config.NumberColumn(
                        "均线信号",
                        help="短期均线相对长期均线的位置：1=金叉偏多，-1=死叉偏空，0=中性",
                        format="%.1f",
                    ),
                    "rsi_signal": st.column_config.NumberColumn(
                        "RSI信号",
                        help="基于 RSI 超买超卖区间的信号：1=超卖偏多，-1=超买偏空，0=中性",
                        format="%.1f",
                    ),
                    "macd_signal": st.column_config.NumberColumn(
                        "MACD信号",
                        help="MACD 相对 signal 线的位置：1=偏多，-1=偏空，0=中性",
                        format="%.1f",
                    ),
                    "年化波动率": st.column_config.NumberColumn(
                        "年化波动率 (%)",
                        help="基于日收益率估算的单票年化波动率，单位为百分比，数值越高价格波动越大",
                        format="%.1f",
                    ),
                    "最大回撤": st.column_config.NumberColumn(
                        "最大回撤 (%)",
                        help="在观察窗口内从高点到低点的最大跌幅（百分比，负值表示回撤），绝对值越大历史回撤越深",
                        format="%.1f",
                    ),
                    "action": st.column_config.TextColumn(
                        "交易建议",
                        help="根据综合信号分数给出的文字化建议：强烈买入/买入/观望/卖出/强烈卖出",
                    ),
                    "因子理由": st.column_config.TextColumn(
                        "因子理由",
                        help="结合 RSI、均线、MACD 等技术指标给出的简要中文说明，解释为什么产生当前交易建议",
                    ),
                },
            )

            # 简要统计：当前买入/卖出/观望数量
            action_counts = base_for_stats["action"].value_counts()
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### 当前信号分布概览")
            cols = st.columns(3)
            buy_cnt = int(
                action_counts.get("买入", 0)
                + action_counts.get("强烈买入", 0)
            )
            sell_cnt = int(
                action_counts.get("卖出", 0)
                + action_counts.get("强烈卖出", 0)
            )
            hold_cnt = int(
                action_counts.get("观望/持有", 0)
                + action_counts.get("观望/数据不足", 0)
            )
            with cols[0]:
                st.metric("买入/加仓候选", buy_cnt)
            with cols[1]:
                st.metric("卖出/减仓候选", sell_cnt)
            with cols[2]:
                st.metric("观望标的", hold_cnt)

            # --- 简单模拟建仓计划（等权分配示例） ---
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### 简单模拟建仓计划（等权示例）")
            st.caption(
                "此处不连接真实券商账户，仅基于当前买入信号，假设总资金等权分配到若干标的上，"
                "用于帮助从'信号'直观过渡到'买多少'的数量级感知。"
            )

            col_cap, col_pos = st.columns(2)
            with col_cap:
                sim_capital = st.number_input(
                    "模拟总资金（单位：元）",
                    min_value=10_000.0,
                    max_value=10_000_000.0,
                    value=100_000.0,
                    step=10_000.0,
                    help="仅用于计算模拟建仓数量，不会影响任何真实账户。",
                )
            with col_pos:
                max_positions = st.slider(
                    "最多持仓数量",
                    min_value=1,
                    max_value=20,
                    value=5,
                    help="从买入候选中按综合信号排序，最多选取多少只资产进行等权建仓。",
                )

            plan_df = generate_equal_weight_plan(signal_table, total_capital=sim_capital, max_positions=max_positions)

            if plan_df.empty:
                st.info("当前没有符合条件的买入候选，或价格/资金不足以买入整股/份额，暂无法生成建仓计划。")
            else:
                # 增加名称与格式化
                display_names_plan = [ticker_names.get(t, t) for t in plan_df["ticker"]]
                plan_show = plan_df.copy()
                plan_show.insert(0, "资产", display_names_plan)

                def _fmt_price(p: float) -> str:
                    return f"{p:,.2f}"

                def _fmt_notional(v: float) -> str:
                    return f"{v:,.2f}"

                plan_show["价格"] = plan_show["last_price"].apply(_fmt_price)
                plan_show["建仓金额"] = plan_show["notional"].apply(_fmt_notional)

                plan_show = plan_show[
                    ["资产", "ticker", "action", "价格", "shares", "建仓金额", "combined_signal"]
                ]

                st.dataframe(
                    plan_show,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "资产": st.column_config.TextColumn("资产"),
                        "ticker": st.column_config.TextColumn("代码"),
                        "action": st.column_config.TextColumn("方向"),
                        "价格": st.column_config.TextColumn("价格"),
                        "shares": st.column_config.NumberColumn("数量", help="模拟买入股数/份额"),
                        "建仓金额": st.column_config.TextColumn("建仓金额"),
                        "combined_signal": st.column_config.NumberColumn(
                            "综合信号", format="%.2f", help="用于排序的信号分数"
                        ),
                    },
                )

                # 按钮：将当前计划应用为当日调仓指令，更新模拟账户（委托交易引擎处理）
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("应用为当日调仓指令（更新模拟账户）", key="apply_plan_to_paper"):
                    from core.account import ensure_account_dict
                    from core.trading_engine import apply_equal_weight_rebalance

                    # 确保账户结构完整
                    st.session_state.paper_account = ensure_account_dict(
                        st.session_state.get("paper_account"),
                        initial_capital=1_000_000.0,
                    )
                    account = st.session_state.paper_account

                    # 通过交易引擎执行一轮等权调仓
                    account, msg = apply_equal_weight_rebalance(
                        account=account,
                        signal_table=signal_table,
                        data=data,
                        total_capital=account.get("initial_capital", 1_000_000.0),
                        max_positions=max_positions,
                    )
                    st.session_state.paper_account = account
                    # 每次调仓完成后立即持久化模拟账户状态
                    save_paper_account_func = _get_save_paper_account()
                    save_paper_account_func()

                    if "成功" in msg or "执行" in msg:
                        st.success(f"模拟账户已完成调仓：{msg} 可前往'模拟账户'标签页查看持仓与权益曲线。")
                    else:
                        st.warning(msg)


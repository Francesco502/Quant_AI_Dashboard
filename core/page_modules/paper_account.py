"""
模拟账户页面模块
"""
import streamlit as st
import pandas as pd
import plotly.graph_objs as go
from core.page_utils import get_ticker_names, get_selected_tickers, get_data
from core.account import ensure_account_dict, compute_equity, append_equity_history
# 延迟导入避免循环导入
def _get_save_paper_account():
    from app import save_paper_account
    return save_paper_account


def render_paper_account_page():
    """渲染模拟账户页面"""
    ticker_names = get_ticker_names()
    tickers = get_selected_tickers()
    data = get_data()
    
    if data.empty or len(tickers) == 0:
        st.info("💡 提示：数据正在加载中，如果长时间未显示，请检查资产选择和数据源配置。")
        return
    
    st.markdown("### 模拟账户概览")
    st.caption(
        "基于上一步生成的模拟建仓计划，在本地会话中维护一个简单的'纸面账户'，"
        "用于查看持仓、现金与权益曲线。不连接任何真实券商，仅用于研究与演示。"
    )

    # 初始化模拟账户状态（通过 account 模块统一处理）
    st.session_state.paper_account = ensure_account_dict(
        st.session_state.get("paper_account"),
        initial_capital=1_000_000.0,
    )
    account = st.session_state.paper_account

    # 计算当前总权益与收益
    latest_prices = {}
    for t in tickers:
        if t in data.columns:
            latest_prices[t] = float(data[t].iloc[-1])
    equity = compute_equity(account, latest_prices)
    current_pnl = equity - account["initial_capital"]
    if current_pnl > 0:
        current_pnl_str = f"+{current_pnl:,.0f} 元"
    elif current_pnl < 0:
        current_pnl_str = f"{current_pnl:,.0f} 元"
    else:
        current_pnl_str = "0 元"

    # 概览卡片：初始资金 / 当前现金 / 当前总权益 / 当前收益
    col_cfg1, col_cfg2, col_cfg3, col_cfg4 = st.columns(4)
    with col_cfg1:
        st.metric("初始资金", f"{account['initial_capital']:,.0f} 元")
    with col_cfg2:
        st.metric("当前现金", f"{account['cash']:,.0f} 元")
    with col_cfg3:
        st.metric("当前总权益", f"{equity:,.0f} 元")
    with col_cfg4:
        st.metric(
            "当前收益",
            current_pnl_str,
            help="当前总权益减去初始资金；正值为盈利，负值为亏损",
        )

    st.markdown("#### 当前持仓")
    if not account["positions"]:
        st.info("当前尚无模拟持仓。可以在'交易信号'页生成建仓计划并应用为当日调仓指令。")
    else:
        pos_records = []
        for t, sh in account["positions"].items():
            price = latest_prices.get(t, 0.0)
            value = sh * price
            pos_records.append(
                {
                    "代码": t,
                    "名称": ticker_names.get(t, t),
                    "数量": sh,
                    "最新价格": f"{price:,.2f}",
                    "市值": f"{value:,.2f}",
                }
            )
        df_pos = pd.DataFrame(pos_records)
        st.dataframe(df_pos, hide_index=True, width="stretch")

    st.markdown("#### 交易记录（本会话）")
    if not account["trade_log"]:
        st.info("暂无模拟交易记录。")
    else:
        df_trades = pd.DataFrame(account["trade_log"])
        st.dataframe(df_trades, hide_index=True, width="stretch")

    st.markdown("#### 权益曲线（本会话）")
    # 更新权益历史：以当前最后一个数据日期为节点
    if data.index.size > 0:
        last_date = data.index[-1]
        append_equity_history(account, equity, dt=last_date)
        st.session_state.paper_account = account
        save_paper_account = _get_save_paper_account()
        save_paper_account()
    if account["equity_history"]:
        eh = pd.DataFrame(account["equity_history"]).drop_duplicates(
            subset=["date"], keep="last"
        )
        # 兼容历史数据中混合的字符串 / Timestamp 日期格式
        if "date" in eh.columns:
            eh["date"] = pd.to_datetime(eh["date"], errors="coerce")
            eh = eh.dropna(subset=["date"]).sort_values("date")
        else:
            eh = eh.sort_values("date")
        fig_eq = go.Figure()
        fig_eq.add_trace(
            go.Scatter(
                x=eh["date"],
                y=eh["equity"],
                mode="lines",
                name="模拟账户权益",
            )
        )
        fig_eq.update_layout(
            height=400,
            margin=dict(l=60, r=30, t=50, b=50),
            xaxis_title="日期",
            yaxis_title="权益（元）",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_eq, width='stretch', key="chart_equity")


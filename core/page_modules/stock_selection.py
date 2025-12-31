"""
选股页面模块（StockTradebyZ 战法）
"""
import streamlit as st
import pandas as pd
import plotly.graph_objs as go
from core.page_utils import get_ticker_names, get_selected_tickers, get_data
from core.stocktradebyz_adapter import (
    run_selectors_for_market,
    run_selectors_for_universe,
    get_default_selector_configs,
    STOCKTRADEBYZ_AVAILABLE,
)
from core.app_utils import save_selector_results
from core.apple_ui import get_apple_chart_layout, APPLE_COLORS
# 延迟导入避免循环导入
def _get_render_data_warehouse_monitor():
    from app import render_data_warehouse_monitor
    return render_data_warehouse_monitor

def _get_save_paper_account():
    from app import save_paper_account
    return save_paper_account


def render_stock_selection_page():
    """渲染选股页面"""
    ticker_names = get_ticker_names()
    tickers = get_selected_tickers()
    data = get_data()
    
    st.markdown("### 选股")
    st.caption(
        "基于 A 股全市场日线数据（./data 目录），"
        "使用Z哥战法（BBIKDJ / SuperB1 / 补票 / 填坑 / 上穿60放量）进行全市场扫描与选股，"
        "并可一键生成等权建仓计划，联动模拟账户。"
    )
    
    # 显示数据仓库监控
    render_data_warehouse_monitor = _get_render_data_warehouse_monitor()
    render_data_warehouse_monitor()
    st.markdown("---")

    if not STOCKTRADEBYZ_AVAILABLE:
        from core.stocktradebyz_adapter import STZ_DIR
        try:
            from core.stocktradebyz_adapter import _stz_error
            error_detail = f"\n\n**详细错误**: {_stz_error}"
        except:
            error_detail = ""
        
        st.error(
            f"❌ 未检测到 StockTradebyZ 战法模块\n\n"
            f"**预期路径**: `{STZ_DIR}`\n\n"
            f"**解决方案**:\n"
            f"1. 确认 `core/stocktradebyz/Selector.py` 和 `core/stocktradebyz/configs.json` 文件存在\n"
            f"2. 确认已安装依赖: `pip install scipy`\n"
            f"3. 确保 `data/prices/A股/` 目录中有 A 股 parquet 数据文件（或提供 `core/stocktradebyz/stocklist.csv`）\n"
            f"4. 重新打开本页面{error_detail}"
        )
    else:
        # 评估模式选择
        eval_mode = st.radio(
            "评估模式",
            options=["全市场扫描", "资产池评估"],
            index=0,
            key="z_eval_mode",
            help="全市场扫描：对所有A股进行选股筛选；资产池评估：对资产池中选中的资产进行战法评估",
        )
        
        st.markdown("#### 配置")
        # 第一行：日期选择
        if data.empty:
            st.warning("数据尚未加载，请先选择资产并加载数据。")
            return
        
        last_date = data.index.max()
        first_date = data.index.min()
        trade_date = st.date_input(
            "选股交易日",
            value=last_date.date(),
            min_value=first_date.date(),
            max_value=last_date.date(),
            key="z_select_trade_date",
        )

        # 第二行：战法选择
        try:
            default_cfgs = get_default_selector_configs()
            selector_label_map = {
                f"{cfg.alias}（{cfg.class_name}）": cfg.class_name
                for cfg in default_cfgs
            }
            selector_labels = list(selector_label_map.keys())
        except Exception:
            selector_label_map = {
                "BBIKDJ（少妇战法）": "BBIKDJSelector",
                "SuperB1（SuperB1战法）": "SuperB1Selector",
                "补票战法（BBIShortLong）": "BBIShortLongSelector",
                "填坑战法（PeakKDJ）": "PeakKDJSelector",
                "上穿60放量战法（MA60CrossVolumeWave）": "MA60CrossVolumeWaveSelector",
            }
            selector_labels = list(selector_label_map.keys())

        selected_labels = st.multiselect(
            "选择战法策略",
            options=selector_labels,
            default=selector_labels,
            key="z_select_strategies",
        )
        selected_selectors = [
            selector_label_map[l] for l in selected_labels if l in selector_label_map
        ]

        # ----- 高级参数（可选）：对部分战法暴露少量关键参数 -----
        selector_param_overrides: dict = st.session_state.get("z_selector_params", {})
        with st.expander("高级参数（可选）", expanded=False):
            st.caption(
                "以下参数将覆盖 StockTradebyZ/configs.json 中的默认设置，仅对当前选中的战法生效；"
                "如不熟悉含义，可保持默认。"
            )
            # 建立类名 -> 默认配置 映射，便于取出默认参数
            default_cfg_map = (
                {cfg.class_name: cfg for cfg in default_cfgs} if "default_cfgs" in locals() else {}
            )

            for class_name in selected_selectors:
                cfg = default_cfg_map.get(class_name)
                base_params = dict(cfg.params) if cfg else {}
                current_override = dict(selector_param_overrides.get(class_name, {}))

                if class_name == "BBIKDJSelector":
                    st.markdown("**BBIKDJ（少妇战法）参数**")
                    j_threshold = st.number_input(
                        "J 阈值（越小越极端超卖）",
                        value=float(
                            current_override.get(
                                "j_threshold", base_params.get("j_threshold", 15)
                            )
                        ),
                        key="z_param_bbi_j_threshold",
                    )
                    max_window = st.number_input(
                        "最大窗口长度（用于判断趋势和波动区间）",
                        min_value=20,
                        max_value=300,
                        step=10,
                        value=int(
                            current_override.get(
                                "max_window", base_params.get("max_window", 120)
                            )
                        ),
                        key="z_param_bbi_max_window",
                    )
                    current_override["j_threshold"] = j_threshold
                    current_override["max_window"] = max_window

                elif class_name == "SuperB1Selector":
                    st.markdown("**SuperB1 战法参数**")
                    lookback_n = st.number_input(
                        "回看窗口（lookback_n）",
                        min_value=5,
                        max_value=60,
                        step=1,
                        value=int(
                            current_override.get(
                                "lookback_n", base_params.get("lookback_n", 10)
                            )
                        ),
                        key="z_param_superb1_lookback_n",
                    )
                    price_drop_pct = st.number_input(
                        "当日相对前一日下跌比例阈值（price_drop_pct）",
                        min_value=0.0,
                        max_value=0.2,
                        step=0.005,
                        format="%.3f",
                        value=float(
                            current_override.get(
                                "price_drop_pct", base_params.get("price_drop_pct", 0.02)
                            )
                        ),
                        key="z_param_superb1_price_drop",
                    )
                    current_override["lookback_n"] = lookback_n
                    current_override["price_drop_pct"] = price_drop_pct

                elif class_name == "PeakKDJSelector":
                    st.markdown("**填坑战法（PeakKDJ）参数**")
                    j_threshold_pk = st.number_input(
                        "J 阈值（越小越极端超卖）",
                        value=float(
                            current_override.get(
                                "j_threshold", base_params.get("j_threshold", 10)
                            )
                        ),
                        key="z_param_peak_j_threshold",
                    )
                    fluc_threshold = st.number_input(
                        "当日相对参考峰波动率上限（fluc_threshold）",
                        min_value=0.0,
                        max_value=0.1,
                        step=0.005,
                        format="%.3f",
                        value=float(
                            current_override.get(
                                "fluc_threshold", base_params.get("fluc_threshold", 0.03)
                            )
                        ),
                        key="z_param_peak_fluc",
                    )
                    current_override["j_threshold"] = j_threshold_pk
                    current_override["fluc_threshold"] = fluc_threshold

                # 将覆盖参数写回总字典
                selector_param_overrides[class_name] = current_override

        # 持久化到 session_state，供选股与回测共用
        st.session_state["z_selector_params"] = selector_param_overrides

        st.markdown("---")
        run_col, _ = st.columns([1, 3])
        with run_col:
            button_text = "运行资产池评估" if eval_mode == "资产池评估" else "运行战法选股"
            run_clicked = st.button(button_text, key="z_select_run")

        result_df = None
        if run_clicked:
            if not selected_selectors:
                st.warning("请至少选择一个战法策略。")
            else:
                progress_bar = st.progress(0.0)
                status_text = st.empty()

                def _on_progress(p: float, msg: str) -> None:
                    try:
                        progress_bar.progress(max(0.0, min(1.0, p)))
                        status_text.write(msg)
                    except Exception:
                        pass

                if eval_mode == "资产池评估":
                    # 资产池评估模式
                    selected_tickers = st.session_state.get("selected_tickers", [])
                    if not selected_tickers:
                        st.warning("资产池中未选择任何资产，请先在'资产池'页面添加资产。")
                        result_df = None
                    else:
                        with st.spinner(f"正在对 {len(selected_tickers)} 个资产进行战法评估..."):
                            try:
                                _on_progress(0.1, f"开始加载 {len(selected_tickers)} 个资产的数据...")
                                result_df = run_selectors_for_universe(
                                    tickers=selected_tickers,
                                    trade_date=pd.to_datetime(trade_date),
                                    selector_names=selected_selectors,
                                    selector_params=selector_param_overrides,
                                    name_map=ticker_names,
                                )
                                _on_progress(1.0, "评估完成")
                            except Exception as e:
                                st.error(f"运行资产池评估时出错：{e}")
                                result_df = None
                else:
                    # 全市场扫描模式
                    with st.spinner("正在基于全市场数据运行 Z 战法选股...（首次运行可能较慢）"):
                        try:
                            result_df = run_selectors_for_market(
                                trade_date=pd.to_datetime(trade_date),
                                selector_names=selected_selectors,
                                selector_params=selector_param_overrides,
                                progress_callback=_on_progress,
                            )
                        except Exception as e:
                            st.error(f"运行战法选股时出错：{e}")
                            result_df = None

                if result_df is None or result_df.empty:
                    status_text.write("当前未找到任何符合所选战法条件的股票（资产）。")
                else:
                    st.session_state["z_select_results"] = result_df
                    # 自动保存选股结果
                    save_success = save_selector_results(result_df, trade_date)
                    if save_success:
                        status_text.write(f"✅ 选股完成！结果已保存到本地数据仓库。")
                    else:
                        status_text.write(f"⚠️ 选股完成，但保存到本地数据仓库时出现错误。")

        # 若本次未点击按钮，则尝试读取上一次的结果，便于后续直接生成建仓计划
        if result_df is None:
            stored = st.session_state.get("z_select_results")
            if isinstance(stored, pd.DataFrame) and not stored.empty:
                result_df = stored

        if result_df is not None and not result_df.empty:
            # 获取当前评估模式（可能从 session_state 读取）
            current_eval_mode = st.session_state.get("z_eval_mode", "全市场扫描")
            
            if current_eval_mode == "资产池评估":
                # 资产池评估模式：展示汇总表格和热力图
                st.markdown("#### 资产池战法评估结果")
                
                # 构建资产 × 战法的推荐矩阵
                selected_tickers = st.session_state.get("selected_tickers", [])
                if not selected_tickers:
                    st.warning("资产池中未选择任何资产。")
                else:
                    # 创建战法别名到类名的映射（反向）
                    selector_class_to_alias = {}
                    for _, row in result_df.iterrows():
                        if row["selector_class"] not in selector_class_to_alias:
                            selector_class_to_alias[row["selector_class"]] = row.get("selector_alias", row["selector_class"])
                    
                    # 创建评估矩阵（使用战法别名作为列名）
                    selector_aliases = [selector_class_to_alias.get(s, s) for s in selected_selectors]
                    eval_matrix = pd.DataFrame(
                        index=selected_tickers,
                        columns=selector_aliases,
                        data=0.0
                    )
                    
                    # 填充矩阵：1表示被选中，0表示未选中
                    for _, row in result_df.iterrows():
                        ticker = row["ticker"]
                        selector_alias = row.get("selector_alias", row.get("selector_class", ""))
                        if ticker in eval_matrix.index and selector_alias in eval_matrix.columns:
                            eval_matrix.loc[ticker, selector_alias] = 1.0
                    
                    # 计算综合得分（被多少个战法选中）
                    if len(eval_matrix.columns) > 0:
                        eval_matrix["综合得分"] = eval_matrix.sum(axis=1)
                    else:
                        eval_matrix["综合得分"] = 0.0
                    
                    eval_matrix["推荐等级"] = eval_matrix["综合得分"].apply(
                        lambda x: "强烈推荐" if x >= len(selector_aliases) * 0.6 
                        else "推荐" if x > 0 
                        else "中性"
                    )
                    
                    # 添加资产名称和价格
                    eval_matrix.insert(0, "资产名称", [ticker_names.get(t, t) for t in eval_matrix.index])
                    
                    # 从 result_df 获取价格信息
                    price_map = {}
                    for _, row in result_df.iterrows():
                        ticker = row["ticker"]
                        if ticker not in price_map:
                            price_map[ticker] = row.get("last_close", 0.0)
                    
                    eval_matrix["收盘价"] = [price_map.get(t, 0.0) for t in eval_matrix.index]
                    
                    # 按综合得分排序
                    eval_matrix = eval_matrix.sort_values("综合得分", ascending=False)
                    
                    # 展示汇总表格
                    st.markdown("##### 评估汇总表")
                    display_cols = ["资产名称", "收盘价"] + selector_aliases + ["综合得分", "推荐等级"]
                    display_cols = [c for c in display_cols if c in eval_matrix.columns]
                    
                    display_df = eval_matrix[display_cols].copy()
                    display_df["收盘价"] = display_df["收盘价"].map(lambda x: f"{x:,.2f}" if x > 0 else "-")
                    display_df["综合得分"] = display_df["综合得分"].map(lambda x: f"{x:.0f}")
                    
                    st.dataframe(
                        display_df,
                        hide_index=True,
                        width="stretch",
                    )
                    
                    # 热力图展示
                    st.markdown("##### 推荐热力图")
                    
                    # 准备热力图数据（排除综合得分、推荐等级、资产名称、收盘价列）
                    heatmap_data = eval_matrix.drop(columns=["资产名称", "收盘价", "综合得分", "推荐等级"], errors="ignore")
                    
                    if not heatmap_data.empty:
                        # 创建热力图 - Apple 风格
                        fig = go.Figure(data=go.Heatmap(
                            z=heatmap_data.values,
                            x=heatmap_data.columns.tolist(),
                            y=[ticker_names.get(t, t) for t in heatmap_data.index],
                            colorscale=[[0, APPLE_COLORS['gray_50']], [1, APPLE_COLORS['green']]],
                            showscale=True,
                            colorbar=dict(
                                title="推荐",
                                thickness=15,
                                len=0.6,
                                tickfont=dict(size=11, color=APPLE_COLORS['gray_600']),
                            ),
                            text=heatmap_data.values,
                            texttemplate="%{text:.0f}",
                            textfont={"size": 11, "color": APPLE_COLORS['dark']},
                            hovertemplate="资产: %{y}<br>战法: %{x}<br>推荐: %{z}<extra></extra>",
                        ))
                        fig.update_layout(**get_apple_chart_layout(
                            title="资产池战法推荐热力图",
                            # 适当降低单行高度，避免整体图像过高导致显示不全
                            height=max(380, len(heatmap_data) * 30),
                            xaxis_title="战法策略",
                            yaxis_title="资产",
                        ))
                        fig.update_layout(margin=dict(l=150, r=50, t=60, b=50))
                        st.plotly_chart(fig, width='stretch', key="chart_heatmap")
                    
                    # 使用汇总数据用于后续建仓计划
                    agg = pd.DataFrame({
                        "ticker": eval_matrix.index,
                        "last_close": [price_map.get(t, 0.0) for t in eval_matrix.index],
                        "selectors": ["、".join([alias for alias in selector_aliases if eval_matrix.loc[t, alias] > 0]) for t in eval_matrix.index],
                        "score": eval_matrix["综合得分"].values,
                    })
                
            else:
                # 全市场扫描模式：原有展示逻辑
                st.markdown("#### 选股结果")

                # 展示明细表：每行一只股票 + 一个战法
                display_df = result_df.copy()
                display_df = display_df.rename(
                    columns={
                        "ticker": "代码",
                        "name": "名称",
                        "selector_alias": "战法",
                        "trade_date": "信号日期",
                        "last_close": "收盘价",
                    }
                )
                display_df["信号日期"] = pd.to_datetime(display_df["信号日期"]).dt.strftime(
                    "%Y-%m-%d"
                )
                display_df["收盘价"] = display_df["收盘价"].map(lambda x: f"{x:,.2f}")

                st.dataframe(
                    display_df[["代码", "名称", "战法", "信号日期", "收盘价"]],
                    hide_index=True,
                    width="stretch",
                )

                # 按代码聚合，用于生成建仓计划：score = 被多少个战法同时选中
                agg = (
                    result_df.groupby("ticker")
                    .agg(
                        last_close=("last_close", "last"),
                        selectors=("selector_alias", lambda xs: "、".join(sorted(set(xs)))),
                        score=("selector_class", "nunique"),
                    )
                    .reset_index()
                )

                st.markdown("#### 按股票汇总的战法信号")
                agg_display = agg.copy()
                agg_display.insert(
                    1,
                    "名称",
                    [ticker_names.get(t, t) for t in agg_display["ticker"]],
                )
                agg_display = agg_display.rename(
                    columns={
                        "ticker": "代码",
                        "last_close": "收盘价",
                        "selectors": "触发战法",
                        "score": "信号得分",
                    }
                )
                agg_display["收盘价"] = agg_display["收盘价"].map(lambda x: f"{x:,.2f}")

                st.dataframe(
                    agg_display[["代码", "名称", "收盘价", "触发战法", "信号得分"]],
                    hide_index=True,
                    width="stretch",
                )

                # 构造统一的 signal_table，复用等权建仓与调仓逻辑
                signal_table = pd.DataFrame(
                    {
                        "ticker": agg["ticker"],
                        "last_price": agg["last_close"],
                        "combined_signal": agg["score"].astype(float),
                        # Z 战法选出即视为"买入候选"
                        "action": ["买入"] * len(agg),
                    }
                )

                st.markdown("---")
                st.markdown("#### 基于战法选股的等权建仓计划")
                st.caption(
                    "以下建仓计划仅用于模拟账户的等权配置示例："
                    "将资金在所有战法选出的标的之间等权分配，按价格计算买入股数。"
                )

                from core.paper_trading import generate_equal_weight_plan

                plan_col1, plan_col2 = st.columns(2)
                with plan_col1:
                    z_sim_capital = st.number_input(
                        "模拟总资金（单位：元）",
                        min_value=10_000.0,
                        max_value=10_000_000.0,
                        value=100_000.0,
                        step=10_000.0,
                        key="z_select_sim_capital",
                    )
                with plan_col2:
                    z_max_positions = st.slider(
                        "最多持仓数量",
                        min_value=1,
                        max_value=20,
                        value=min(5, len(agg)),
                        key="z_select_max_positions",
                    )

                plan_df = generate_equal_weight_plan(
                    signal_table,
                    total_capital=z_sim_capital,
                    max_positions=z_max_positions,
                )

                if plan_df is None or plan_df.empty:
                    st.info(
                        "当前没有可用于等权建仓的候选，或资金/价格不足以买入整股/份额，暂无法生成建仓计划。"
                    )
                else:
                    plan_show = plan_df.copy()
                    plan_show.insert(
                        0,
                        "资产",
                        [ticker_names.get(t, t) for t in plan_show["ticker"]],
                    )
                    plan_show["价格"] = plan_show["last_price"].map(
                        lambda x: f"{x:,.2f}"
                    )
                    plan_show["建仓金额"] = plan_show["notional"].map(
                        lambda x: f"{x:,.2f}"
                    )
                    plan_show = plan_show[
                        [
                            "资产",
                            "ticker",
                            "action",
                            "价格",
                            "shares",
                            "建仓金额",
                            "combined_signal",
                        ]
                    ]

                    st.dataframe(
                        plan_show,
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "资产": st.column_config.TextColumn("资产"),
                            "ticker": st.column_config.TextColumn("代码"),
                            "action": st.column_config.TextColumn("方向"),
                            "价格": st.column_config.TextColumn("价格"),
                            "shares": st.column_config.NumberColumn(
                                "数量", help="模拟买入股数/份额"
                            ),
                            "建仓金额": st.column_config.TextColumn("建仓金额"),
                            "combined_signal": st.column_config.NumberColumn(
                                "信号得分", format="%.0f", help="被多少个战法同时选中"
                            ),
                        },
                    )

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(
                        "应用为当日调仓指令（基于战法选股）",
                        key="apply_z_select_plan_to_paper",
                    ):
                        from core.account import ensure_account_dict
                        from core.trading_engine import apply_equal_weight_rebalance

                        st.session_state.paper_account = ensure_account_dict(
                            st.session_state.get("paper_account"),
                            initial_capital=1_000_000.0,
                        )
                        account = st.session_state.paper_account

                        account, msg = apply_equal_weight_rebalance(
                            account=account,
                            signal_table=signal_table,
                            data=data,
                            total_capital=z_sim_capital,
                            max_positions=z_max_positions,
                        )
                        st.session_state.paper_account = account
                        save_paper_account = _get_save_paper_account()
                        save_paper_account()

                        if "未执行" in msg or "暂无" in msg:
                            st.warning(msg)
                        else:
                            st.success(
                                f"模拟账户已基于战法选股完成调仓：{msg} 可前往'模拟账户'页查看持仓与权益曲线。"
                            )


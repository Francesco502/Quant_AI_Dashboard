"""
资产池管理页面模块
"""
import streamlit as st
import pandas as pd
from core.page_utils import get_ticker_names, get_selected_tickers
from core.app_utils import save_user_state


def render_asset_pool_page(default_universe, ticker_names):
    """渲染资产池管理页面"""
    st.markdown("### 资产池管理")
    st.caption("集中管理默认资产与自定义资产，并选择哪些资产参与后续分析。")
    
    # 构建资产池表格
    pool_records = []
    for t in default_universe:
        pool_records.append({
            "代码": t,
            "名称": ticker_names.get(t, t),
            "类别": "Default",
            "来源": "Auto",
            "是否选中": t in st.session_state.selected_tickers,
        })
    for a in st.session_state.custom_assets:
        t = a["ticker"]
        pool_records.append({
            "代码": t,
            "名称": a.get("name") or t,
            "类别": a.get("category") or "Custom",
            "来源": "Auto",
            "是否选中": t in st.session_state.selected_tickers,
        })
    
    df_pool = pd.DataFrame(pool_records) if pool_records else pd.DataFrame(
        columns=["代码", "名称", "类别", "来源", "是否选中"]
    )
    
    edited = st.data_editor(
        df_pool,
        hide_index=True,
        width="stretch",
        column_config={
            "代码": st.column_config.TextColumn("代码", help="资产代码，如 AAPL、600519.SS、0700.HK、BTC-USD 等"),
            "名称": st.column_config.TextColumn("名称", help="展示名称，可编辑"),
            "类别": st.column_config.TextColumn("类别", help="资产分类标签，仅用于说明"),
            "来源": st.column_config.TextColumn("来源", help="当前数据源自动识别"),
            "是否选中": st.column_config.CheckboxColumn("是否选中"),
        },
    )
    
    # 根据编辑结果更新名称与选中资产
    if not edited.empty:
        # 更新默认与自定义资产名称
        for _, row in edited.iterrows():
            code = row["代码"]
            name = (row["名称"] or "").strip()
            category = row.get("类别", None)

            # 自定义资产：直接写回 custom_assets
            updated_custom = False
            for a in st.session_state.custom_assets:
                if a["ticker"] == code:
                    a["name"] = name or a.get("name") or code
                    if category:
                        a["category"] = category
                    updated_custom = True
                    break

            # 默认资产或非 custom 资产：写入 user_ticker_names 覆盖
            if not updated_custom and name:
                st.session_state.user_ticker_names[code] = name

        # 更新选中资产列表
        new_selected = edited[edited["是否选中"] == True]["代码"].tolist()
        if new_selected != st.session_state.selected_tickers:
            st.session_state.selected_tickers = new_selected
            st.info("资产选择已更新，将在下一次分析刷新时生效（例如切换标签页或调整参数）。")

        # 持久化所有更改
        save_user_state()
    
    st.markdown("#### 添加自定义资产")
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        new_ticker = st.text_input(
            "资产代码",
            placeholder="如：600519.SS, 0700.HK, MSFT, BTC-USD, 159755.SZ",
            key="pool_new_ticker",
        )
    with col_t2:
        new_category = st.selectbox(
            "资产类型（可选）",
            ["Auto detect", "A股 / 基金", "港股", "美股", "加密货币", "其他"],
            index=0,
            key="pool_new_category",
        )
    new_name = st.text_input(
        "显示名称（可选）",
        placeholder="用于在图表和表格中展示的名字，例如：贵州茅台、Tencent、MSFT 等",
        key="pool_new_name",
    )
    
    col_add, col_clear = st.columns([1, 1])
    with col_add:
        if st.button("添加到资产池", key="pool_add_btn"):
            if new_ticker.strip():
                t = new_ticker.strip()
                n = new_name.strip() if new_name.strip() else t
                c = new_category
                existing = [a for a in st.session_state.custom_assets if a["ticker"] == t]
                if existing:
                    for a in st.session_state.custom_assets:
                        if a["ticker"] == t:
                            a["name"] = n
                            a["category"] = c
                else:
                    st.session_state.custom_assets.append({"ticker": t, "name": n, "category": c})
                st.success(f"已添加/更新资产：{t} - {n}")
                save_user_state()
            else:
                st.warning("请输入资产代码后再添加。")
    with col_clear:
        if st.button("清空自定义资产", key="pool_clear_btn"):
            custom_codes = [a["ticker"] for a in st.session_state.custom_assets]
            st.session_state.custom_assets = []
            st.session_state.user_ticker_names = {
                k: v
                for k, v in st.session_state.user_ticker_names.items()
                if k not in custom_codes
            }
            st.success("已清空自定义资产池。")
            save_user_state()
    
    # 提供删除自定义资产的入口（只对自定义资产生效）
    custom_codes = [a["ticker"] for a in st.session_state.custom_assets]
    if custom_codes:
        st.markdown("#### 删除自定义资产")
        st.caption("此处只删除你自行添加的自定义资产，不影响系统内置的默认资产。")
        codes_to_delete = st.multiselect(
            "选择要删除的自定义资产",
            options=custom_codes,
            help="删除后，这些资产将从资产池中移除，并不再出现在后续分析中。"
        )
        if st.button("删除选中的自定义资产", key="pool_delete_btn"):
            if codes_to_delete:
                # 从自定义资产池中移除
                st.session_state.custom_assets = [
                    a for a in st.session_state.custom_assets
                    if a["ticker"] not in codes_to_delete
                ]
                # 同时清理这些资产的名称覆盖
                st.session_state.user_ticker_names = {
                    k: v
                    for k, v in st.session_state.user_ticker_names.items()
                    if k not in codes_to_delete
                }
                # 如果这些资产当前被选中，用于分析的列表中也一并移除
                if "selected_tickers" in st.session_state:
                    st.session_state.selected_tickers = [
                        t for t in st.session_state.selected_tickers
                        if t not in codes_to_delete
                    ]
                save_user_state()
                st.success(f"已删除自定义资产：{', '.join(codes_to_delete)}")

    # ===== 合并的本地数据仓库监控（放在页面最下方） =====
    st.markdown("---")
    st.markdown("### 本地数据仓库监控")
    
    # 第一部分：整体数据仓库统计
    # 延迟导入避免循环导入
    from app import render_data_warehouse_monitor
    render_data_warehouse_monitor()
    
    # 第二部分：当前选中资产的缓存情况
    st.markdown("---")
    st.markdown("#### 当前选中资产的缓存状态")
    st.caption("查看当前选中资产在本地 Parquet 仓库中的缓存情况，包括市场类型、覆盖区间与最后更新时间。")

    from core.data_store import get_local_status_for_tickers
    tickers = get_selected_tickers()

    if not tickers:
        st.info("当前没有选中的资产，请在上方表格中勾选至少一个资产。")
    else:
        status_df = get_local_status_for_tickers(tickers)
        if status_df.empty:
            st.info("本地数据仓库中尚无任何缓存记录。可以通过侧边栏「更新本地数据仓库」按钮初始化缓存。")
        else:
            status_df = status_df.rename(
                columns={
                    "ticker": "代码",
                    "market": "市场",
                    "exists": "已缓存",
                    "coverage_days": "覆盖天数",
                    "start_date": "起始日期",
                    "end_date": "结束日期",
                    "last_modified": "最后更新时间",
                }
            )
            st.dataframe(
                status_df,
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "说明：当你点击「更新本地数据仓库」或系统自动更新时，新的日线数据会被追加并覆盖到本地 Parquet 文件中。"
            )


"""
页面工具函数
供各个页面模块共享使用的工具函数
"""
import streamlit as st
import pandas as pd
from typing import List, Dict


def get_ticker_names() -> Dict[str, str]:
    """获取资产名称映射"""
    # 优先使用主函数中合并后的 ticker_names
    if "ticker_names" in st.session_state:
        return st.session_state.ticker_names
    return st.session_state.get("user_ticker_names", {})


def get_selected_tickers() -> List[str]:
    """获取当前选中的资产列表"""
    # 优先使用主函数中处理后的 tickers（已过滤掉无数据的资产）
    if "tickers" in st.session_state:
        return st.session_state.tickers
    return st.session_state.get("selected_tickers", [])


def get_data() -> pd.DataFrame:
    """获取当前数据"""
    return st.session_state.get("data", pd.DataFrame())


def get_days() -> int:
    """获取历史回看天数"""
    return st.session_state.get("days", 252)


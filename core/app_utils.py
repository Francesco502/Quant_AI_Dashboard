"""
应用工具函数
从app.py中提取的共享函数，避免循环导入
"""
import streamlit as st
import json
import os
import pandas as pd
from pathlib import Path

USER_STATE_FILE = os.path.join(".streamlit", "user_state.json")


def save_user_state():
    """将关键用户配置持久化到本地文件（包括数据源与 API 密钥）"""
    try:
        state_to_save = {
            "selected_tickers": st.session_state.get("selected_tickers", []),
            "custom_assets": st.session_state.get("custom_assets", []),
            "data_sources": st.session_state.get("data_sources", []),
            "user_ticker_names": st.session_state.get("user_ticker_names", {}),
            # API 密钥：为方便本机长期使用，允许写入本地 user_state.json（请勿提交到公共仓库）
            "alpha_vantage_key": st.session_state.get("alpha_vantage_key", ""),
            "tushare_token": st.session_state.get("tushare_token", ""),
        }
        os.makedirs(os.path.dirname(USER_STATE_FILE), exist_ok=True)
        with open(USER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存用户状态失败: {e}")


def save_selector_results(result_df: pd.DataFrame, trade_date: str) -> bool:
    """保存选股结果到本地文件"""
    try:
        from core.data_store import BASE_DIR
        
        base_path = Path(BASE_DIR)
        signals_dir = base_path / "signals" / "z_selectors"
        signals_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用交易日期作为文件名
        date_str = pd.to_datetime(trade_date).strftime("%Y-%m-%d")
        file_path = signals_dir / f"{date_str}.csv"
        
        # 保存为CSV
        result_df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        return True
    except Exception as e:
        print(f"保存选股结果失败: {e}")
        return False


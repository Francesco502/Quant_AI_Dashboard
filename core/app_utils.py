"""
应用工具函数
提供通用的数据存储和文件操作工具
"""
import json
import os
import pandas as pd
from pathlib import Path


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

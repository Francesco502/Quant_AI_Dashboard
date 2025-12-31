"""
信号存储模块（阶段一：基础设施升级）

职责：
- 预测结果持久化
- 支持信号回溯和执行追踪
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from .data_store import BASE_DIR

SIGNALS_DIR = os.path.join(BASE_DIR, "signals")


def _ensure_dirs() -> None:
    """确保信号目录存在"""
    os.makedirs(SIGNALS_DIR, exist_ok=True)


def get_signal_file_path(date: str) -> str:
    """
    获取某日期的信号文件路径
    
    参数:
        date: 日期字符串（YYYY-MM-DD）
        
    返回:
        文件路径
    """
    _ensure_dirs()
    return os.path.join(SIGNALS_DIR, f"{date}.parquet")


def get_today_signal_file() -> str:
    """获取今天的信号文件路径"""
    today = datetime.now().strftime("%Y-%m-%d")
    return get_signal_file_path(today)


class SignalStore:
    """信号存储管理器"""

    def save_signal(
        self,
        ticker: str,
        prediction: float,
        direction: int,
        confidence: float,
        signal: str,
        model_id: str,
        target_weight: Optional[float] = None,
        status: str = "pending",
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        保存单个信号
        
        参数:
            ticker: 标的代码
            prediction: 预测收益率
            direction: 方向（1=看涨, -1=看跌, 0=中性）
            confidence: 置信度（0-1）
            signal: 交易信号（buy/sell/hold）
            model_id: 模型ID
            target_weight: 建议仓位权重
            status: 状态（pending/executed/expired）
            timestamp: 时间戳（默认当前时间）
            
        返回:
            是否成功
        """
        if timestamp is None:
            timestamp = datetime.now()

        signal_data = {
            "timestamp": timestamp,
            "ticker": ticker,
            "model_id": model_id,
            "prediction": prediction,
            "direction": direction,
            "confidence": confidence,
            "signal": signal,
            "target_weight": target_weight if target_weight is not None else 0.0,
            "status": status,
        }

        date_str = timestamp.strftime("%Y-%m-%d")
        file_path = get_signal_file_path(date_str)

        try:
            _ensure_dirs()

            # 如果文件已存在，读取并追加
            if os.path.exists(file_path):
                df = pd.read_parquet(file_path)
                # 检查是否已存在相同ticker和model_id的信号（更新而非重复）
                mask = (df["ticker"] == ticker) & (df["model_id"] == model_id)
                if mask.any():
                    df.loc[mask, list(signal_data.keys())] = list(signal_data.values())
                else:
                    df = pd.concat([df, pd.DataFrame([signal_data])], ignore_index=True)
            else:
                df = pd.DataFrame([signal_data])

            df.to_parquet(file_path, index=False)
            return True
        except Exception as e:
            print(f"保存信号失败 ({ticker}): {e}")
            return False

    def load_signals(
        self,
        date: Optional[str] = None,
        ticker: Optional[str] = None,
        model_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        加载信号
        
        参数:
            date: 日期（YYYY-MM-DD），None则加载今天
            ticker: 标的代码过滤
            model_id: 模型ID过滤
            status: 状态过滤
            
        返回:
            信号DataFrame
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        file_path = get_signal_file_path(date)
        if not os.path.exists(file_path):
            return pd.DataFrame()

        try:
            df = pd.read_parquet(file_path)
            if df.empty:
                return df

            # 过滤
            if ticker:
                df = df[df["ticker"] == ticker]
            if model_id:
                df = df[df["model_id"] == model_id]
            if status:
                df = df[df["status"] == status]

            return df
        except Exception as e:
            print(f"加载信号失败 ({date}): {e}")
            return pd.DataFrame()

    def update_signal_status(
        self, ticker: str, model_id: str, date: str, new_status: str
    ) -> bool:
        """
        更新信号状态
        
        参数:
            ticker: 标的代码
            model_id: 模型ID
            date: 日期
            new_status: 新状态
            
        返回:
            是否成功
        """
        file_path = get_signal_file_path(date)
        if not os.path.exists(file_path):
            return False

        try:
            df = pd.read_parquet(file_path)
            mask = (df["ticker"] == ticker) & (df["model_id"] == model_id)
            if mask.any():
                df.loc[mask, "status"] = new_status
                df.to_parquet(file_path, index=False)
                return True
            return False
        except Exception as e:
            print(f"更新信号状态失败: {e}")
            return False

    def get_latest_signals(
        self, ticker: Optional[str] = None, n_days: int = 7
    ) -> pd.DataFrame:
        """
        获取最近N天的信号
        
        参数:
            ticker: 标的代码过滤
            n_days: 天数
            
        返回:
            信号DataFrame
        """
        all_signals = []
        today = datetime.now()

        for i in range(n_days):
            date = (today - pd.Timedelta(days=i)).strftime("%Y-%m-%d")
            signals = self.load_signals(date=date, ticker=ticker)
            if not signals.empty:
                all_signals.append(signals)

        if not all_signals:
            return pd.DataFrame()

        return pd.concat(all_signals, ignore_index=True).sort_values(
            "timestamp", ascending=False
        )


# 全局单例
_signal_store_instance: Optional[SignalStore] = None


def get_signal_store() -> SignalStore:
    """获取信号存储单例"""
    global _signal_store_instance
    if _signal_store_instance is None:
        _signal_store_instance = SignalStore()
    return _signal_store_instance


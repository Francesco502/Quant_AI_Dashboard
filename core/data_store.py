"""本地数据仓库模块（阶段 2）

职责：
- 负责本地日线价格数据的读写与维护；
- 当前实现：按 ticker 维度存储到 Parquet 文件；
- 目录按市场划分：A股（包含股票和基金）/ 港股 / 美股 / 黄金/贵金属 / 加密货币 / 其他；
- 注意：基金代码（6位数字）统一归类到"A股"目录，不会创建单独的"基金"目录；
- 后续可以替换为 SQLite / DuckDB，而不影响上层接口。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Dict, List

import pandas as pd


BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# 统一的 OHLCV 列名约定
OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def classify_market(ticker: str) -> str:
    """根据代码简单判断市场类型，用于目录划分"""
    t = ticker.upper()
    # A股（股票/基金统一归入 A股 目录，细分交由上层或其他工具处理）
    if t.endswith(".SZ") or t.endswith(".SS") or (t.isdigit() and len(t) == 6):
        return "A股"
    # 港股
    if t.endswith(".HK") or t in {"HSI"}:
        return "港股"
    # 加密货币
    if t.endswith("-USD") or t.endswith("USDT"):
        return "加密货币"
    # 黄金 / 贵金属
    if "XAU" in t or "XAG" in t or "GOLD" in t:
        return "黄金/贵金属"
    # 美股（粗略判断：纯字母且长度<=5）
    if t.isalpha() and 1 <= len(t) <= 5:
        return "美股"
    return "其他"


def get_price_file_path(ticker: str) -> str:
    """获取某个标的在本地仓库中的 Parquet 路径（按市场分目录）"""
    safe_ticker = ticker.replace("/", "_").replace("\\", "_").replace(":", "_")
    market = classify_market(ticker)
    # 安全措施：确保不会创建"基金"目录，统一归类到"A股"
    if market == "基金":
        market = "A股"
    prices_dir = os.path.join(BASE_DIR, "prices", market)
    _ensure_dir(prices_dir)
    return os.path.join(prices_dir, f"{safe_ticker}.parquet")


def load_local_price_history(ticker: str) -> Optional[pd.Series]:
    """加载本地存储的某标的完整日线价格历史（若不存在返回 None）"""
    path = get_price_file_path(ticker)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_parquet(path)
        if df.empty:
            return None
        # 优先选用 close/price 列，兼容老版本仅单列 price 的情况
        if "close" in df.columns:
            series = df["close"]
        elif "price" in df.columns:
            series = df["price"]
        else:
            # 兼容未来可能的多列结构，这里默认取第一列
            series = df.iloc[:, 0]
        if not isinstance(series.index, pd.DatetimeIndex):
            series.index = pd.to_datetime(series.index)
        return series.sort_index()
    except Exception:
        return None


def save_local_price_history(ticker: str, series: pd.Series) -> None:
    """将某标的完整价格历史写入本地 Parquet（覆盖式保存）"""
    if series is None or series.empty:
        return
    path = get_price_file_path(ticker)
    # 使用 close 列保存，便于与 OHLCV 结构对齐
    df = pd.DataFrame({"close": series})
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df.to_parquet(path)


def load_local_ohlcv_history(ticker: str) -> Optional[pd.DataFrame]:
    """
    加载本地存储的某标的完整 OHLCV 历史（若不存在或结构不足则返回 None）

    兼容行为：
    - 如果文件中只有单列 close/price，则构造简化版 OHLCV（open/high/low=close, volume=NaN）。
    """
    path = get_price_file_path(ticker)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_parquet(path)
        if df.empty:
            return None
        # 已包含标准 OHLC 结构
        if any(col in df.columns for col in ("open", "high", "low", "close")):
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            # 确保列顺序以 OHLCV 为主，其他列保留在后
            cols = [c for c in OHLCV_COLUMNS if c in df.columns] + [
                c for c in df.columns if c not in OHLCV_COLUMNS
            ]
            return df[cols]
        # 仅有 price/close 等单列时，构造简化 OHLCV
        if "close" in df.columns:
            close = df["close"]
        elif "price" in df.columns:
            close = df["price"]
        else:
            close = df.iloc[:, 0]
        if not isinstance(close.index, pd.DatetimeIndex):
            close.index = pd.to_datetime(close.index)
        close = close.sort_index()
        ohlcv = pd.DataFrame(index=close.index)
        ohlcv["open"] = close
        ohlcv["high"] = close
        ohlcv["low"] = close
        ohlcv["close"] = close
        ohlcv["volume"] = pd.NA
        return ohlcv
    except Exception:
        return None


def save_local_ohlcv_history(ticker: str, df: pd.DataFrame) -> None:
    """
    将某标的完整 OHLCV 历史写入本地 Parquet（覆盖式保存）

    要求：
    - index 为日期索引；
    - 至少包含 close 列，其余列缺失时可选。
    """
    if df is None or df.empty:
        return
    path = get_price_file_path(ticker)
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    out.to_parquet(path)


def migrate_price_to_ohlcv_if_needed(ticker: str) -> None:
    """
    迁移单个标的：如本地仅存在 price/close 单列，则按
    open=high=low=close, volume=NaN 的规则覆盖为 OHLCV 结构。

    - 已经是 OHLCV 的文件不会受影响；
    - 为了避免意外开销，仅在需要时调用（例如后台数据更新脚本里）。
    """
    path = get_price_file_path(ticker)
    if not os.path.exists(path):
        return
    try:
        df = pd.read_parquet(path)
        if df.empty:
            return
        # 已经有标准 OHLCV 列时不做处理
        if any(c in df.columns for c in ["open", "high", "low", "close"]):
            return

        # 从单列 price/close 或第一列构造 OHLCV
        if "close" in df.columns:
            close = df["close"]
        elif "price" in df.columns:
            close = df["price"]
        else:
            close = df.iloc[:, 0]

        if not isinstance(close.index, pd.DatetimeIndex):
            close.index = pd.to_datetime(close.index)
        close = close.sort_index()

        ohlcv = pd.DataFrame(index=close.index)
        ohlcv["open"] = close
        ohlcv["high"] = close
        ohlcv["low"] = close
        ohlcv["close"] = close
        ohlcv["volume"] = pd.NA

        save_local_ohlcv_history(ticker, ohlcv)
    except Exception:
        # 迁移失败时静默跳过，避免影响主流程
        return


def get_local_coverage_days(ticker: str) -> int:
    """返回本地该标的历史覆盖天数（用于调试/监控）"""
    series = load_local_price_history(ticker)
    if series is None or series.empty:
        return 0
    return (series.index.max() - series.index.min()).days + 1


def get_local_status_for_ticker(ticker: str) -> Dict[str, object]:
    """返回单个 ticker 的本地仓状态（用于监控界面）"""
    market = classify_market(ticker)
    path = get_price_file_path(ticker)
    exists = os.path.exists(path)
    status: Dict[str, object] = {
        "ticker": ticker,
        "market": market,
        "exists": exists,
        "coverage_days": 0,
        "start_date": None,
        "end_date": None,
        "last_modified": None,
    }
    if not exists:
        return status

    series = load_local_price_history(ticker)
    if series is None or series.empty:
        return status

    start = series.index.min()
    end = series.index.max()
    status["coverage_days"] = (end - start).days + 1
    status["start_date"] = start.strftime("%Y-%m-%d")
    status["end_date"] = end.strftime("%Y-%m-%d")

    try:
        mtime = os.path.getmtime(path)
        status["last_modified"] = datetime.fromtimestamp(mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except Exception:
        status["last_modified"] = None

    return status


def get_local_status_for_tickers(tickers: List[str]) -> pd.DataFrame:
    """批量获取多个 ticker 的本地仓状态"""
    records = [get_local_status_for_ticker(t) for t in tickers]
    if not records:
        return pd.DataFrame(
            columns=[
                "ticker",
                "market",
                "exists",
                "coverage_days",
                "start_date",
                "end_date",
                "last_modified",
            ]
        )
    return pd.DataFrame(records)




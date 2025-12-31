"""本地数据更新模块（阶段 2）

职责：
- 负责根据当前请求的标的列表，使用远程数据源增量更新本地 Parquet 仓库；
- 当前通过函数调用触发，后续可以接入定时任务/独立进程。
"""

from __future__ import annotations

from datetime import datetime
from typing import List

import pandas as pd

from .data_service import _load_price_data_remote
from .data_store import load_local_price_history, save_local_price_history

# 为本地仓库设计的“最大缓存窗口”（与前端历史回看上限保持一致：约 10 年）
MAX_CACHE_DAYS = 3650
MIN_CACHE_DAYS = 60


def update_local_history_for_tickers(
    tickers: List[str],
    days: int,
    data_sources: List[str],
    alpha_vantage_key: str | None = None,
    tushare_token: str | None = None,
) -> None:
    """为给定标的列表更新本地历史数据到最新

    简化逻辑：
    - 读取本地已有数据，取其最早日期 `local_start` 与最晚日期 `local_end`；
    - 计算需要的整体时间窗口：`lookback_days = max(days, (today - local_start).days+1)`；
    - 调用远程 load_price_data_remote 获取这一窗口的完整历史（可能覆盖本地已有部分）；
    - 将远程结果覆盖式写入本地（后续可以改为严格增量）。
    """
    if not tickers:
        return

    # 计算窗口长度：尽量覆盖已有 + 新增，且至少为 MAX_CACHE_DAYS
    max_existing_span = 0
    for t in tickers:
        local_series = load_local_price_history(t)
        if local_series is not None and not local_series.empty:
            span = (local_series.index.max().date() - local_series.index.min().date()).days + 1
            if span > max_existing_span:
                max_existing_span = span

    # 始终至少缓存 MAX_CACHE_DAYS，这样即使用户当前只看 60 天，本地仍保留最长窗口
    lookback_days = max(days, max_existing_span, MIN_CACHE_DAYS, MAX_CACHE_DAYS)

    # 注意：这里必须调用“远程专用”的加载函数，不能走本地优先的 load_price_data，
    # 否则当本地已存在部分数据时将无法扩展历史窗口。
    remote_df = _load_price_data_remote(
        tickers=tickers,
        days=lookback_days,
        data_sources=data_sources,
        alpha_vantage_key=alpha_vantage_key,
        tushare_token=tushare_token,
    )
    if remote_df is None or remote_df.empty:
        return

    # 将远程数据写回本地仓库
    for t in tickers:
        if t in remote_df.columns:
            series = remote_df[t].dropna()
            if not series.empty:
                save_local_price_history(t, series)



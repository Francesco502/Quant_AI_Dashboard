"""LLM 决策存储模块（Phase 3）

职责：
- 将每日 LLM 决策结果落盘，便于后续 AI 回测；
- 按 ticker 维度存储到 Parquet 文件；
- 字段：ticker, date, conclusion, action, buy_price, stop_loss, target_price, score, created_at。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import os

import pandas as pd

from core.data_store import BASE_DIR, _ensure_dir  # type: ignore[attr-defined]


DECISIONS_DIR = os.path.join(BASE_DIR, "decisions")


def _get_ticker_path(ticker: str) -> str:
    safe = ticker.replace("/", "_").replace("\\", "_").replace(":", "_")
    _ensure_dir(DECISIONS_DIR)
    return os.path.join(DECISIONS_DIR, f"{safe}.parquet")


def append_decisions(ticker: str, rows: List[Dict[str, Any]]) -> None:
    """将若干决策记录追加到指定 ticker 的决策文件中"""
    if not rows:
        return
    path = _get_ticker_path(ticker)
    new_df = pd.DataFrame(rows)
    if not new_df.empty and "date" in new_df.columns:
        new_df["date"] = pd.to_datetime(new_df["date"])
    if os.path.exists(path):
        try:
            old_df = pd.read_parquet(path)
        except Exception:
            old_df = pd.DataFrame()
        if not old_df.empty:
            if "date" in old_df.columns:
                old_df["date"] = pd.to_datetime(old_df["date"])
            merged = pd.concat([old_df, new_df], ignore_index=True)
            # 按 date+ticker 去重（若 ticker 列存在），否则按 date 去重
            subset = ["date", "ticker"] if "ticker" in merged.columns else ["date"]
            merged = merged.drop_duplicates(subset=subset, keep="last")
            merged = merged.sort_values("date")
            merged.to_parquet(path, index=False)
            return
    # 无旧数据
    new_df = new_df.sort_values("date") if "date" in new_df.columns else new_df
    new_df.to_parquet(path, index=False)


def save_daily_decisions(result: Dict[str, Any]) -> None:
    """将 run_daily_analysis 的结果保存到本地

    result 预期结构：
        {
          "results": [
            {
               "ticker": ...,
               "name": ...,
               "decision": {...},
               "meta": {...}
            },
            ...
          ],
          "summary": {...},
          ...
        }
    """
    results = result.get("results") or []
    if not results:
        return

    today = datetime.now().date().isoformat()
    created_at = datetime.now().isoformat()

    for r in results:
        ticker = r.get("ticker")
        if not ticker:
            continue
        d = r.get("decision") or {}
        row = {
            "ticker": ticker,
            "date": today,
            "conclusion": d.get("conclusion"),
            "action": d.get("action"),
            "buy_price": d.get("buy_price"),
            "stop_loss": d.get("stop_loss"),
            "target_price": d.get("target_price"),
            "score": d.get("score"),
            "created_at": created_at,
        }
        append_decisions(ticker, [row])


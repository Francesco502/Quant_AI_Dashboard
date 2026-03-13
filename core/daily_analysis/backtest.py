"""LLM 决策回测模块（Phase 3）

基于历史决策记录与后 N 日价格走势，计算方向胜率、止盈/止损命中率等指标。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import os

import pandas as pd

from core.data_store import load_local_price_history  # type: ignore[attr-defined]
from core.data_store import BASE_DIR, _ensure_dir  # type: ignore[attr-defined]


DECISIONS_DIR = os.path.join(BASE_DIR, "decisions")


@dataclass
class DecisionRecord:
    ticker: str
    date: datetime
    action: Optional[str]
    buy_price: Optional[float]
    stop_loss: Optional[float]
    target_price: Optional[float]
    score: Optional[float]


def _get_ticker_path(ticker: str) -> str:
    safe = ticker.replace("/", "_").replace("\\", "_").replace(":", "_")
    _ensure_dir(DECISIONS_DIR)
    return os.path.join(DECISIONS_DIR, f"{safe}.parquet")


def load_decisions(ticker: str) -> List[DecisionRecord]:
    """从本地决策文件加载指定 ticker 的所有决策记录"""
    path = _get_ticker_path(ticker)
    if not os.path.exists(path):
        return []
    try:
        df = pd.read_parquet(path)
    except Exception:
        return []
    if df.empty or "date" not in df.columns:
        return []
    df["date"] = pd.to_datetime(df["date"])
    records: List[DecisionRecord] = []
    for _, row in df.iterrows():
        records.append(
            DecisionRecord(
                ticker=str(row.get("ticker") or ticker),
                date=row["date"].to_pydatetime(),
                action=row.get("action"),
                buy_price=_to_float(row.get("buy_price")),
                stop_loss=_to_float(row.get("stop_loss")),
                target_price=_to_float(row.get("target_price")),
                score=_to_float(row.get("score")),
            )
        )
    return records


def _to_float(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _slice_horizon(series: pd.Series, start_date: datetime, horizon_days: int) -> pd.Series:
    """从给定日期起，截取后 N 日价格序列"""
    if not isinstance(series.index, pd.DatetimeIndex):
        series.index = pd.to_datetime(series.index)
    series = series.sort_index()
    mask = series.index >= pd.to_datetime(start_date.date())
    sub = series[mask]
    if sub.empty:
        return sub
    end_date = start_date + timedelta(days=horizon_days)
    return sub[sub.index <= end_date]


def backtest_ticker(ticker: str, horizon_days: int = 5) -> Dict[str, Any]:
    """对单一 ticker 的历史 LLM 决策进行回测"""
    decisions = load_decisions(ticker)
    price_series = load_local_price_history(ticker)
    if not decisions or price_series is None or price_series.empty:
        return {
            "ticker": ticker,
            "metrics": {
                "sample_count": 0,
                "direction_win_rate": None,
                "take_profit_hit_rate": None,
                "stop_loss_hit_rate": None,
            },
            "decisions": [],
        }

    eval_rows: List[Dict[str, Any]] = []
    dir_total = 0
    dir_win = 0
    tp_total = 0
    tp_hit = 0
    sl_total = 0
    sl_hit = 0

    for d in decisions:
        window = _slice_horizon(price_series, d.date, horizon_days)
        if window.empty:
            continue
        p0 = float(window.iloc[0])
        pN = float(window.iloc[-1])
        high = float(window.max())
        low = float(window.min())

        direction_correct = None
        if d.action in ("买入", "卖出"):
            dir_total += 1
            if d.action == "买入":
                direction_correct = pN >= p0
            else:  # 卖出
                direction_correct = pN <= p0
            if direction_correct:
                dir_win += 1

        tp_hit_flag = None
        if d.target_price is not None:
            tp_total += 1
            tp_hit_flag = high >= d.target_price
            if tp_hit_flag:
                tp_hit += 1

        sl_hit_flag = None
        if d.stop_loss is not None:
            sl_total += 1
            sl_hit_flag = low <= d.stop_loss
            if sl_hit_flag:
                sl_hit += 1

        eval_rows.append(
            {
                "date": d.date.date().isoformat(),
                "action": d.action,
                "buy_price": d.buy_price,
                "stop_loss": d.stop_loss,
                "target_price": d.target_price,
                "score": d.score,
                "direction_correct": direction_correct,
                "take_profit_hit": tp_hit_flag,
                "stop_loss_hit": sl_hit_flag,
                "start_price": p0,
                "end_price": pN,
                "horizon_days": horizon_days,
            }
        )

    def rate(hit: int, total: int) -> Optional[float]:
        return hit / total if total > 0 else None

    metrics = {
        "sample_count": len(eval_rows),
        "direction_win_rate": rate(dir_win, dir_total),
        "take_profit_hit_rate": rate(tp_hit, tp_total),
        "stop_loss_hit_rate": rate(sl_hit, sl_total),
    }

    return {"ticker": ticker, "metrics": metrics, "decisions": eval_rows}


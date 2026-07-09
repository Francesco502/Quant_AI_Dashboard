"""Batch-prepared backtest input helpers for v3.0.0."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PreparedBacktestInput:
    price_data: pd.DataFrame
    tickers: tuple[str, ...]
    start_date: str | None
    end_date: str | None


def prepare_backtest_input(price_data: pd.DataFrame) -> PreparedBacktestInput:
    if price_data is None or price_data.empty:
        return PreparedBacktestInput(pd.DataFrame(), (), None, None)
    frame = price_data.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    frame = frame.reindex(sorted(frame.columns), axis=1)
    frame = frame.ffill().bfill()
    return PreparedBacktestInput(
        price_data=frame,
        tickers=tuple(str(c) for c in frame.columns),
        start_date=frame.index.min().date().isoformat(),
        end_date=frame.index.max().date().isoformat(),
    )


def make_parameter_hash(params: dict[str, Any]) -> str:
    payload = json.dumps(params, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def align_benchmark_returns(benchmark_prices: pd.Series, prepared: PreparedBacktestInput) -> pd.Series:
    series = benchmark_prices.copy()
    series.index = pd.to_datetime(series.index)
    returns = series.sort_index().pct_change().fillna(0.0)
    return returns.reindex(prepared.price_data.index).ffill().fillna(0.0)

"""Contracts for batch OHLCV data access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class BatchOHLCVRequest:
    tickers: tuple[str, ...]
    days: int = 365
    refresh_stale: bool = True

    def __init__(self, tickers, days: int = 365, refresh_stale: bool = True):
        if int(days) <= 0:
            raise ValueError("days must be positive")
        normalized = tuple(sorted({str(t).strip().upper() for t in tickers if str(t).strip()}))
        object.__setattr__(self, "tickers", normalized)
        object.__setattr__(self, "days", int(days))
        object.__setattr__(self, "refresh_stale", bool(refresh_stale))


@dataclass(frozen=True)
class FreshnessSummary:
    latest_date: Optional[str] = None
    age_days: Optional[int] = None


@dataclass(frozen=True)
class BatchOHLCVResponse:
    ticker_frames: dict[str, pd.DataFrame]
    missing_tickers: tuple[str, ...] = ()
    cache_hit: bool = False
    source: str = "unknown"
    freshness: FreshnessSummary | None = None

    @property
    def tickers(self) -> tuple[str, ...]:
        return tuple(sorted(self.ticker_frames))

    @property
    def row_count(self) -> int:
        return int(sum(len(frame) for frame in self.ticker_frames.values()))

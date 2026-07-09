"""Local OHLCV lake backed by one pickle/parquet-compatible file per ticker."""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from .contracts import BatchOHLCVRequest, BatchOHLCVResponse, FreshnessSummary


def _safe_ticker(ticker: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", ticker)


class LocalOhlcvLake:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, ticker: str) -> Path:
        return self.root / f"{_safe_ticker(ticker)}.parquet"

    def write_batch(self, frames: dict[str, pd.DataFrame]) -> None:
        for ticker, frame in frames.items():
            if frame is None or frame.empty:
                continue
            out = frame.copy()
            out.index = pd.to_datetime(out.index)
            out = out.sort_index()
            path = self._path(str(ticker).strip().upper())
            path.parent.mkdir(parents=True, exist_ok=True)
            out.to_pickle(path)

    def read_batch(self, request: BatchOHLCVRequest) -> BatchOHLCVResponse:
        frames: dict[str, pd.DataFrame] = {}
        missing: list[str] = []
        latest = None
        for ticker in request.tickers:
            path = self._path(ticker)
            if not path.exists():
                missing.append(ticker)
                continue
            frame = pd.read_pickle(path)
            frame.index = pd.to_datetime(frame.index)
            frame = frame.sort_index()
            if request.days:
                frame = frame.tail(request.days)
            frames[ticker] = frame
            if not frame.empty:
                max_date = frame.index.max().date().isoformat()
                latest = max(latest, max_date) if latest else max_date
        return BatchOHLCVResponse(
            ticker_frames=frames,
            missing_tickers=tuple(missing),
            cache_hit=bool(frames) and not missing,
            source="local_lake",
            freshness=FreshnessSummary(latest_date=latest, age_days=None),
        )

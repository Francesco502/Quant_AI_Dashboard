"""Batch data access facade for local-first OHLCV retrieval."""

from __future__ import annotations

from pathlib import Path

from core.data_store import BASE_DIR

from .contracts import BatchOHLCVRequest, BatchOHLCVResponse
from .local_lake import LocalOhlcvLake


def load_ohlcv_batch(request: BatchOHLCVRequest) -> BatchOHLCVResponse:
    lake = LocalOhlcvLake(Path(BASE_DIR) / "ohlcv_lake")
    return lake.read_batch(request)

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.api_response_cache import get_cached, set_cached


def test_set_cached_serializes_timestamp_and_roundtrips(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("API_RESPONSE_CACHE_ENABLED", "true")
    monkeypatch.setenv("API_CACHE_DIR", str(tmp_path))

    payload = {
        "index": [pd.Timestamp("2026-03-16")],
        "columns": ["close"],
        "data": [[123.45]],
    }

    set_cached("prices", {"ticker": "600519", "days": 30}, payload)
    cached = get_cached("prices", {"ticker": "600519", "days": 30})

    assert cached is not None
    assert cached["index"] == ["2026-03-16T00:00:00"]
    assert cached["columns"] == ["close"]
    assert cached["data"] == [[123.45]]


def test_set_cached_does_not_leave_partial_file_on_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("API_RESPONSE_CACHE_ENABLED", "true")
    monkeypatch.setenv("API_CACHE_DIR", str(tmp_path))

    class BadValue:
        def isoformat(self) -> str:
            raise RuntimeError("boom")

        def __str__(self) -> str:
            return "bad-value"

    payload = {"x": BadValue()}
    set_cached("market_review", {"market": "cn"}, payload)
    cached = get_cached("market_review", {"market": "cn"})

    assert cached == {"x": "bad-value"}

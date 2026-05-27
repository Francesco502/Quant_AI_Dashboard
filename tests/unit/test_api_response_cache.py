from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.api_response_cache import get_cached, prune_cache, set_cached


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


def test_set_cached_uses_unique_temp_files_for_same_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("API_RESPONSE_CACHE_ENABLED", "true")
    monkeypatch.setenv("API_CACHE_DIR", str(tmp_path))

    import core.api_response_cache as cache

    replace_sources: list[Path] = []
    real_replace = cache.os.replace

    def spy_replace(src: Any, dst: Any) -> None:
        replace_sources.append(Path(src))
        real_replace(src, dst)

    monkeypatch.setattr(cache.os, "replace", spy_replace)

    set_cached("prices", {"ticker": "600000", "days": 5}, {"value": 1})
    set_cached("prices", {"ticker": "600000", "days": 5}, {"value": 2})

    assert len(replace_sources) == 2
    assert replace_sources[0] != replace_sources[1]


def test_prune_cache_enforces_max_entries(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("API_RESPONSE_CACHE_ENABLED", "true")
    monkeypatch.setenv("API_CACHE_DIR", str(tmp_path))

    for index in range(5):
        set_cached("prices", {"ticker": f"T{index}", "days": 5}, {"value": index})

    deleted = prune_cache(max_entries=2)

    assert deleted == 3
    assert len(list(tmp_path.rglob("*.json"))) == 2

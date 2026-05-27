"""Tests for atomic local Parquet cache writes."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core import data_store


def test_save_local_price_history_writes_temp_file_before_replace(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(data_store, "BASE_DIR", str(tmp_path))
    write_paths: list[Path] = []
    replace_calls: list[tuple[Path, Path]] = []

    real_to_parquet = pd.DataFrame.to_parquet
    real_replace = data_store.os.replace

    def spy_to_parquet(self, path, *args, **kwargs):
        write_paths.append(Path(path))
        return real_to_parquet(self, path, *args, **kwargs)

    def spy_replace(src, dst):
        replace_calls.append((Path(src), Path(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", spy_to_parquet)
    monkeypatch.setattr(data_store.os, "replace", spy_replace)

    series = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-01-01", "2026-01-02"]))
    data_store.save_local_price_history("600519", series)

    final_path = Path(data_store.get_price_file_path("600519"))
    assert write_paths
    assert write_paths[0] != final_path
    assert write_paths[0].name.startswith(".600519.parquet.")
    assert replace_calls == [(write_paths[0], final_path)]
    assert final_path.exists()

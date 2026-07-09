"""Persistent feature snapshot storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd


def _safe_part(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", str(value or "")).strip("._-")
    return safe or "default"


@dataclass
class FeatureSnapshot:
    frame: pd.DataFrame
    metadata: dict[str, Any]
    data_path: Path
    metadata_path: Path


class FeatureSnapshotStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def paths(self, *, market: str, feature_version: str) -> tuple[Path, Path]:
        directory = self.root / _safe_part(market)
        return directory / f"{_safe_part(feature_version)}.parquet", directory / f"{_safe_part(feature_version)}.json"

    def write(
        self,
        frame: pd.DataFrame,
        *,
        market: str,
        feature_version: str,
        source_price_version: str = "local",
        metadata: dict[str, Any] | None = None,
    ) -> FeatureSnapshot:
        data_path, metadata_path = self.paths(market=market, feature_version=feature_version)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        out = frame.copy()
        if "date" in out.columns:
            out["date"] = pd.to_datetime(out["date"])
        out.to_pickle(data_path)
        as_of_date = None
        if not out.empty and "date" in out.columns:
            as_of_date = pd.to_datetime(out["date"]).max().date().isoformat()
        payload = {
            "market": market,
            "feature_version": feature_version,
            "source_price_version": source_price_version,
            "as_of_date": as_of_date,
            "ticker_count": int(out["ticker"].nunique()) if "ticker" in out.columns else 0,
            "row_count": int(len(out)),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            payload.update(metadata)
        metadata_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        return FeatureSnapshot(frame=out, metadata=payload, data_path=data_path, metadata_path=metadata_path)

    def read(self, *, market: str, feature_version: str) -> FeatureSnapshot | None:
        data_path, metadata_path = self.paths(market=market, feature_version=feature_version)
        if not data_path.exists() or not metadata_path.exists():
            return None
        frame = pd.read_pickle(data_path)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return FeatureSnapshot(frame=frame, metadata=metadata, data_path=data_path, metadata_path=metadata_path)

"""Hot-cache market scanning over prebuilt feature snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd

from core import native_kernel
from core.features.snapshot_store import FeatureSnapshotStore


class FeatureSnapshotMissingError(RuntimeError):
    pass


def build_scan_cache_key(*, market: str, as_of_date: str | None, strategy_config: dict[str, Any]) -> str:
    payload = {"market": market, "as_of_date": as_of_date, "strategy_config": strategy_config or {}}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def scan_feature_rows(
    frame: pd.DataFrame,
    *,
    strategy_config: dict[str, Any],
    market: str,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    df = frame.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    if "market" in df.columns:
        df = df[df["market"].astype(str).str.upper() == str(market).upper()]
    if as_of_date and "date" in df.columns:
        df = df[df["date"] == pd.Timestamp(as_of_date)]
    elif "date" in df.columns and not df.empty:
        df = df[df["date"] == df["date"].max()]
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["score"] = native_kernel.score_feature_rows(df)
    params = (strategy_config or {}).get("params") or {}
    min_score = float(params.get("min_score", 0.0))
    df = df[df["score"] >= min_score]
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    return df


def scan_latest_snapshot(
    *,
    store: FeatureSnapshotStore,
    market: str,
    feature_version: str,
    strategy_config: dict[str, Any],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    snapshot = store.read(market=market, feature_version=feature_version)
    if snapshot is None:
        raise FeatureSnapshotMissingError(f"No feature snapshot found for market={market} feature_version={feature_version}")
    result = scan_feature_rows(
        snapshot.frame,
        strategy_config=strategy_config,
        market=market,
        as_of_date=snapshot.metadata.get("as_of_date"),
    )
    if limit:
        result = result.head(int(limit))
    if "date" in result.columns:
        result = result.copy()
        result["date"] = pd.to_datetime(result["date"]).dt.date.astype(str)
    return result.to_dict(orient="records")

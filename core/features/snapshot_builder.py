"""Build and update v3 feature snapshots from OHLCV frames."""

from __future__ import annotations

import pandas as pd

from .snapshot_store import FeatureSnapshot, FeatureSnapshotStore
from .technical import add_technical_features


def _normalize_input_frames(frames: list[pd.DataFrame] | tuple[pd.DataFrame, ...]) -> pd.DataFrame:
    parts = []
    for frame in frames:
        if frame is None or frame.empty:
            continue
        parts.append(add_technical_features(frame))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def build_feature_snapshot(
    frames: list[pd.DataFrame] | tuple[pd.DataFrame, ...],
    *,
    store: FeatureSnapshotStore,
    market: str,
    feature_version: str,
    source_price_version: str = "local",
) -> FeatureSnapshot:
    snapshot_frame = _normalize_input_frames(frames)
    if not snapshot_frame.empty:
        snapshot_frame["market"] = market
    return store.write(
        snapshot_frame,
        market=market,
        feature_version=feature_version,
        source_price_version=source_price_version,
    )


def update_feature_snapshot(
    frames: list[pd.DataFrame] | tuple[pd.DataFrame, ...],
    *,
    store: FeatureSnapshotStore,
    market: str,
    feature_version: str,
    source_price_version: str = "local",
) -> FeatureSnapshot:
    current = store.read(market=market, feature_version=feature_version)
    incoming = _normalize_input_frames(frames)
    if not incoming.empty:
        incoming["market"] = market
    if current is not None and not current.frame.empty:
        combined = pd.concat([current.frame, incoming], ignore_index=True)
    else:
        combined = incoming
    if not combined.empty and {"ticker", "date"}.issubset(combined.columns):
        combined["date"] = pd.to_datetime(combined["date"])
        combined = combined.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
    return store.write(
        combined,
        market=market,
        feature_version=feature_version,
        source_price_version=source_price_version,
    )

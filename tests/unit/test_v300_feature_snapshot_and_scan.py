"""Feature snapshot and batch scan contracts for v3.0.0."""

from __future__ import annotations

import pandas as pd
import pytest

from core.features.snapshot_builder import build_feature_snapshot, update_feature_snapshot
from core.features.snapshot_store import FeatureSnapshotStore
from core.scanner.batch_scan import (
    FeatureSnapshotMissingError,
    build_scan_cache_key,
    scan_feature_rows,
    scan_latest_snapshot,
)


def _ohlcv(ticker: str = "AAPL", periods: int = 5) -> pd.DataFrame:
    dates = pd.date_range("2026-06-22", periods=periods, freq="D")
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": dates,
            "open": [10.0 + i for i in range(periods)],
            "high": [11.0 + i for i in range(periods)],
            "low": [9.0 + i for i in range(periods)],
            "close": [10.0 + i for i in range(periods)],
            "volume": [1000.0 + i for i in range(periods)],
        }
    )


def test_feature_snapshot_store_writes_required_metadata(tmp_path):
    store = FeatureSnapshotStore(tmp_path)
    snapshot = build_feature_snapshot(
        [_ohlcv()],
        store=store,
        market="CN",
        feature_version="v300-unit",
        source_price_version="unit-prices",
    )

    assert snapshot.metadata["feature_version"] == "v300-unit"
    assert snapshot.metadata["market"] == "CN"
    assert snapshot.metadata["as_of_date"] == "2026-06-26"
    assert snapshot.metadata["ticker_count"] == 1
    assert snapshot.metadata["row_count"] == 5
    assert snapshot.metadata["source_price_version"] == "unit-prices"
    assert isinstance(snapshot.metadata["created_at"], str)
    assert store.paths(market="CN", feature_version="v300-unit")[0].exists()
    assert store.paths(market="CN", feature_version="v300-unit")[1].exists()


def test_update_feature_snapshot_replaces_duplicate_ticker_date(tmp_path):
    store = FeatureSnapshotStore(tmp_path)
    build_feature_snapshot([_ohlcv(periods=5)], store=store, market="CN", feature_version="v300-unit")
    updated = _ohlcv(periods=5).tail(1).copy()
    updated["close"] = 99.0

    snapshot = update_feature_snapshot([updated], store=store, market="CN", feature_version="v300-unit")
    latest = snapshot.frame.sort_values("date").iloc[-1]

    assert len(snapshot.frame) == 5
    assert latest["close"] == 99.0


def _feature_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "D"],
            "market": ["CN", "CN", "HK", "CN"],
            "date": [
                pd.Timestamp("2026-06-25"),
                pd.Timestamp("2026-06-26"),
                pd.Timestamp("2026-06-26"),
                pd.Timestamp("2026-06-26"),
            ],
            "close": [10.0, 20.0, 30.0, 40.0],
            "return_20d": [0.01, 0.12, 0.20, -0.08],
            "rsi_14": [45.0, 58.0, 62.0, 30.0],
            "ma_20": [9.0, 18.0, 28.0, 45.0],
            "ma_60": [8.0, 17.0, 27.0, 50.0],
            "volatility_20d": [0.02, 0.03, 0.04, 0.05],
            "volume_ratio_20d": [1.0, 2.0, 1.5, 0.7],
        }
    )


def test_scan_feature_rows_filters_by_market_and_as_of_date():
    result = scan_feature_rows(
        _feature_rows(),
        strategy_config={"name": "momentum", "params": {"min_score": 0}},
        market="CN",
        as_of_date="2026-06-26",
    )

    assert result["ticker"].tolist() == ["B", "D"]


def test_scan_cache_key_is_deterministic_for_strategy_params():
    first = build_scan_cache_key(
        market="CN",
        as_of_date="2026-06-26",
        strategy_config={"name": "momentum", "params": {"b": 2, "a": 1}},
    )
    second = build_scan_cache_key(
        market="CN",
        as_of_date="2026-06-26",
        strategy_config={"params": {"a": 1, "b": 2}, "name": "momentum"},
    )

    assert first == second


def test_scan_latest_snapshot_raises_clear_error_when_missing(tmp_path):
    with pytest.raises(FeatureSnapshotMissingError, match="No feature snapshot"):
        scan_latest_snapshot(
            store=FeatureSnapshotStore(tmp_path),
            market="CN",
            feature_version="missing",
            strategy_config={"name": "momentum"},
        )

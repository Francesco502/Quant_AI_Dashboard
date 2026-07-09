"""Data access and native-kernel contracts for v3.0.0."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import native_kernel
from core.data_access.contracts import BatchOHLCVRequest, BatchOHLCVResponse, FreshnessSummary
from core.data_access.local_lake import LocalOhlcvLake
from core.features.technical import add_technical_features


def test_batch_ohlcv_request_sorts_and_deduplicates_tickers():
    request = BatchOHLCVRequest(tickers=[" TSLA ", "AAPL", "TSLA", "  "], days=10)

    assert request.tickers == ("AAPL", "TSLA")
    assert request.refresh_stale is True


def test_batch_ohlcv_request_rejects_invalid_days():
    with pytest.raises(ValueError, match="days must be positive"):
        BatchOHLCVRequest(tickers=["AAPL"], days=0)


def test_batch_ohlcv_response_reports_tickers_rows_and_missing():
    frame = pd.DataFrame(
        {"close": [1.0, 2.0]},
        index=pd.to_datetime(["2026-06-25", "2026-06-26"]),
    )
    response = BatchOHLCVResponse(
        ticker_frames={"AAPL": frame},
        missing_tickers=("MSFT",),
        cache_hit=True,
        source="local_lake",
        freshness=FreshnessSummary(latest_date="2026-06-26", age_days=1),
    )

    assert response.tickers == ("AAPL",)
    assert response.row_count == 2
    assert response.missing_tickers == ("MSFT",)


def _ohlcv_frame(start: str = "2026-06-24") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [10.0, 11.0, 12.0],
            "high": [11.0, 12.0, 13.0],
            "low": [9.5, 10.5, 11.5],
            "close": [10.5, 11.5, 12.5],
            "volume": [1000.0, 1100.0, 1200.0],
        },
        index=pd.date_range(start, periods=3, freq="D"),
    )


def test_local_ohlcv_lake_roundtrips_batch_frames(tmp_path):
    lake = LocalOhlcvLake(tmp_path)
    lake.write_batch({"MSFT": _ohlcv_frame("2026-06-24"), "AAPL": _ohlcv_frame("2026-06-23")})

    result = lake.read_batch(BatchOHLCVRequest(tickers=["MSFT", "AAPL"], days=2))

    assert result.source == "local_lake"
    assert result.cache_hit is True
    assert result.missing_tickers == ()
    assert result.tickers == ("AAPL", "MSFT")
    assert list(result.ticker_frames["AAPL"].columns) == ["open", "high", "low", "close", "volume"]
    assert result.ticker_frames["AAPL"].index.is_monotonic_increasing
    assert result.ticker_frames["AAPL"].index[-1].strftime("%Y-%m-%d") == "2026-06-25"


def test_technical_features_are_stable_for_known_series():
    frame = pd.DataFrame(
        {
            "ticker": "AAPL",
            "date": pd.date_range("2026-01-01", periods=25, freq="D"),
            "close": [float(i) for i in range(1, 26)],
            "volume": np.full(25, 1000.0),
        }
    )

    result = add_technical_features(frame)

    assert result["ma_20"].iloc[19] == 10.5
    assert result["ma_20"].iloc[-1] == 15.5
    assert result["rsi_14"].between(0, 100).all()


class FakeNativeModule:
    def score_feature_rows(self, arrays):
        return native_kernel.score_feature_rows_python(arrays)


def test_native_facade_uses_loaded_module_and_preserves_python_contract(monkeypatch):
    monkeypatch.setenv("QUANT_NATIVE_KERNEL", "auto")
    monkeypatch.setattr(native_kernel, "_load_module", lambda: FakeNativeModule())
    rows = pd.DataFrame(
        {
            "close": [10.0, 30.0],
            "ma_20": [9.0, 20.0],
            "ma_60": [8.0, 19.0],
            "return_20d": [0.1, np.nan],
            "rsi_14": [55.0, 80.0],
            "volatility_20d": [0.02, 0.05],
            "volume_ratio_20d": [1.2, 2.0],
        }
    )

    native_scores = native_kernel.score_feature_rows(rows)
    monkeypatch.setenv("QUANT_NATIVE_KERNEL", "off")
    python_scores = native_kernel.score_feature_rows(rows)

    np.testing.assert_allclose(native_scores, python_scores)

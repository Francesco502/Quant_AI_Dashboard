"""Unit tests for StockTradebyZ adapter behavior."""

from __future__ import annotations

from pathlib import Path

import core.stocktradebyz_adapter as adapter


def test_market_scan_refreshes_stale_data_by_default(monkeypatch, tmp_path: Path):
    prices_dir = tmp_path / "prices"
    prices_dir.mkdir(parents=True)
    (prices_dir / "000001.parquet").touch()

    calls: list[dict[str, object]] = []

    def fake_load_ohlcv_data(**kwargs):
        calls.append(kwargs)
        return {}

    monkeypatch.delenv("MARKET_SCAN_REFRESH_STALE", raising=False)
    monkeypatch.setattr(adapter, "_ensure_available", lambda: None)
    monkeypatch.setattr("core.data_store.BASE_DIR", str(tmp_path))
    monkeypatch.setattr(adapter, "load_ohlcv_data", fake_load_ohlcv_data)

    result = adapter.run_selectors_for_market(trade_date="2026-03-19", market="CN")

    assert result.empty
    assert calls
    assert calls[0]["refresh_stale"] is True

import pandas as pd

from core.auto_paper_trading import (
    UNIVERSE_MODE_ASSET_POOL,
    UNIVERSE_MODE_CN_A_SHARE,
    UNIVERSE_MODE_MANUAL,
    _load_price_history_batched,
    _prefilter_universe_tickers,
    resolve_auto_trading_universe,
)


def test_resolve_manual_universe_dedupes_symbols():
    resolved = resolve_auto_trading_universe(
        {
            "trading": {
                "universe_mode": UNIVERSE_MODE_MANUAL,
                "universe": ["510300", "510300", "159915"],
            }
        }
    )

    assert resolved.mode == UNIVERSE_MODE_MANUAL
    assert resolved.tickers == ["510300", "159915"]


def test_resolve_asset_pool_universe(monkeypatch):
    monkeypatch.setattr(
        "core.auto_paper_trading.get_asset_pool_tickers",
        lambda limit=None: ["013281", "002611"][: limit or 2],
    )

    resolved = resolve_auto_trading_universe(
        {
            "trading": {
                "universe_mode": UNIVERSE_MODE_ASSET_POOL,
            }
        }
    )

    assert resolved.mode == UNIVERSE_MODE_ASSET_POOL
    assert resolved.tickers == ["013281", "002611"]


def test_resolve_cn_a_share_universe(monkeypatch):
    monkeypatch.setattr(
        "core.auto_paper_trading.list_cn_a_share_tickers",
        lambda limit=None: ["000001", "000002", "600000"][: limit or 3],
    )

    resolved = resolve_auto_trading_universe(
        {
            "trading": {
                "universe_mode": UNIVERSE_MODE_CN_A_SHARE,
                "universe_limit": 2,
            }
        }
    )

    assert resolved.mode == UNIVERSE_MODE_CN_A_SHARE
    assert resolved.tickers == ["000001", "000002"]


def test_prefilter_universe_screens_and_limits(monkeypatch):
    calls = []

    def fake_load_price_data(tickers, days, refresh_stale=False):  # noqa: ANN001
        calls.append((list(tickers), days, refresh_stale))
        index = pd.date_range("2026-01-01", periods=90, freq="B")
        payload = {}
        for idx, ticker in enumerate(tickers):
            base = 10 + idx
            payload[ticker] = pd.Series([base + (step * (idx + 1) * 0.1) for step in range(len(index))], index=index)
        return pd.DataFrame(payload, index=index)

    monkeypatch.setattr("core.auto_paper_trading.load_price_data", fake_load_price_data)

    result = _prefilter_universe_tickers(
        [f"{i:06d}" for i in range(1, 11)],
        evaluation_days=180,
        screening_limit=4,
        batch_size=3,
    )

    assert len(result) == 4
    assert all(len(batch[0]) <= 3 for batch in calls)
    assert all(batch[2] is False for batch in calls)


def test_load_price_history_batched_merges_batches(monkeypatch):
    def fake_load_price_data(tickers, days, refresh_stale=False):  # noqa: ANN001
        index = pd.date_range("2026-01-01", periods=5, freq="B")
        return pd.DataFrame({ticker: pd.Series(range(1, 6), index=index, dtype=float) for ticker in tickers}, index=index)

    monkeypatch.setattr("core.auto_paper_trading.load_price_data", fake_load_price_data)

    frame = _load_price_history_batched(["000001", "000002", "000003"], history_days=120, batch_size=2)

    assert list(frame.columns) == ["000001", "000002", "000003"]
    assert len(frame) == 5

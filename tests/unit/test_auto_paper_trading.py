from types import SimpleNamespace

import pandas as pd

from core.auto_paper_trading import (
    StrategyEvaluation,
    UNIVERSE_MODE_ASSET_POOL,
    UNIVERSE_MODE_CN_A_SHARE,
    UNIVERSE_MODE_MANUAL,
    _load_price_history_batched,
    _prefilter_universe_tickers,
    run_auto_trading_cycle,
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

    def fake_load_price_data(tickers, days, refresh_stale=False, remote_cache_days=None):  # noqa: ANN001
        calls.append((list(tickers), days, refresh_stale, remote_cache_days))
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
    assert all(batch[3] == 140 for batch in calls)


def test_prefilter_universe_downsamples_before_screening(monkeypatch):
    calls = []

    def fake_load_price_data(tickers, days, refresh_stale=False, remote_cache_days=None):  # noqa: ANN001
        calls.append(list(tickers))
        index = pd.date_range("2026-01-01", periods=90, freq="B")
        return pd.DataFrame(
            {ticker: pd.Series([10 + step * 0.1 for step in range(len(index))], index=index) for ticker in tickers},
            index=index,
        )

    monkeypatch.setattr("core.auto_paper_trading.load_price_data", fake_load_price_data)

    _prefilter_universe_tickers(
        [f"{i:06d}" for i in range(1, 51)],
        evaluation_days=180,
        screening_limit=4,
        batch_size=5,
    )

    screened = [ticker for batch in calls for ticker in batch]
    assert len(screened) <= 16
    assert len(set(screened)) == len(screened)


def test_load_price_history_batched_merges_batches(monkeypatch):
    def fake_load_price_data(tickers, days, refresh_stale=False, remote_cache_days=None):  # noqa: ANN001
        index = pd.date_range("2026-01-01", periods=5, freq="B")
        return pd.DataFrame({ticker: pd.Series(range(1, 6), index=index, dtype=float) for ticker in tickers}, index=index)

    monkeypatch.setattr("core.auto_paper_trading.load_price_data", fake_load_price_data)

    frame = _load_price_history_batched(["000001", "000002", "000003"], history_days=120, batch_size=2)

    assert list(frame.columns) == ["000001", "000002", "000003"]
    assert len(frame) == 5


def test_run_auto_trading_cycle_returns_rebalance_result(monkeypatch):
    index = pd.date_range("2026-01-01", periods=220, freq="B")
    price_frame = pd.DataFrame(
        {
            "000001": pd.Series([10 + step * 0.05 for step in range(len(index))], index=index),
            "000002": pd.Series([8 + step * 0.04 for step in range(len(index))], index=index),
        }
    )

    monkeypatch.setattr(
        "core.auto_paper_trading.resolve_auto_trading_universe",
        lambda cfg: SimpleNamespace(mode="manual", label="manual", tickers=["000001", "000002"]),
    )
    monkeypatch.setattr("core.auto_paper_trading._prefilter_universe_tickers", lambda tickers, **kwargs: list(tickers))
    monkeypatch.setattr("core.auto_paper_trading._load_price_history_batched", lambda tickers, **kwargs: price_frame[tickers])
    monkeypatch.setattr(
        "core.auto_paper_trading.evaluate_strategies",
        lambda **kwargs: [
            StrategyEvaluation(
                strategy_id="ema_crossover",
                name="EMA",
                average_total_return=0.12,
                average_sharpe_ratio=1.3,
                worst_drawdown=0.08,
                score=1.1,
                tested_tickers=["000001", "000002"],
                passed=True,
            )
        ],
    )
    monkeypatch.setattr(
        "core.auto_paper_trading._build_candidate_scores",
        lambda price_data, passed_evaluations: {"000001": 3.0, "000002": 2.0},
    )
    monkeypatch.setattr("core.auto_paper_trading._resolve_user_id", lambda db, username: 1)

    submitted_orders = []

    class FakeAccountManager:
        def get_positions(self, account_id, refresh_prices=False):
            return []

        def get_account(self, account_id, user_id):
            return SimpleNamespace(id=account_id, balance=100000.0, initial_capital=100000.0)

        def save_equity_snapshot(self, **kwargs):
            return None

    fake_account = SimpleNamespace(id=2, account_name="全市场自动模拟交易", initial_capital=100000.0)
    fake_service = SimpleNamespace(
        db=object(),
        account_mgr=FakeAccountManager(),
        risk_monitor=SimpleNamespace(risk_limits=SimpleNamespace(max_single_stock=0.5)),
        get_portfolio=lambda user_id, account_id: {"total_assets": 100000.0},
        submit_order=lambda **kwargs: submitted_orders.append(kwargs) or {"success": True},
    )

    monkeypatch.setattr(
        "core.auto_paper_trading._ensure_account",
        lambda account_mgr, user_id, account_name, initial_capital: fake_account,
    )

    result = run_auto_trading_cycle(
        {
            "trading": {
                "username": "admin",
                "account_name": "全市场自动模拟交易",
                "initial_capital": 100000.0,
                "strategy_ids": ["ema_crossover"],
                "max_positions": 2,
                "evaluation_days": 180,
                "top_n_strategies": 1,
                "min_total_return": 0.0,
                "min_sharpe_ratio": 0.0,
                "max_drawdown": 0.35,
            }
        },
        fake_service,
    )

    assert result["account_id"] == 2
    assert result["selection_mode"] == "validated"
    assert result["selected_tickers"] == ["000001", "000002"]
    assert len(submitted_orders) == 2
    assert all(order["side"].value == "BUY" for order in submitted_orders)

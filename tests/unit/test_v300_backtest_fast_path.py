from __future__ import annotations

import numpy as np
import pandas as pd

from core.backtest_engine import BacktestEngine


def _price_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"A": [10.0, 11.0, 12.0, 11.0], "B": [20.0, 19.0, 18.0, 21.0]},
        index=pd.date_range("2026-06-23", periods=4, freq="D"),
    )


def _target_shares() -> pd.DataFrame:
    return pd.DataFrame(
        {"A": [10, 10, 0, 5], "B": [0, 5, 5, 5]},
        index=pd.date_range("2026-06-23", periods=4, freq="D"),
    )


def test_profiled_backtest_reports_hot_loop_breakdown():
    price_data = _price_frame()

    def strategy(df: pd.DataFrame, params: dict) -> dict[str, int]:
        return _target_shares().loc[df.index[-1]].astype(int).to_dict()

    result = BacktestEngine(initial_capital=100000).run(price_data, strategy, collect_profile=True)

    assert result["profile"]["iterations"] == len(price_data)
    assert result["profile"]["total_seconds"] >= 0.0
    assert set(result["profile"]["breakdown"])
    assert all(item["seconds"] >= 0.0 for item in result["profile"]["breakdown"].values())
    assert all(0.0 <= item["percent"] <= 100.0 for item in result["profile"]["breakdown"].values())


def test_precomputed_signal_matrix_fast_path_matches_event_driven_without_fees():
    fees = {"commission": 0.0, "stamp_duty": 0.0, "slippage": 0.0}
    price_data = _price_frame()
    signals = _target_shares()

    def strategy(df: pd.DataFrame, params: dict) -> dict[str, int]:
        return signals.loc[df.index[-1]].astype(int).to_dict()

    baseline = BacktestEngine(initial_capital=100000, fees=fees).run(price_data, strategy)
    fast = BacktestEngine(initial_capital=100000, fees=fees).run_precomputed_signals(
        price_data,
        signals,
        target_type="shares",
    )

    pd.testing.assert_series_equal(
        baseline["equity_curve"]["equity"],
        fast["equity_curve"]["equity"],
        check_names=False,
    )
    np.testing.assert_allclose(baseline["total_return"], fast["total_return"])
    np.testing.assert_allclose(baseline["turnover"], fast["turnover"])
    assert fast["fast_path"] is True

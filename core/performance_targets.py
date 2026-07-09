"""Release performance gates for Quant-AI Dashboard v3.0.0."""

from __future__ import annotations


API_HEALTH_MAX_MS = 100.0
DASHBOARD_SUMMARY_HOT_MAX_MS = 500.0
API_ONLY_RSS_MAX_MB = 800.0
BACKTEST_FAST_PATH_MAX_MS = 100.0
SCAN_HOT_CACHE_MAX_MS = 500.0


def as_dict() -> dict[str, float]:
    return {
        "API_HEALTH_MAX_MS": API_HEALTH_MAX_MS,
        "DASHBOARD_SUMMARY_HOT_MAX_MS": DASHBOARD_SUMMARY_HOT_MAX_MS,
        "API_ONLY_RSS_MAX_MB": API_ONLY_RSS_MAX_MB,
        "BACKTEST_FAST_PATH_MAX_MS": BACKTEST_FAST_PATH_MAX_MS,
        "SCAN_HOT_CACHE_MAX_MS": SCAN_HOT_CACHE_MAX_MS,
    }

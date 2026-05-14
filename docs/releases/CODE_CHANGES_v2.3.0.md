# Code Changes `v2.3.0`

## Backend

- `core/audit_log.py`: restored `Request` import for middleware health and API access logging.
- `core/memory_monitor.py`: corrected resident-memory calculation on macOS.
- `api/router_registry.py`: kept legacy account routes retired by default while preserving an explicit opt-in path.
- `api/routers/trading.py` and `api/routers/trading_helpers.py`: restored missing helper imports, auto-run state compatibility, and account/auto-trading flows.
- `core/trading_service.py`: added safe lazy construction, compatibility aliases, default broker behavior, and stricter account/order error handling.
- `core/backtest_engine.py`: restored legacy strategy/backtest call compatibility and stable result payloads.
- `core/strategy_framework.py`: restored legacy config, indicator, forecast, and ensemble compatibility.
- `core/risk_monitor.py`: avoids concentration warnings for reducing sell orders.
- `core/llm_client.py`: added bounded LLM request timeouts and retry control.
- `api/routers/agent.py` and `core/agent/runner.py`: added quick/default Agent mode, tool selection, and timeout degradation.

## Data Fetchers

- `core/data_cleaning.py`: added shared OHLCV normalization helper.
- `core/data_fetchers/tushare.py`: restored optional Tushare runtime resolution and monkeypatch compatibility.
- `core/data_fetchers/akshare.py`, `alpha_vantage.py`, `binance.py`, `yfinance.py`, `hk_index.py`: restored extracted imports and optional provider guards.

## Frontend

- `web/src/lib/theme-context.tsx`: removed mount-time state update pattern flagged by lint.
- `web/src/components/layout/app-shell.tsx`: removed unused auth value.
- `web/src/app/settings/page.tsx`: added release-safe loading shell with expected page context.
- `web/src/app/daily-workbench/page.tsx`: added page title in loading skeleton.

## Tests And Docs

- `tests/unit/test_strategy_framework.py`: aligned stale strategy tests with the DataFrame contract used by current APIs.
- `AGENTS.md`: updated frontend/API route inventory for `v2.3.0`.
- `docs/releases/*_v2.3.0.md`: added release notes, status, upgrade, rollback, and code-change records.

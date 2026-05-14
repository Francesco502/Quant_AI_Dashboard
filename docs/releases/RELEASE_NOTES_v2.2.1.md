# Release Notes `v2.2.1`

## Focus

`v2.2.1` turns the personal quant workspace into a daily decision workflow instead of a set of isolated pages.

## Added

- Daily decision workbench at `/daily-workbench`.
- Data freshness checks for prediction, scanning, and backtesting flows.
- Unified review audit API for scans, predictions, backtests, asset ledger edits, strategy templates, paper orders, and backups.
- Backup create, list, download, and selective restore for SQLite data, configs, exports, and audit logs.
- Personal asset CSV import.
- Settings initialization guide with backup management.

## Improved

- Scan results now link directly into prediction, backtest, and paper order flows.
- Backtest parameter optimization now includes overfitting warnings and records audit events.
- New 2.2.1 APIs expose typed response models instead of loose dictionaries.
- Workspace navigation includes a first-class daily decision entry.

## Validation Gates

- `python -m pytest tests/unit/test_v221_daily_workbench.py tests/unit/test_v221_api_routes.py -q`
- `python -m pytest tests/integration/test_user_assets_api.py -q`
- `python -m pytest tests/unit/test_api_app_registration.py tests/integration/test_trading_api.py -q`
- `python -m compileall -q api core tests`
- `cd web && npm run lint`
- `cd web && npm run build`

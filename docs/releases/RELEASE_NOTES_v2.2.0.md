# Release Notes `v2.2.0`

## Highlights

- Consolidated the personal quant workspace around research, market review, backtesting, paper trading, and decision support.
- Standardized the frontend production startup path on `next start` and aligned release validation to the externally running services on ports `8686` and `8685`.
- Added a canonical release guide and cleaned current operating docs so quickstart, deployment, and release procedures all point to the same workflow.

## Release Engineering Changes

- `scripts/release_check.py` is now the canonical external release gate.
- CI release validation now runs the same script used locally, reducing drift between local sign-off and GitHub Actions.
- Generated release reports are written under `output/reports/` instead of polluting the repository root.
- Generated Playwright traces and temporary scratch directories are explicitly ignored.

## Operational Notes

- Canonical production deployment remains `docker compose` with `Dockerfile.optimized`.
- Browser login still depends on `APP_LOGIN_PASSWORD` or `APP_LOGIN_PASSWORD_HASH` being configured.
- Automatic trading remains opt-in and should stay disabled until credentials, data freshness, and strategy settings are verified.

# Release Notes `v2.3.0`

## Focus

`v2.3.0` hardens the personal quant dashboard for release by stabilizing API startup, paper-trading flows, frontend shell behavior, and external release validation.

## Fixed

- Restored `/api/health` by fixing audit middleware request typing.
- Recovered the trading API account, primary-account, auto-config, and run-now flows.
- Restored extracted data fetchers for Tushare, AkShare, Alpha Vantage, Binance, yfinance, and HK index helpers.
- Made the backtest engine compatible with both current and legacy strategy call signatures used by local tests.
- Removed frontend lint failures and warnings in the theme provider and app shell.
- Added fast, explicit fallback behavior for Agent research when an external LLM provider times out.
- Preserved page identity during settings and daily-workbench loading states so UI smoke tests and users see the correct context immediately.

## Improved

- Live health checks now report realistic memory pressure on macOS and low-resource hosts.
- Trading service initialization supports production dependency injection and test/local lazy construction.
- External release validation now passes with Playwright Chromium installed and running frontend/backend services.
- Release route documentation now matches the actual App Router surface.

## Validation Gates

- `python -m compileall -q api core tests`
- `python -m pytest tests/unit -q`
- `python -m pytest tests/integration -q`
- `python -m pytest tests/test_v3_smoke.py -q`
- `python -m pytest tests/e2e -m "e2e_inprocess" -q`
- `cd web && npm run lint`
- `cd web && npm run build`
- `cd web && NEXT_PUBLIC_API_URL=/api NEXT_STATIC_EXPORT=1 NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production npx next build`
- `python scripts/release_check.py`

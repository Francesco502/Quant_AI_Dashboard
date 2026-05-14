# Release Status `v2.3.0`

## Current Position

- Release line: `v2.3.0`
- Status: `release-candidate validation green; pending final scope commit/tag`
- Deployment target: optimized single-image Docker deployment with frontend on `8686` and backend API on `8685`
- Latest local sign-off date: `2026-05-14`

## Completed Scope

- Backend startup, audit middleware, health checks, and route registration.
- Paper-trading service compatibility, account detail routes, reset flow, and auto-trading configuration endpoints.
- Extracted market data fetcher imports and normalization contracts.
- Backtest, strategy framework, and risk monitor compatibility fixes.
- Frontend theme/app shell lint hardening plus settings and daily-workbench loading-state release fixes.
- External release validation using running local frontend/backend services.
- Optimized image runtime hardening for dashboard cold-start fan-out on low-resource hosts.

## Required Release Evidence

1. `python -m compileall -q api core tests`
2. `python -m pytest tests/unit -q`
3. `python -m pytest tests/integration -q`
4. `python -m pytest tests/test_v3_smoke.py -q`
5. `python -m pytest tests/e2e -m "e2e_inprocess" -q`
6. `cd web && npm run lint`
7. `cd web && npm run build`
8. `cd web && npm audit --audit-level=low`
9. `cd web && NEXT_PUBLIC_API_URL=/api NEXT_STATIC_EXPORT=1 NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production npx next build`
10. `docker build -f Dockerfile.optimized -t quant-ai-dashboard:2.3.0 .`
11. With frontend/backend running: `python scripts/release_check.py`

## Latest Validation Result

- Default pytest: `479 passed, 30 skipped`
- Compile: passed
- Focused audit/monitoring regression tests: `20 passed`
- Frontend audit: `0 vulnerabilities`
- Frontend lint: passed with no warnings
- Frontend production build: passed on Next.js `16.2.6`
- Docker optimized image build: passed locally as `quant-ai-dashboard:local-verify`
- External release validation: `18 passed` against `quant-ai-dashboard:local-verify` on `127.0.0.1:8685/8686`

## Residual Notes

- Next.js currently emits a Node `[DEP0205] module.register()` deprecation warning during build; this is not an application error.
- External LLM providers remain optional. Agent research returns an explicit degraded response when a configured provider times out.
- The optimized image defaults `UVICORN_LIMIT_CONCURRENCY=32`; tune this through the container environment for tighter or roomier hosts.
- Automatic real-money trading remains out of scope; paper trading and manual review remain the intended workflow.
- The worktree still contains a broad release candidate file set. Before tagging, review and commit only the intended source, test, docs, and deployment changes.

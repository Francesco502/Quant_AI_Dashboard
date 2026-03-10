# Quant-AI Dashboard Release Notes

## Version
- `1.0.0`

## Release Date
- `2026-03-10`

## Summary
`v1.0.0` is the first stable release baseline for the current architecture (FastAPI + Next.js + SQLite).
This release focuses on reliability, API contract closure, and production-facing test credibility.

## Key Updates
1. Authentication and CORS
- Fixed middleware behavior so CORS preflight `OPTIONS` requests are not blocked by auth checks.
- Fixed `/api/auth/me` permission payload generation to return RBAC permissions correctly.
- Added role fallback/self-healing behavior when role mapping is missing.

2. Trading Contract Closure (Paper Trading)
- Aligned frontend paper-trading API calls with backend routes.
- Added frontend account payload normalization to bridge backend flat schema and UI portfolio schema.

3. Portfolio Analysis Stability
- Fixed ndarray scalar extraction in risk contribution calculation to prevent `TypeError` and `500`.

4. Legacy Account Compatibility
- Removed implicit fallback to “first active DB account” in `ensure_account_dict(None)`.
- Default account generation is now deterministic and test-friendly.

5. Test Reliability
- Updated feature-engineering tests to pytest-compatible setup method.
- Added integration regression coverage for auth/CORS behavior.
- Added benchmark fixture fallback and benchmark dependency declaration.

## Documentation and Versioning
- Unified project version to `1.0.0` in code and package metadata.
- Updated root/backend/frontend README files.
- Added dedicated release and code-change documents for traceability.

## Verification Snapshot
Validated with targeted tests and lint checks, including:
- `tests/integration/test_portfolio_api.py`
- `tests/integration/test_auth_api.py`
- `tests/unit/test_feature_engineering.py`
- `tests/unit/test_risk_monitor.py`
- `tests/unit/test_trading_engine_extra.py::TestAccountUtils::test_ensure_account_dict_empty`
- `web/src/lib/api.ts` lint

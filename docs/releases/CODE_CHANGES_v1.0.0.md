# Quant-AI Dashboard Code Changes (`v1.0.0`)

## Scope
This document records the code-level changes bundled into `v1.0.0`, including stability fixes, version bump updates, and release documentation.

## Version Metadata
- `core/version.py`
  - Updated `__version__` / `VERSION` to `1.0.0`
  - Updated `VERSION_INFO` major/minor/patch and build date

- `web/package.json`
  - Updated frontend package version to `1.0.0`

- `web/package-lock.json`
  - Updated lockfile root package version to `1.0.0`

## Backend/API Reliability
- `api/auth.py`
  - Allowed `OPTIONS` requests to pass auth middleware for CORS preflight
  - Fixed `/api/auth/me` permission payload generation
  - Added role fallback and role mapping self-heal on user loading

- `core/portfolio_analyzer.py`
  - Fixed 1x1 ndarray to scalar conversion in risk contribution calculation

- `core/account.py`
  - Removed implicit DB account fallback for `ensure_account_dict(None)`
  - Kept explicit scoped account loading when `account_id` or `user_id` is provided

## Frontend Contract Alignment
- `web/src/lib/api.ts`
  - Aligned paper-trading calls to backend-supported routes
  - Added paper-account response normalization from backend flat shape to UI portfolio shape
  - Updated paper order submission path and payload mapping

## Test & Validation Enhancements
- `tests/integration/test_auth_api.py` (new)
  - Added integration tests for:
    - CORS preflight pass-through
    - `/api/auth/me` for regular users
    - admin permission response consistency

- `tests/unit/test_feature_engineering.py`
  - Replaced unittest-style `setUp` with pytest-compatible `setup_method`

- `tests/conftest.py`
  - Added benchmark fixture fallback for environments lacking `pytest-benchmark`

- `tests/test_v3_smoke.py`
  - Updated version consistency assertion to `1.0.0`

- `requirements.txt`
  - Added `pytest-benchmark>=4.0.0`
  - Normalized testing dependency lines

## Readme and Release Docs
- `README.md`
- `api/README.md`
- `web/README.md`
  - Updated for `v1.0.0` and linked release documents

- `docs/RELEASE_NOTES_v1.0.0.md` (new)
- `docs/CODE_CHANGES_v1.0.0.md` (new)

## Container Metadata
- `docker-compose.yml`
  - Updated image tag from `v3.0.0` to `v1.0.0`

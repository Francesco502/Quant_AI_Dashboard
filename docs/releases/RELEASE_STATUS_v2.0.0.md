# Release Status (`v2.0.0`)

## Current Position
- Release line: `v2.0.0`
- Status: `formal-release hardening in progress`

## Completed So Far
- Version metadata has been promoted from `v2.0.0-alpha.1` to `v2.0.0`
- Release design and implementation plan have been written under `docs/superpowers/`
- P0 security hardening completed:
  - removed real-looking example API key values
  - removed weak implicit default admin bootstrap
  - switched external E2E login to self-contained auth flows that no longer depend on a preexisting local admin account
  - added focused auth and LLM hardening tests
- Verification completed:
  - `python -m compileall -q api core tests`
  - `python -m pytest tests/unit/ -q`
  - `python -m pytest tests/integration -v`
  - `python -m pytest tests/e2e -m "e2e_inprocess" -v`
  - `python -m pytest tests/test_v3_smoke.py -q`
  - `cd web && npm run lint`
  - `cd web && npm run build`
  - `docker compose config`
  - Docker image build and runtime health check
  - `python -m pytest tests/e2e/test_release_validation.py -m "e2e_external" -v`
  - `python -m pytest tests/e2e/test_paper_trading.py -m "e2e_external" -v`

## Still Required Before Tagging `v2.0.0`
1. Review and polish the final release notes set before public tagging
2. Create the final `v2.0.0` release commit
3. Push branch/tag and publish GitHub Release evidence

## Evidence Added In This Cycle
- `tests/integration/test_auth_api.py`
  - bootstrap admin requires explicit credentials
  - bootstrap admin can be initialized from configured env vars
- `tests/unit/test_llm_client_security.py`
  - no default key falls back to dummy client
  - configured key still uses OpenAI-compatible mode
- `tests/e2e/test_release_validation.py`
  - external release smoke now self-registers a temporary user when no explicit credentials are provided
- `tests/e2e/test_paper_trading.py`
  - external paper-trading smoke now follows the actual `/api/trading/accounts*` contract

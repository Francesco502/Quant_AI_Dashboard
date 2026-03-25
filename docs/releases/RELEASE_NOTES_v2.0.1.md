# Quant-AI Dashboard Release Notes

## Version
- `2.0.1`

## Release Date
- `2026-03-19`

## Release Type
- `Patch release`
- Focused on release blocking bug fixes and production-readiness hardening.

## Summary
`v2.0.1` closes the main release blockers discovered during the 2.0.0 hardening cycle:

1. Fixed stop-loss / take-profit exit rule generation so take-profit thresholds are above entry price for long positions.
2. Restored invalid price rejection in risk checks while preserving market-order price fallback for missing prices.
3. Added runtime security guardrails for `SECRET_KEY` and release CORS configuration.
4. Added explicit LLM provider availability reporting and a lightweight provider health check endpoint.
5. Replaced the extended-analysis benchmark placeholder with real benchmark return loading.
6. Replaced the SMS alert placeholder with a working Twilio REST integration path.

## Release Gate

Before tagging `v2.0.1`, the following should be green and recorded:

1. `python -m pytest tests/unit -q`
2. `python -m pytest tests/integration -q`
3. `python -m pytest tests/test_v3_smoke.py -q`
4. `cd web && npm run lint && npm run build`
5. `RUN_EXTERNAL_E2E=1 pytest tests/e2e/test_release_validation.py -q`

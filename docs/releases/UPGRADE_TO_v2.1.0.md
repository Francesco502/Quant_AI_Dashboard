# Upgrade To `v2.1.0`

## What Changes

- Version bump from `2.0.1` to `2.1.0`
- Personal asset ledger, valuation snapshots, and DCA reconciliation are enabled
- Trading workspace is reorganized around simulation trading and automatic execution
- LLM default runtime is now Volcengine Ark through an OpenAI-compatible interface
- Docker deployment supports frontend, API, and daemon in one image

## Upgrade Notes

- No manual destructive schema migration is required for SQLite deployments.
- Existing asset-pool data remains unchanged.
- Existing personal-asset data is preserved.
- On environments where the seeded `admin` account is enabled, the default personal-asset set is auto-seeded only when the ledger is empty.
- Same-origin deployments should keep `API_EXPECT_SAME_ORIGIN=true`; split-origin deployments should explicitly set `CORS_ORIGINS`.

## Recommended Verification

```bash
python -m pytest tests/test_v3_smoke.py -q
python -m pytest tests/unit -q
python -m pytest tests/integration -q
cd web && npm run lint && npm run build
RUN_EXTERNAL_E2E=1 pytest tests/e2e/test_release_validation.py -q
```

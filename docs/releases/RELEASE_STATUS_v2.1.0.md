# Release Status `v2.1.0`

## Current Position

- Release line: `v2.1.0`
- Status: `release-candidate ready for final commit/tag`
- Deployment target: single-image lightweight server deployment with same-origin frontend/API routing

## Completed Scope

- Personal asset ledger, valuation, and DCA automation
- Unified simulation trading workspace
- Full-market automatic paper trading defaults
- Locked server-side data-source configuration
- LLM runtime defaults aligned to Volcengine Ark
- Runtime security health reporting and same-origin release guardrails
- Single-image Docker deployment for frontend, API, and daemon

## Release Evidence

1. `python -m pytest tests/unit -q`
2. `python -m pytest tests/integration -q`
3. `python -m pytest tests/test_v3_smoke.py -q`
4. `RUN_EXTERNAL_E2E=1 pytest tests/e2e/test_release_validation.py -q`
5. `cd web && npm run lint && npm run build`

## Final Release Tasks

1. Create the release commit from the final reviewed worktree.
2. Tag that commit as `v2.1.0`.
3. Publish the Docker image built from `Dockerfile.optimized`.

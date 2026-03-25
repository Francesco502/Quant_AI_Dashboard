# Release Status `v2.1.1`

## Current Position

- Release line: `v2.1.1`
- Status: `released`
- Deployment target: single-image lightweight server deployment with same-origin frontend/API routing

## Completed Scope

- Version metadata updated across backend, frontend, tests, and deployment docs.
- CI workflow hardened against plugin-dependent startup failures.
- CI triggers switched to manual dispatch-only mode.
- SMTP example placeholders standardized in legacy documentation.

## Release Evidence

1. `python -m pytest tests/test_v3_smoke.py -q`
2. `python -m pytest tests/unit -q`
3. `python -m pytest tests/performance -q`
4. `python -m coverage run --source=core,api -m pytest tests/unit -q`
5. `cd web && npm run lint && npm run build`

## Final Release Tasks

1. Create release commit.
2. Tag release commit as `v2.1.1`.
3. Publish single-image runtime built from `Dockerfile.optimized`.

# Release Status `v2.1.2`

## Current Position

- Release line: `v2.1.2`
- Status: `release-ready pending final commit/tag`
- Deployment target: single-image lightweight server deployment with same-origin frontend/API routing

## Completed Scope

- Version metadata updated across backend, frontend, tests, and deployment docs.
- Optimized Docker image build repaired to remove dependency on ignored local runtime files.
- Frontend optimized-image build now exports static assets for Nginx-based single-image deployment.
- CI workflow now validates the optimized release image build explicitly.
- External release validation passed against the built `2.1.2-rc` image with release-safe auth and same-origin settings.

## Release Evidence

1. `python -m compileall -q api core tests`
2. `python -m pytest tests/test_v3_smoke.py -q`
3. `python -m pytest tests/unit -q`
4. `python -m pytest tests/integration -q`
5. `python -m pytest tests/performance -q`
6. `cd web && npm run lint && npm run build`
7. `docker build -f Dockerfile.optimized -t quant-ai-dashboard:2.1.2-rc .`
8. `RUN_EXTERNAL_E2E=1 python -m pytest tests/e2e/test_release_validation.py -o addopts="--strict-markers --tb=short --disable-warnings" -m e2e_external -q`

## Final Release Tasks

1. Create the release commit from the final reviewed worktree.
2. Tag that commit as `v2.1.2`.
3. Publish the optimized single-image runtime built from `Dockerfile.optimized`.

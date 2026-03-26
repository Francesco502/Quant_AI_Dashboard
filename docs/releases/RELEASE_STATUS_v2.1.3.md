# Release Status `v2.1.3`

## Current Position

- Release line: `v2.1.3`
- Status: `released`
- Deployment target: single-image lightweight server deployment with same-origin frontend/API routing

## Completed Scope

- Version metadata updated across backend, frontend, tests, and deployment docs.
- Clean-checkout CI parity restored by tracking `core.data.external` in Git.
- Automatic push/PR CI guardrails remain enabled, including optimized image validation.
- External release validation and optimized image validation both passed on the release baseline.

## Release Evidence

1. `python -m compileall -q api core tests`
2. `python -m pytest tests/test_v3_smoke.py -q`
3. `python -m pytest tests/unit -q`
4. `python -m pytest tests/integration -q`
5. `python -m pytest tests/performance -q`
6. `cd web && npm run lint && npm run build`
7. `docker build -f Dockerfile.optimized -t quant-ai-dashboard:2.1.3 .`
8. The latest `main` GitHub Actions release-validation baseline completed successfully before tagging

## Post-Release Notes

1. `v2.1.2` remains published as the earlier tag and image line.
2. `v2.1.3` is the patch release that aligns the published source baseline with the green CI baseline.
3. Monitor the existing Node.js 20 GitHub Actions deprecation warning and schedule an action-version refresh before June 2026.

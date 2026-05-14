# Release Scope `v2.3.0`

## Purpose

This file records the current release-candidate scope so the broad local worktree can be reviewed intentionally before commit and tag.

## Candidate Areas

- Backend API and route registration: `api/`
- Core data, strategy, backtest, trading, monitoring, audit, and user-asset services: `core/`
- Frontend App Router pages, shared shell, loading/error states, and portfolio/trading/backtest workspaces: `web/src/`
- Release, deployment, and upgrade docs: `README.md`, `docs/current/`, `docs/releases/`
- Validation coverage: `tests/`
- Docker and runtime packaging: `Dockerfile`, `Dockerfile.optimized`, `docker-compose.yml`, `docker/`

## Review Before Commit

- Confirm the deleted legacy modules and pages are intentionally retired.
- Confirm untracked release docs and new backend/frontend modules are intended for `v2.3.0`.
- Keep local assistant metadata, generated reports, caches, build output, logs, and runtime data out of source control.
- Re-run the external release validation script against the final target services before tagging.

## Latest Local Evidence

- `.venv/bin/python -m pytest -v`: `479 passed, 30 skipped`
- `npm audit --audit-level=low`: `0 vulnerabilities`
- `npm run lint -- --max-warnings=0`: passed
- `npm run build`: passed
- `docker build -f Dockerfile.optimized -t quant-ai-dashboard:local-verify .`: passed
- `.venv/bin/python scripts/release_check.py`: `18 passed`

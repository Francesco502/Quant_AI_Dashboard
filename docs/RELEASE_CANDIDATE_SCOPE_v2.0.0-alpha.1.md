# Release Candidate Scope (`v2.0.0-alpha.1`)

## Goal
Define which parts of the current worktree belong to the `v2.0.0-alpha.1` release candidate, and which parts should remain excluded from release packaging.

## Include In Candidate

### Backend source
- `api/`
- `core/`

### Frontend source
- `web/src/`
- `web/package.json`
- `web/package-lock.json`
- `web/next.config.ts`
- `web/eslint.config.mjs`
- `web/Dockerfile`

### Runtime and deployment
- `docker-compose.yml`
- `docker-compose.optimized.yml`
- `Dockerfile`
- `Dockerfile.optimized`
- `docker/`
- `requirements.txt`
- `requirements.runtime.txt`
- `start_dashboard.bat`
- `start_dashboard.ps1`
- `start_optimized.sh`

### Tests and quality gates
- `tests/`
- `.github/workflows/`
- `pytest.ini`

### Release-facing docs
- `README.md`
- `api/README.md`
- `web/README.md`
- `tests/README.md`
- `docs/RELEASE_NOTES_v2.0.0-alpha.1.md`
- `docs/CODE_CHANGES_v2.0.0-alpha.1.md`
- `docs/RELEASE_STATUS_v2.0.0-alpha.1.md`
- `docs/RELEASE_CANDIDATE_SCOPE_v2.0.0-alpha.1.md`
- `DEPLOY_OPTIMIZED.md`
- `OPTIMIZATION_GUIDE.md`

## Keep Excluded From Release Package
- external reference repositories
  - `daily_stock_analysis-main/`
  - `dexter-main/`
- generated model artifacts
  - `models/*.joblib`
  - runtime-generated model binaries
- runtime output and coverage output
  - `output/`
  - `htmlcov/`
  - `benchmarks/`
  - `.pytest_cache/`
- local/agent helper files
  - `CLAUDE.md`
  - `.geminiignore`
  - prompt scratch files
- secrets and environment-specific files
  - `.env`
  - daemon status/config state

## Still Requires Human Decision Before Commit
- whether all new planning/analysis docs under `docs/` should be committed with alpha
- whether migration/optimization helper scripts under `scripts/` are part of alpha scope
- whether every newly added test file should ship in alpha.1 or be split into a later PR

## Important Note
The worktree is still dirty mainly because the repository now contains a large amount of real new source code, tests, CI, and deployment files.
This is no longer an ignore-rule problem.
To make the worktree clean, the next step must be commit curation, not more ignore expansion.

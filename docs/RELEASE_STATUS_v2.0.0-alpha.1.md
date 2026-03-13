# Release Status (`v2.0.0-alpha.1`)

## Current Position
- Release line: `v2.0.0-alpha.1`
- Status: `pre-release hardening in progress`

## Completed Verification
- Python source compilation
  - `python -m compileall -q api core tests`
- Backend unit tests
  - `python -m pytest tests/unit/ -q`
- Backend integration tests
  - `python -m pytest tests/integration -v`
- In-process E2E tests
  - `python -m pytest tests/e2e -m "e2e_inprocess" -v`
- Version smoke tests
  - `python -m pytest tests/test_v3_smoke.py -q`
- Frontend lint
  - `cd web && npm run lint`
- Frontend production build
  - `cd web && npm run build`
- External release validation
  - backend via `uvicorn`
  - frontend via `npm run dev`
  - `python -m pytest tests/e2e/test_release_validation.py -m "e2e_external" -v`
- Docker Compose syntax validation
  - `docker compose config`
- Docker image build
  - `docker compose build quant-app`
- Docker runtime smoke
  - `docker compose up -d`
  - `docker compose ps`
  - host health check against `http://127.0.0.1:8685/api/health`

## Fixed During Hardening
- Replaced false final-version wording `v2.0.0` with `v2.0.0-alpha.1`
- Aligned version metadata across runtime, frontend package, smoke tests, and release docs
- Added release-scope and code-change docs for the alpha line
- Extended `.gitignore` to exclude external reference repos, output artifacts, model binaries, coverage output, and abnormal local files
- Fixed CI release-validation frontend startup to use a working command
- Added a separate frontend `preview` command for exported static output

## Remaining Blockers Before Final Release
1. Git worktree is still not release-clean
   - many tracked modifications remain uncommitted
   - many intended new source files remain untracked
2. GitHub release evidence is still missing
   - no `v2.x` tag yet
   - no committed release branch / PR yet
   - no GitHub Actions run exists for the final release candidate commit
3. GitHub authentication is still incomplete
   - `gh` is now installed locally
   - but `gh auth status` reports no logged-in host
4. Release scope still needs final commit curation
   - decide which new docs and source modules are part of the alpha/beta release set

## Known Notes
- The project uses static export for the frontend, so `next start` is not a valid preview path for release validation
- Local release-validation was successfully executed with backend `uvicorn` + frontend `npm run dev`
- Docker validation is now available locally because Docker Desktop was started during hardening

## Suggested Next Step
1. Curate the release file set
2. Commit the alpha baseline
3. Re-run CI on GitHub
4. Re-run Docker build/up after Docker daemon is available
5. Promote to `beta` only after those checks pass

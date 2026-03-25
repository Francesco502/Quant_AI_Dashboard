# Quant-AI Dashboard Code Changes (`v2.0.0-alpha.1`)

## Scope
This document records the release-hardening changes that align the repository with an internal pre-release instead of a final `v2.0.0`.

## Version Baseline Alignment
- `core/version.py`
  - Updated runtime version from `2.0.0` to `2.0.0-alpha.1`
  - Added `prerelease` metadata
- `web/package.json`
  - Updated frontend package version to `2.0.0-alpha.1`
- `web/package-lock.json`
  - Updated root package version metadata to `2.0.0-alpha.1`

## Documentation Alignment
- `README.md`
  - Updated the displayed project version to `v2.0.0-alpha.1`
  - Pointed release document links to alpha release docs
- `api/README.md`
  - Updated API version heading and release doc links
- `web/README.md`
  - Updated frontend version heading and release doc links
- `tests/README.md`
  - Updated smoke-test version references to `v2.0.0-alpha.1`

## Test Alignment
- `tests/test_v3_smoke.py`
  - Updated the version expectation to `2.0.0-alpha.1`

## Deployment Metadata Alignment
- `docker-compose.yml`
  - Updated image tag and header comment to `v2.0.0-alpha.1`
- `Dockerfile.optimized`
  - Updated image header comment to `v2.0.0-alpha.1`

## Repository Hygiene
- `.gitignore`
  - Added ignores for external reference repositories
  - Added ignores for model artifacts, runtime output, coverage output, frontend build output, and abnormal local files

## Release Positioning
- This alpha reflects a large integrated local worktree, not a final public release
- Final `v2.0.0` remains gated on repository cleanup, validation, CI evidence, and tagging

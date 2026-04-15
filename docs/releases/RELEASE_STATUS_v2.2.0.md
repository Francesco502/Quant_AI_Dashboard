# Release Status `v2.2.0`

## Current Position

- Release line: `v2.2.0`
- Status: `released`
- Deployment target: optimized single-image Docker deployment with frontend on `8686` and backend API on `8685`
- Release date: `2026-04-15`

## Completed Release-Engineering Scope

- Local quickstart, deployment, development, and release docs were aligned to the current runtime model.
- The external release gate now uses a single canonical script: `python scripts/release_check.py`.
- CI release validation was updated to run the same external release gate as local sign-off.
- Generated validation output now lives under ignored output paths.

## Current Evidence

Confirmed locally on the current candidate:

1. `python scripts/release_check.py`
2. `output/reports/release_check_report.txt` reports `ready: yes`

## Release Evidence

1. `python -m compileall -q api core tests`
2. `python -m pytest tests/unit -q`
3. `python -m pytest tests/integration -q`
4. `cd web && npm run lint`
5. `cd web && npm run build`
6. `python scripts/release_check.py`
7. `output/reports/release_check_report.txt` reports `ready: yes`

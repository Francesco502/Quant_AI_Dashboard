# Release Status `v2.2.1`

## Current Position

- Release line: `v2.2.1`
- Status: `candidate`
- Deployment target: optimized single-image Docker deployment with frontend on `8686` and backend API on `8685`
- Candidate date: `2026-04-27`

## Completed Scope

- Daily decision workbench and workflow navigation.
- Data freshness and source trust checks before high-impact analysis flows.
- Unified operation audit for the core personal research loop.
- Backup/download/restore and asset CSV import.
- Tightened API contracts for the 2.2.1 workflow endpoints.
- Settings initialization and backup management.

## Required Release Evidence

1. `python -m compileall -q api core tests`
2. `python -m pytest tests/unit -q`
3. `python -m pytest tests/integration -q`
4. `python -m pytest tests/test_v3_smoke.py -q`
5. `cd web && npm run lint`
6. `cd web && npm run build`
7. Optional external gate with running services: `python scripts/release_check.py`

## Residual Notes

- External UI E2E remains opt-in because it requires running frontend/backend services.
- Automatic real-money trading remains out of scope; paper trading and manual review remain the intended workflow.

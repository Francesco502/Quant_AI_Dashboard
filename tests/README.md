# Test Guide

## Test Layout

- `tests/unit/`: unit coverage for backend services and helpers
- `tests/integration/`: API and service integration tests
- `tests/e2e/`: browser and external-service validation
- `tests/performance/`: optional benchmark-oriented checks
- `tests/test_v3_smoke.py`: lightweight release smoke test

## Common Commands

Run the main backend checks:

```powershell
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/test_v3_smoke.py -q
```

Run in-process E2E:

```powershell
python -m pytest tests/e2e -m "e2e_inprocess" -v
```

Run external release-style validation against already running frontend/backend services:

```powershell
python scripts/release_check.py
```

## Coverage

```powershell
python -m coverage run --source=core,api -m pytest tests/unit -q
python -m coverage xml
python -m coverage html
```

## Notes

- External E2E assumes the frontend is reachable on `8686` and the backend API on `8685` unless overridden through environment variables.
- The canonical external release suite is:
  - `tests/e2e/test_release_validation.py`
  - `tests/e2e/test_ui.py`
  - `tests/e2e/test_ui_auth_and_pages.py`
- Generated Playwright traces, screenshots, and reports belong under ignored output paths.

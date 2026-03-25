# Development

## Repository Layout

- `api/`: HTTP routers, auth, schemas, API entrypoint
- `core/`: data services, trading engine, daemon, indicators, strategy logic
- `web/`: application UI
- `tests/`: automated validation
- `docs/`: current docs, release history, and archives

## Runtime State

Primary local state is stored under `data/`. Treat it as runtime content, not as source material.

Important examples:

- `data/quant.db`: main application database
- `data/user_state.json`: local user-facing asset pool and related state
- `data/prices/`: cached market and fund data

Do not delete these unless you intentionally want to reset local runtime state.

## Generated Output

The following are disposable and should stay out of source control:

- logs
- caches
- coverage reports
- scratch output
- exported frontend build output

## Script Conventions

- `start.ps1` is the primary local launcher
- `start_dashboard.ps1`, `start.bat`, and `start_dashboard.bat` are compatibility wrappers
- `docker-compose.yml` is the primary deployment entrypoint

## Documentation Policy

- Add active operational guidance under `docs/current/`
- Add release-specific material under `docs/releases/`
- Move superseded planning and analysis content under `docs/archive/`

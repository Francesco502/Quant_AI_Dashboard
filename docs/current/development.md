# Development

## Repository Layout

- `api/`: HTTP routers, auth, schemas, and API entrypoints
- `core/`: data services, trading engine, daemon, indicators, and strategy logic
- `web/`: Next.js application UI
- `tests/`: automated validation
- `docs/`: current docs, release history, and archives

## Runtime State

Primary local state is stored under `data/`. Treat it as runtime content, not as source material.

Important examples:

- `data/quant.db`: main application database
- `data/user_state.json`: local asset-pool and related user state
- `data/prices/`: cached market and fund data

Do not delete these unless you intentionally want to reset local runtime state.

## Generated Output

The following are disposable and should stay out of source control:

- `output/`
- `.playwright-cli/`
- `tmp/`
- logs
- coverage reports
- build caches
- exported frontend build output

## Entry Points

- `docker-compose.yml` is the primary deployment entrypoint
- local development should use explicit backend/frontend commands from `docs/current/quickstart.md`
- release validation should use `python scripts/release_check.py`

## Documentation Policy

- add active operational guidance under `docs/current/`
- add versioned release material under `docs/releases/`
- move superseded planning and analysis content under `docs/archive/`

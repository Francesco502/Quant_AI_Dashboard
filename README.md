# Quant-AI Dashboard

Personal quantitative analysis, paper trading, strategy research, and decision-support workspace.

Current release line: **v3.0.0**

## Repository Layout

- `api/`: FastAPI backend
- `core/`: trading, data, strategy, daemon, and monitoring services
- `web/`: Next.js frontend
- `tests/`: unit, integration, smoke, and end-to-end validation
- `docs/current/`: active operating guides
- `docs/releases/`: versioned release notes and upgrade history
- `docs/archive/`: historical plans and superseded material

## Start Here

- Local quickstart: [`docs/current/quickstart.md`](./docs/current/quickstart.md)
- Deployment guide: [`docs/current/deployment.md`](./docs/current/deployment.md)
- Release guide: [`docs/current/release.md`](./docs/current/release.md)
- Development guide: [`docs/current/development.md`](./docs/current/development.md)
- Documentation index: [`docs/README.md`](./docs/README.md)
- Latest release notes: [`docs/releases/RELEASE_NOTES_v3.0.0.md`](./docs/releases/RELEASE_NOTES_v3.0.0.md)

## Local Development

Backend:

```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8685 --reload
```

Frontend:

```powershell
cd web
npm install
npm run dev
```

Optional daemon:

```powershell
python -m core.daemon
```

## Access

- Frontend: [http://localhost:8686](http://localhost:8686)
- API docs: [http://localhost:8685/docs](http://localhost:8685/docs)
- Health: [http://localhost:8685/api/health](http://localhost:8685/api/health)

## Validation

Core checks:

```powershell
python -m compileall -q api core tests
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/test_v3_smoke.py -q
python scripts/deployment_readiness_check.py --strict
```

Frontend checks:

```powershell
cd web
npm run lint
npm run build
```

Release validation against running frontend/backend services:

```powershell
python scripts/release_check.py
```

The generated release report is written to `output/reports/release_check_report.txt`.

## Deployment

Canonical production deployment is Docker Compose:

```powershell
docker compose up -d --build
docker compose -f docker-compose.worker.yml --profile scan --profile backtest up -d --build
```

See [`docs/current/deployment.md`](./docs/current/deployment.md) for runtime environment, volumes, published ports, and post-deploy checks.

## Notes

- Runtime state under `data/` is not source material.
- Generated output such as `output/`, coverage reports, Playwright traces, and temporary scratch files should stay out of source control.
- Automatic trading remains disabled by default and must be explicitly enabled through runtime configuration.
- v3.0.0 defaults LLM integration to DeepSeek-compatible `deepseek-v4-flash`; configure `DEEPSEEK_API_KEY` or `DS_API_KEY` before release validation.
- Rust native kernels are optional and only built when `INSTALL_NATIVE_KERNEL=true`; Python fallback remains supported.

# Quant-AI Dashboard

Personal quantitative analysis, paper trading, strategy research, and decision-support workspace.

Current release: **v2.1.0**

## What This Repo Contains

- `api/`: FastAPI backend
- `core/`: trading, data, strategy, and system services
- `web/`: Next.js frontend
- `tests/`: unit, integration, and end-to-end coverage
- `docs/current/`: current operating guides
- `docs/releases/`: release notes, upgrade guides, and release status history
- `docs/archive/`: historical plans, legacy guides, and superseded material

## Current Entry Points

- Local development startup: [`start.ps1`](./start.ps1)
- Local development quickstart: [`docs/current/quickstart.md`](./docs/current/quickstart.md)
- Canonical deployment guide: [`docs/current/deployment.md`](./docs/current/deployment.md)
- Documentation index: [`docs/README.md`](./docs/README.md)

## Local Development

### PowerShell launcher

```powershell
.\start.ps1
```

### Manual startup

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
- Health check: [http://localhost:8685/api/health](http://localhost:8685/api/health)

## Validation

Backend tests:

```powershell
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/test_v3_smoke.py -q
```

Frontend checks:

```powershell
cd web
npm run lint
npm run build
```

## Notes

- This repository keeps primary runtime state under `data/`; generated logs, caches, and scratch output are intentionally excluded from source control.
- Production deployment is standardized on [`docker-compose.yml`](./docker-compose.yml), which builds [`Dockerfile.optimized`](./Dockerfile.optimized).
- Historical duplicated guides were moved under [`docs/archive/`](./docs/archive/).

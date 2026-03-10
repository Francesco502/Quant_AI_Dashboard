# Quant-AI Dashboard

Personal quantitative analysis and learning system (**v1.0.0**).

## Positioning
- Personal research and decision support.
- Paper trading and backtesting only.
- Manual execution only (no automatic real-money trading).
- Daily timeframe focus.

## Tech Stack
- Backend: FastAPI + Python 3.10+
- Frontend: Next.js 16 + React 19
- Storage: SQLite + local data files

## Local Development

### 1) Backend
```bash
python -m uvicorn api.main:app --reload --port 8685
```

### 2) Frontend
```bash
cd web
npm install
npm run dev
```

### 3) Access
- Frontend: [http://localhost:8686](http://localhost:8686)
- API Docs: [http://localhost:8685/docs](http://localhost:8685/docs)
- Health: [http://localhost:8685/api/health](http://localhost:8685/api/health)

## Testing
```bash
# Python tests
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v

# Frontend lint
cd web
npm run lint
```

## Release Documents (v1.0.0)
- Release notes: [`docs/RELEASE_NOTES_v1.0.0.md`](docs/RELEASE_NOTES_v1.0.0.md)
- Code change log: [`docs/CODE_CHANGES_v1.0.0.md`](docs/CODE_CHANGES_v1.0.0.md)

## Deployment Notes (2C/2G)
- Runtime image uses `requirements.runtime.txt` (lean baseline).
- Heavy models are disabled by default via `DISABLE_HEAVY_MODELS=true` in optimized container flow.
- Optional heavy dependencies are commented in `requirements.runtime.txt` and should be enabled only when required.

## Safety Principle
Automatic trading is hard-disabled in code. Daemon scheduling is manual-analysis only.

# Quickstart

## Prerequisites

- Python 3.11 recommended
- Node.js 20 recommended
- npm 10+
- Optional: a virtual environment under `.venv/`

## Fastest Local Start

From the repository root:

```powershell
.\start.ps1
```

This launches:

- FastAPI backend on `8685`
- background daemon on the default daemon config
- Next.js frontend on `8686`

## Manual Startup

Backend:

```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8685 --reload
```

Daemon:

```powershell
python -m core.daemon
```

Frontend:

```powershell
cd web
npm install
npm run dev
```

## Access URLs

- Frontend: [http://localhost:8686](http://localhost:8686)
- API docs: [http://localhost:8685/docs](http://localhost:8685/docs)
- Health: [http://localhost:8685/api/health](http://localhost:8685/api/health)

## Login Notes

- Admin creation depends on `APP_LOGIN_PASSWORD` or `APP_LOGIN_PASSWORD_HASH`
- The default admin username is `admin` unless `APP_ADMIN_USERNAME` is set
- If no login password is configured, the backend may run in a local development mode depending on environment

## Recommended Checks

```powershell
python -m pytest tests/test_v3_smoke.py -q
python -m pytest tests/integration -q

cd web
npm run lint
npm run build
```

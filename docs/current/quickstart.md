# Quickstart

## Prerequisites

- Python 3.11 recommended
- Node.js 20 recommended
- npm 10+
- Optional local virtual environment under `.venv/`

## Local Startup

Start services explicitly from the repository root.

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

## Access URLs

- Frontend: [http://localhost:8686](http://localhost:8686)
- API docs: [http://localhost:8685/docs](http://localhost:8685/docs)
- Health: [http://localhost:8685/api/health](http://localhost:8685/api/health)

## Login Notes

- Default admin username is `admin` unless `APP_ADMIN_USERNAME` is set.
- Set `APP_LOGIN_PASSWORD` or `APP_LOGIN_PASSWORD_HASH` before expecting browser login to work.
- Local development may appear to start successfully even when login credentials are missing, so always verify `/login` after boot.

## Recommended Checks

```powershell
python -m pytest tests/test_v3_smoke.py -q
python -m pytest tests/integration -q

cd web
npm run lint
npm run build
```

For release-style validation against already running services:

```powershell
python scripts/release_check.py
```

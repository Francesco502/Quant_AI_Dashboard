# Quant-AI Dashboard API (v2.0.0-alpha.1)

FastAPI backend for the personal research and paper-trading workflow.

## Local Run
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8685 --reload
```

## Local URLs
- Swagger: [http://localhost:8685/docs](http://localhost:8685/docs)
- ReDoc: [http://localhost:8685/redoc](http://localhost:8685/redoc)
- Health: [http://localhost:8685/api/health](http://localhost:8685/api/health)

## Auth
Most `/api/*` endpoints are protected by bearer token middleware.

### Get token
```bash
curl -X POST http://localhost:8685/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

### Call protected endpoint
```bash
curl http://localhost:8685/api/backtest/strategies \
  -H "Authorization: Bearer <TOKEN>"
```

## Main Route Groups
- `/api/auth/*` authentication
- `/api/backtest/*` strategy backtest/optimization
- `/api/trading/*` paper trading and execution
- `/api/portfolio/*` portfolio analysis and decision payloads
- `/api/user/*` user watchlist/preferences/strategy config
- `/api/monitoring/*` health and metrics
- `/api/stz/*` market scan and selector runs

## Frontend Port Alignment
- Frontend dev server runs on `http://localhost:8686` (`web/package.json`).
- Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8685/api` for local development.

## Versioned Release Docs
- `../docs/RELEASE_NOTES_v2.0.0-alpha.1.md`
- `../docs/CODE_CHANGES_v2.0.0-alpha.1.md`

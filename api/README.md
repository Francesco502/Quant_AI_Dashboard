# Quant-AI Dashboard API

FastAPI backend for the Quant-AI Dashboard `v2.1.3` workspace.

## Responsibilities

- authentication and user session APIs
- asset pool and personal asset management
- market review, prediction, and LLM decision APIs
- backtesting, paper trading, and automatic paper-trading control
- monitoring, health, and system status endpoints

## Local Run

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8685 --reload
```

## Local URLs

- Swagger: [http://localhost:8685/docs](http://localhost:8685/docs)
- ReDoc: [http://localhost:8685/redoc](http://localhost:8685/redoc)
- Health: [http://localhost:8685/api/health](http://localhost:8685/api/health)

## Authentication

Most `/api/*` endpoints require a bearer token.

### Get a token

```bash
curl -X POST http://localhost:8685/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=<your-configured-password>"
```

### Call a protected endpoint

```bash
curl http://localhost:8685/api/backtest/strategies \
  -H "Authorization: Bearer <TOKEN>"
```

## Main Route Groups

- `/api/auth/*`: authentication and user management
- `/api/backtest/*`: strategy backtest and optimization
- `/api/trading/*`: paper trading and automatic trading control
- `/api/portfolio/*`: portfolio analysis and decision payloads
- `/api/user/*`: user preferences, assets, and settings
- `/api/monitoring/*`: health and monitoring
- `/api/stz/*`: market scan, selector runs, and asset pool
- `/api/llm-analysis/*`: LLM dashboard analysis
- `/api/agent/*`: agent workflows

## Frontend Alignment

- local frontend default: `http://localhost:8686`
- local API base: `http://127.0.0.1:8685/api`
- production single-image deployment proxies the frontend and API through one container entrypoint

## Canonical Docs

- project index: [../README.md](../README.md)
- current docs: [../docs/current/README.md](../docs/current/README.md)
- deployment: [../docs/current/deployment.md](../docs/current/deployment.md)
- releases: [../docs/releases/](../docs/releases/)

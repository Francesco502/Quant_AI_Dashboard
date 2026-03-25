# Deployment

## Canonical Deployment Path

Use [`docker-compose.yml`](../../docker-compose.yml), which builds [`Dockerfile.optimized`](../../Dockerfile.optimized).

This is the standard `v2.1.0` full-stack single-image deployment path for the repository. One image contains:

- static frontend served by Nginx
- FastAPI backend served by Uvicorn
- optional daemon process under Supervisor

## Start

```bash
docker compose up -d --build
```

## Direct Single-Image Build

```bash
docker build -f Dockerfile.optimized -t quant-ai-dashboard:2.1.0 .
```

## Direct Single-Image Run

```bash
docker run -d \
  --name quant-ai-dashboard \
  -p 8686:80 \
  -p 8685:8685 \
  -e SECRET_KEY=change-me \
  -e APP_LOGIN_PASSWORD=change-me \
  -e CORS_ORIGINS=http://localhost:8686 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/strategies:/app/strategies \
  quant-ai-dashboard:2.1.0
```

## Stop

```bash
docker compose down
```

## Logs

```bash
docker compose logs -f
```

## Published Ports

- `8686`: frontend via Nginx
- `8685`: backend API, exposed for direct debugging and API access

## Persistent Volumes

- `./data`
- `./logs`
- `./strategies`
- `./models`

## Required Environment

Set these through `.env` or your deployment platform:

- `SECRET_KEY`
- `APP_LOGIN_PASSWORD` or `APP_LOGIN_PASSWORD_HASH`
- `CORS_ORIGINS` or same-origin deployment configuration
- `TUSHARE_TOKEN` when using Tushare
- `ALPHA_VANTAGE_KEY` when using Alpha Vantage
- `OPENAI_API_KEY`, `DASHSCOPE_API_KEY`, `ARK_API_KEY`, or other model-provider keys as needed

## Notes

- `Dockerfile` remains available for backend-only or custom deployments, but it is not the default documented stack.
- Historical optimized deployment notes were moved to `docs/archive/legacy-guides/`.
- `Dockerfile.optimized` now bundles the frontend, backend, Supervisor, Nginx, and default runtime config files needed for a lightweight server deployment.

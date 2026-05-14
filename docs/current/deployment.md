# Deployment

## Canonical Deployment Path

Use [`docker-compose.yml`](../../docker-compose.yml), which builds [`Dockerfile.optimized`](../../Dockerfile.optimized).

This is the standard `v2.3.0` full-stack deployment path:

- frontend served on `8686`
- backend API exposed on `8685`
- optional daemon managed inside the same optimized image

## Start

```bash
docker compose up -d --build
```

## Stop

```bash
docker compose down
```

## Logs

```bash
docker compose logs -f
```

## Direct Single-Image Build

```bash
docker build -f Dockerfile.optimized -t quant-ai-dashboard:2.3.0 .
```

## Direct Single-Image Run

```bash
docker run -d \
  --name quant-ai-dashboard \
  -p 8686:80 \
  -p 8685:8685 \
  --env-file /opt/quant-ai-dashboard/.env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/strategies:/app/strategies \
  quant-ai-dashboard:2.3.0
```

## Published Ports

- `8686`: frontend
- `8685`: backend API

## Persistent Volumes

- `./data`
- `./logs`
- `./strategies`
- `./models`

## Required Runtime Environment

Set these through `.env` or the deployment platform:

- `SECRET_KEY`
- `APP_LOGIN_PASSWORD` or `APP_LOGIN_PASSWORD_HASH`
- `API_EXPECT_SAME_ORIGIN=true` for same-origin deployment, or explicit `CORS_ORIGINS`
- `TUSHARE_TOKEN` for A-share workflows
- model-provider keys such as `OPENAI_API_KEY`, `ARK_API_KEY`, `DASHSCOPE_API_KEY`, or equivalent

## Runtime Tuning

- `UVICORN_LIMIT_CONCURRENCY` defaults to `32` in the optimized image. Lower it for very tight hosts, or raise it if the dashboard serves multiple simultaneous browser sessions.

## Recommended Deployment Root

Keep `.env` next to `docker-compose.yml`, for example:

```text
/opt/quant-ai-dashboard/.env
/opt/quant-ai-dashboard/docker-compose.yml
```

## Post-Deploy Verification

```bash
curl -f http://127.0.0.1:8685/api/health
curl -f http://127.0.0.1:8686/login
```

Then verify in browser:

- `/login`
- `/`
- `/portfolio`
- `/trading`
- `/backtest`
- `/dashboard-llm`
- `/daily-workbench`
- `/settings`

## Release Validation

Before publishing a candidate, start the frontend and backend on the standard local ports and run:

```bash
python scripts/release_check.py
```

The report is written to `output/reports/release_check_report.txt`.

## Notes

- `Dockerfile.optimized` is the canonical release image.
- `Dockerfile` remains available for backend-only or custom deployment flows.
- Historical deployment notes were moved to `docs/archive/legacy-guides/`.

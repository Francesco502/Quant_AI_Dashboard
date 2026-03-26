# Deployment

## Canonical Deployment Path

Use [`docker-compose.yml`](../../docker-compose.yml), which builds [`Dockerfile.optimized`](../../Dockerfile.optimized).

This is the standard `v2.1.4` full-stack single-image deployment path for the repository. One image contains:

- static frontend served by Nginx
- FastAPI backend served by Uvicorn
- optional daemon process under Supervisor

## Start

```bash
docker compose up -d --build
```

## Direct Single-Image Build

```bash
docker build -f Dockerfile.optimized -t quant-ai-dashboard:2.1.4 .
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
  quant-ai-dashboard:2.1.4
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

## Recommended `.env` Location

For Docker Compose deployment, put `.env` next to [`docker-compose.yml`](../../docker-compose.yml), for example:

```text
/opt/quant-ai-dashboard/.env
/opt/quant-ai-dashboard/docker-compose.yml
```

This keeps the deployed image version, volume mounts, and runtime secrets in one deployment root.

If you run the image directly with `docker run`, keep the file in the same deployment root and pass it explicitly:

```bash
docker run --env-file /opt/quant-ai-dashboard/.env ...
```

Minimal example:

```dotenv
TZ=Asia/Shanghai
APP_TIMEZONE=Asia/Shanghai
SECRET_KEY=replace-with-random-secret
APP_LOGIN_PASSWORD=replace-with-strong-password
API_EXPECT_SAME_ORIGIN=true
TUSHARE_TOKEN=your_tushare_token
ALPHA_VANTAGE_KEY=your_alpha_vantage_key
LLM_PROVIDER=openai_compat
ARK_API_KEY=your_volcengine_ark_api_key
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
OPENAI_MODEL=doubao-seed-1-6-thinking
```

`2.1.4` defaults to Beijing time in Docker deployment. Keep `TZ=Asia/Shanghai` and `APP_TIMEZONE=Asia/Shanghai` unless you intentionally want daemon scheduling and dashboard timestamps to follow another timezone.

For A-share auto trading, do not leave market data to AkShare alone. Provide a working `TUSHARE_TOKEN`, or preload local price history into `/app/data`; otherwise the daemon can start normally but manual and scheduled auto-trading runs may stop with `No market data available for auto-trading universe`.

## Release Security Gate

Production deployment must explicitly choose one browser-origin model:

- same-origin routing: set `API_EXPECT_SAME_ORIGIN=true`
- explicit cross-origin routing: set `CORS_ORIGINS=https://your-frontend-domain`

If neither is configured correctly, the service can still start, but `/api/health` will report `security.ready=false` and strict production validation can fail startup.

## Notes

- `Dockerfile` remains available for backend-only or custom deployments, but it is not the default documented stack.
- Historical optimized deployment notes were moved to `docs/archive/legacy-guides/`.
- `Dockerfile.optimized` now bundles the frontend, backend, Supervisor, Nginx, and default runtime config files needed for a lightweight server deployment.

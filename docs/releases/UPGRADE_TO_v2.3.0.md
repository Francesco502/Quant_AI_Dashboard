# Upgrade To `v2.3.0`

## What Changes

- `v2.3.0` is a release-hardening update for the current Next.js 16 and FastAPI stack.
- The standard local ports remain frontend `8686` and backend `8685`.
- Paper trading remains manual/simulated by default; automatic real-money trading remains unavailable.

## Upgrade Steps

### 1. Backup Runtime State

```bash
mkdir -p /opt/backup/quant-ai-$(date +%F)
cp -r data /opt/backup/quant-ai-$(date +%F)/data
cp -r logs /opt/backup/quant-ai-$(date +%F)/logs || true
cp .env /opt/backup/quant-ai-$(date +%F)/.env || true
```

### 2. Pull Code And Checkout Release

```bash
git fetch --all --tags
git checkout v2.3.0
```

### 3. Review Required Environment

Ensure these are set in `.env` or the deployment platform:

- `SECRET_KEY`
- `APP_LOGIN_PASSWORD` or `APP_LOGIN_PASSWORD_HASH`
- `API_EXPECT_SAME_ORIGIN=true` or explicit `CORS_ORIGINS`
- optional provider keys such as `TUSHARE_TOKEN`, `OPENAI_API_KEY`, `ARK_API_KEY`, `DASHSCOPE_API_KEY`

Optional LLM tuning:

- `LLM_REQUEST_TIMEOUT_SECONDS` defaults to `15`
- `LLM_MAX_RETRIES` defaults to `0`

### 4. Rebuild And Restart

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

### 5. Post-Upgrade Verification

```bash
curl -f http://127.0.0.1:8685/api/health
curl -f http://127.0.0.1:8686/login
```

Then verify in browser:

- `/`
- `/portfolio`
- `/trading`
- `/backtest`
- `/dashboard-llm`
- `/daily-workbench`
- `/settings`

### 6. Optional Local Release Validation

```bash
python -m playwright install chromium
python scripts/release_check.py
```

## Compatibility Notes

- `v2.3.0` preserves the current SQLite/runtime layout under normal compose-based upgrades.
- Keep `data/`, `logs/`, `models/`, and `strategies/` mounted as persistent volumes.

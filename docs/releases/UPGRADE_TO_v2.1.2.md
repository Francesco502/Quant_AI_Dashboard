# Upgrade To `v2.1.2`

## What Changes

- Version bump from `2.1.1` to `2.1.2`.
- Optimized single-image Docker packaging no longer depends on a local ignored `daemon_config.json`.
- Optimized image builds now export the frontend statically during the Docker build.
- CI explicitly validates the optimized release image before release validation.

## Server Upgrade From `2.1.1` To `2.1.2`

### 1) Backup Before Upgrade

```bash
mkdir -p /opt/backup/quant-ai-$(date +%F)
cp -r data /opt/backup/quant-ai-$(date +%F)/data
cp -r logs /opt/backup/quant-ai-$(date +%F)/logs || true
cp .env /opt/backup/quant-ai-$(date +%F)/.env || true
```

### 2) Pull Code And Checkout Release

```bash
git fetch --all --tags
git checkout v2.1.2
```

### 3) Review Required Environment

Ensure these are set in `.env` (or deployment platform):

- `SECRET_KEY`
- `APP_LOGIN_PASSWORD` or `APP_LOGIN_PASSWORD_HASH`
- `API_EXPECT_SAME_ORIGIN` or explicit `CORS_ORIGINS`
- optional provider keys (`TUSHARE_TOKEN`, `ALPHA_VANTAGE_KEY`, model keys)

### 4) Rebuild And Restart (Docker Compose Path)

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

### 5) Post-Upgrade Verification

```bash
curl -f http://127.0.0.1:8685/api/health
```

Then verify in browser:

- `http://<server>:8686/login`
- `http://<server>:8686/portfolio`
- `http://<server>:8686/trading`
- `http://<server>:8686/backtest`

### 6) Optional Manual Release Validation

In GitHub Actions, run workflow **CI - Run Tests with Coverage** manually using **Run workflow**.

## Compatibility Notes

- Upgrade from `2.1.1` to `2.1.2` does not require destructive SQLite migration.
- Existing user assets, runtime config, and trading data are preserved under normal compose-based upgrade.

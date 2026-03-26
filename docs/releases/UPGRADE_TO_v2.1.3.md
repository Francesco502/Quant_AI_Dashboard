# Upgrade To `v2.1.3`

## What Changes

- Version bump from `2.1.2` to `2.1.3`.
- Clean-checkout environments now include the tracked `core.data.external` package required by CI and runtime imports.
- Release metadata and deployment references are updated to `v2.1.3`.

## Server Upgrade From `2.1.2` To `2.1.3`

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
git checkout v2.1.3
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

In GitHub Actions, inspect workflow **CI - Run Tests with Coverage** for the green run associated with the `2.1.3` release baseline.

## Compatibility Notes

- Upgrade from `2.1.2` to `2.1.3` does not require destructive SQLite migration.
- Existing user assets, runtime config, and trading data are preserved under normal compose-based upgrade.

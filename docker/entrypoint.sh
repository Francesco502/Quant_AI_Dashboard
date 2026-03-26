#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

log_info "========================================"
log_info "Quant-AI Dashboard v2.1.4 single-image startup"
log_info "========================================"

export ENABLE_DAEMON="${ENABLE_DAEMON:-true}"
export DISABLE_HEAVY_MODELS="${DISABLE_HEAVY_MODELS:-true}"
export TZ="${TZ:-Asia/Shanghai}"
export APP_TIMEZONE="${APP_TIMEZONE:-${TZ}}"

log_info "ENABLE_DAEMON=${ENABLE_DAEMON}"
log_info "DISABLE_HEAVY_MODELS=${DISABLE_HEAVY_MODELS}"
log_info "TZ=${TZ}"

if [ -f "/usr/share/zoneinfo/${TZ}" ]; then
    ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime
    echo "${TZ}" >/etc/timezone
fi

mkdir -p /app/data/prices /app/data/models /app/data/accounts /app/data/signals
mkdir -p /app/logs /app/strategies /app/models
mkdir -p /var/log/supervisor /var/log/nginx

if ! python -c "import fastapi" >/dev/null 2>&1; then
    log_error "FastAPI is not available in the runtime image."
    exit 1
fi

if ! nginx -t >/dev/null 2>&1; then
    log_error "Nginx configuration validation failed."
    exit 1
fi

log_info "Runtime preflight passed."
log_info "Starting Nginx + Uvicorn + optional daemon under supervisord..."

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf

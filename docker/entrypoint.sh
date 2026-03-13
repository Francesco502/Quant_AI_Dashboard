#!/bin/bash
# ============================================================
# Quant-AI Dashboard v3.0.0 — 单容器入口脚本
# ============================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

log_info "========================================"
log_info "Quant-AI Dashboard v3.0.0（单容器模式）"
log_info "========================================"

# ---------- 环境变量默认值 ----------
export ENABLE_DAEMON=${ENABLE_DAEMON:-true}
export DISABLE_HEAVY_MODELS=${DISABLE_HEAVY_MODELS:-true}

log_info "ENABLE_DAEMON        = ${ENABLE_DAEMON}"
log_info "DISABLE_HEAVY_MODELS = ${DISABLE_HEAVY_MODELS}"

# ---------- 创建运行时目录 ----------
mkdir -p /app/data/prices /app/data/models /app/data/accounts /app/data/signals
mkdir -p /app/logs /app/strategies /app/models
mkdir -p /var/log/supervisor /var/log/nginx

# ---------- 预检 ----------
if ! python -c "import fastapi" 2>/dev/null; then
    log_error "FastAPI 未安装"; exit 1
fi
if ! nginx -t 2>/dev/null; then
    log_error "Nginx 配置检查失败"; exit 1
fi
log_info "预检通过"

# ---------- 启动 ----------
log_info "通过 supervisord 启动 Nginx + Uvicorn + Daemon ..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf

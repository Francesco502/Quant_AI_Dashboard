#!/bin/bash
# ============================================================
# Quant-AI Dashboard 优化版一键启动脚本
# 适用于 2核2GB 低端服务器
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ============================================================
# 日志函数
# ============================================================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# ============================================================
# 检查系统资源
# ============================================================
check_resources() {
    log_step "检查系统资源..."
    
    # 检查 CPU
    CPU_CORES=$(nproc)
    log_info "CPU 核心数: $CPU_CORES"
    
    # 检查内存
    if command -v free &> /dev/null; then
        TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
        AVAILABLE_MEM=$(free -m | awk '/^Mem:/{print $7}')
        log_info "内存总量: ${TOTAL_MEM}MB"
        log_info "可用内存: ${AVAILABLE_MEM}MB"
        
        if [ "$TOTAL_MEM" -lt 150
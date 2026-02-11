# ============================================================
# Quant-AI Dashboard - 后端 Dockerfile (FastAPI + Daemon)
# ============================================================
FROM python:3.11-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 使用国内 apt 镜像源（加速 & 减少网络问题）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt /app/requirements.txt

# 安装 Python 依赖（使用国内镜像源加速）
RUN pip install --no-cache-dir \
    --timeout=300 \
    --retries=5 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

# 复制应用代码
COPY api/ /app/api/
COPY core/ /app/core/
COPY models/ /app/models/
COPY strategies/ /app/strategies/
COPY run_daemon.py /app/run_daemon.py
COPY set_password.py /app/set_password.py

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /app/models

# 暴露 API 端口
EXPOSE 8685

# 默认启动 API 服务（可通过 docker-compose command 覆盖为 daemon）
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8685", "--workers", "2"]

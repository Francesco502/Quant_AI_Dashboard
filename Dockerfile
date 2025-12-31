FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装系统依赖（包括 curl 用于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt /app/requirements.txt

# 安装 Python 依赖（使用国内镜像源加速，增加超时时间）
RUN pip install --no-cache-dir \
    --timeout=300 \
    --retries=5 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

# 复制应用代码
COPY . /app

# 创建必要的目录（如果不存在）
RUN mkdir -p /app/data /app/logs /app/.streamlit

# 暴露 Dashboard 端口（Daemon 不需要暴露端口）
EXPOSE 8501

# 默认启动 Dashboard（可通过 docker-compose command 覆盖为 daemon）
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]



# Quant-AI Dashboard 优化版部署指南 (2核2GB服务器)

本文档指导如何在 **2核2GB** 配置的低端服务器上部署 Quant-AI Dashboard 量化交易系统。

## 优化亮点

- **单容器部署**：合并 backend + frontend + nginx 到单个容器
- **内存优化**：Uvicorn 单 worker 模式，限制并发连接数
- **静态导出**：前端使用纯静态 HTML，无需 Node.js 运行时
- **连接池**：SQLite 连接池限制 2 个连接
- **LRU 缓存**：自动缓存热点数据
- **按需加载**：ML 模型（Prophet/XGBoost）懒加载

## 预期资源占用

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 内存占用 | ~3-4GB | **~1-1.5GB** |
| 启动时间 | 30-60s | **10-15s** |
| Docker 服务数 | 4-5个 | **1个** |

## 快速开始

### 1. 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- 2核 CPU / 2GB RAM / 20GB 磁盘

### 2. 使用优化版配置部署

```bash
# 克隆或进入项目目录
cd Quant_AI_Dashboard-main

# 使用优化版 Docker Compose 配置部署
docker-compose -f docker-compose.optimized.yml up -d --build

# 查看日志
docker logs -f quant-app

# 等待服务启动（约10-15秒）
# 访问 http://服务器IP:8686
```

### 3. 环境变量配置（可选）

创建 `.env` 文件：

```bash
# 核心优化参数
UVICORN_WORKERS=1
UVICORN_CONCURRENCY=10
SQLITE_POOL_SIZE=2
LAZY_LOAD_ML_MODELS=true
ENABLE_LRU_CACHE=true

# 应用配置
SECRET_KEY=your-secret-key-change-me
TUSHARE_TOKEN=your-tushare-token
APP_LOGIN_PASSWORD_HASH=your-password-hash
CORS_ORIGINS=http://localhost:8686
```

## 配置说明

### Docker 资源限制

在 `docker-compose.optimized.yml` 中已配置：

```yaml
deploy:
  resources:
    limits:
      cpus: '1.5'      # 限制 1.5 核
      memory: 1.5G     # 限制 1.5GB 内存
    reservations:
      cpus: '0.5'
      memory: 512M
```

### Uvicorn 优化参数

```bash
# 使用单 worker 模式
--workers 1

# 限制并发连接数
--limit-concurrency 10

# 使用 uvloop（更快的 asyncio 事件循环）
--loop uvloop

# 关闭访问日志（减少 I/O）
--no-access-log
```

### SQLite 连接池配置

```python
# 连接池大小（2核2GB建议2个连接）
pool_size=2

# 禁止溢出连接
max_overflow=0

# 连接超时
pool_timeout=30.0

# 查询超时
query_timeout=30
```

## 常用命令

```bash
# 启动服务
docker-compose -f docker-compose.optimized.yml up -d

# 停止服务
docker-compose -f docker-compose.optimized.yml down

# 查看日志
docker logs -f quant-app

# 进入容器
docker exec -it quant-app /bin/bash

# 重启服务
docker-compose -f docker-compose.optimized.yml restart

# 重建镜像
docker-compose -f docker-compose.optimized.yml up -d --build --force-recreate

# 查看资源占用
docker stats quant-app

# 清理未使用的镜像和卷
docker system prune -a --volumes
```

## 性能监控

### 查看健康状态

```bash
# API 健康检查
curl http://localhost:8686/api/health

# Nginx 健康检查
curl http://localhost:8686/health
```

### 查看缓存统计

```python
# 在 Python 控制台中
from core.lru_cache import get_cache_stats
print(get_cache_stats())

# 查看数据库连接池统计
from core.database_pool import get_pool_stats
print(get_pool_stats())
```

## 故障排除

### 问题：容器启动失败

```bash
# 查看详细日志
docker logs quant-app

# 检查端口占用
netstat -tulpn | grep 8686

# 重启 Docker 服务
sudo systemctl restart docker
```

### 问题：内存不足

```bash
# 查看内存使用
docker stats --no-stream

# 增加交换空间
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 问题：数据库锁定

```bash
# 进入容器检查
sudo docker exec -it quant-app sqlite3 /app/data/quant.db

# 在 SQLite 中
PRAGMA busy_timeout = 30000;
.tables
```

## 回滚到原版

如果需要使用原版多容器部署：

```bash
# 停止优化版
docker-compose -f docker-compose.optimized.yml down

# 启动原版
docker-compose -f docker-compose.yml up -d
```

## 进一步优化建议

1. **启用 Swap**：2GB 内存对于 Python 应用较紧张，建议启用 2-4GB Swap
2. **使用 CDN**：将静态资源放到 CDN，减少服务器压力
3. **数据库分离**：如果数据量大，考虑将 SQLite 迁移到独立的数据库服务器
4. **定时任务外置**：将 daemon 放到其他机器或云服务上执行
5. **监控告警**：部署 Prometheus + Grafana 监控资源使用

## 技术支持

如有问题，请提交 Issue 或联系技术支持。

---

**文档版本**: v1.0  
**最后更新**: 2025-01-20  
**适用系统**: Quant-AI Dashboard v3.0.0+

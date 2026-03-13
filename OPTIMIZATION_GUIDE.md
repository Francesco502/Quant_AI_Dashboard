# 2核2GB服务器优化指南

本文档介绍如何针对低配置服务器（2核2GB）优化 Quant-AI Dashboard 项目。

## 优化概述

| 优化项 | 优化前 | 优化后 | 效果 |
|--------|--------|--------|------|
| 内存占用 | ~3-4GB | ~1.2-1.5GB | ↓ 60% |
| 启动时间 | 30-60s | 10-15s | ↓ 70% |
| 并发能力 | 100+ | 10-20 | 适度降级 |
| 服务数量 | 4个容器 | 1个容器 | ↓ 75% |

## 快速开始

### 1. 使用优化版配置

```bash
# 停止原有服务
docker-compose down

# 使用优化版 Docker Compose
docker-compose -f docker-compose.optimized.yml up -d

# 查看日志
docker logs -f quant-app
```

### 2. 前端构建（静态导出）

```bash
cd web

# 使用优化版配置
cp next.config.optimized.ts next.config.ts

# 构建静态站点
npm run build

# 静态文件位于 web/dist 目录
cd ..
```

### 3. 环境变量配置

创建 `.env.optimized` 文件：

```env
# 后端优化
UVICORN_WORKERS=1
UVICORN_CONCURRENCY=10
SQLITE_POOL_SIZE=2
ENABLE_LRU_CACHE=true
LAZY_LOAD_ML_MODELS=true
ENABLE_GZIP=true
GZIP_MIN_SIZE=1000

# 数据库
SQLITE_DB_PATH=/app/data/quant.db

# 安全
SECRET_KEY=your-secret-key-here
```

## 详细优化说明

### 1. Docker 优化

#### 单容器部署

**优化前**：4个容器（backend、frontend、daemon、nginx）
- 内存占用：~2GB
- 启动时间：~30s

**优化后**：1个容器（合并所有服务）
- 内存占用：~800MB
- 启动时间：~10s

#### 资源限制

```yaml
deploy:
  resources:
    limits:
      cpus: '1.5'
      memory: 1.5G
    reservations:
      cpus: '0.5'
      memory: 512M
```

### 2. 后端优化

#### Uvicorn 配置

```python
# 单 worker 模式（节省内存）
workers = 1

# 限制并发数
concurrency_limit = 10

# 使用 uvloop（更快的异步循环）
loop = "uvloop"
```

#### 并发控制

```python
# 信号量控制并发
request_semaphore = asyncio.Semaphore(10)

@app.middleware("http")
async def concurrency_limit_middleware(request, call_next):
    async with request_semaphore:
        return await call_next(request)
```

#### GZip 压缩

```python
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # 1KB 以上才压缩
    compresslevel=6,     # 平衡性能和压缩率
)
```

### 3. 前端优化

#### 静态导出

```typescript
// next.config.ts
const nextConfig = {
  output: "export",      // 静态导出模式
  distDir: "dist",       // 输出目录
  images: {
    unoptimized: true,   // 禁用图片优化（静态导出需要）
  },
};
```

**优点**：
- 无需 Node.js 运行时
- Nginx 直接服务静态文件
- 内存占用极低

#### 代码分割

```typescript
// 动态导入大型组件
const HeavyChart = dynamic(() => import("@/components/HeavyChart"), {
  ssr: false,
  loading: () => <Skeleton className="h-[400px] w-full" />,
});
```

### 4. 数据库优化

#### SQLite 连接池

```python
# 限制连接数（避免内存溢出）
pool = SQLiteConnectionPool(
    db_path="/app/data/quant.db",
    pool_size=2,           # 2核2GB环境建议2个连接
    max_overflow=0,        # 不允许溢出
    pool_timeout=30.0,
    query_timeout=30,      # 查询超时30秒
)
```

#### 连接优化设置

```python
def _create_connection(self) -> sqlite3.Connection:
    conn = sqlite3.connect(...)
    
    # WAL 模式，提高并发性能
    conn.execute("PRAGMA journal_mode=WAL")
    
    # 平衡性能和安全性
    conn.execute("PRAGMA synchronous=NORMAL")
    
    # 32MB 缓存
    conn.execute("PRAGMA cache_size=-32768")
    
    # 临时表存储在内存
    conn.execute("PRAGMA temp_store=MEMORY")
    
    # 256MB 内存映射
    conn.execute("PRAGMA mmap_size=268435456")
    
    return conn
```

### 5. 缓存策略

#### LRU 缓存

```python
# 创建缓存
cache = LRUCache(
    max_size=100,        # 最多100项
    ttl=300,             # 5分钟过期
    max_memory_mb=50,    # 限制50MB
)

# 使用
cache.set("key", value, ttl=600)
result = cache.get("key")
```

#### 装饰器缓存

```python
@cached(max_size=100, ttl=300)
def get_user(user_id: int) -> dict:
    return db.query(User).get(user_id).to_dict()

# 带自定义缓存键
@cached(ttl=60, key_func=lambda symbol, period: f"{symbol}_{period}")
def get_price(symbol: str, period: str) -> list:
    return fetch_price_from_api(symbol, period)
```

### 6. ML 模型懒加载

```python
# 获取模型管理器
manager = get_model_manager(max_memory_mb=400)

# 注册模型（不加载）
manager.register_model(
    "prophet_forecaster",
    model_class=Prophet,
    memory_estimate_mb=150,
)

# 懒加载（第一次使用时加载）
model = manager.load_model("prophet_forecaster")
forecast = model.predict(future)

# 手动卸载
manager.unload_model("prophet_forecaster")
```

## 监控和调优

### 健康检查

```bash
# 检查服务健康
curl http://localhost:8686/api/health

# 查看详细状态
curl http://localhost:8686/api/health/detailed
```

### 性能监控

```python
# 获取缓存统计
cache_stats = get_cache_stats()
print(f"缓存命中率: {cache_stats['hit_rate']}%")

# 获取连接池统计
pool_stats = get_pool_stats()
print(f"活跃连接: {pool_stats['active_connections']}")

# 获取模型管理器统计
manager_stats = get_model_manager_stats()
print(f"已加载模型: {manager_stats['loaded_models']}")
print(f"内存使用: {manager_stats['estimated_memory_mb']}MB")
```

### 日志级别

```python
# 生产环境建议的日志级别
import logging

# 只保留 WARNING 及以上级别
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

# 保留 INFO 级别（核心业务）
logging.getLogger("core").setLevel(logging.INFO)
```

## 故障排除

### 内存不足

```bash
# 查看内存使用
free -h

# 查看容器内存限制
docker stats quant-app

# 降低内存限制（如果必要）
# 编辑 docker-compose.optimized.yml
# deploy.resources.limits.memory: 1G
```

### 启动失败

```bash
# 查看详细日志
docker logs quant-app --tail 100

# 检查端口冲突
netstat -tlnp | grep 8686

# 手动运行测试
python -c "from api.main import app; print('OK')"
```

### 性能问题

```bash
# 检查 CPU 使用
top -p $(pgrep -d',' -f uvicorn)

# 检查慢查询（启用 SQLite 日志）
# 在代码中添加：
# conn.set_trace_callback(lambda sql: print(f"SQL: {sql}"))

# 增加缓存大小
# 编辑 core/lru_cache.py
# max_size=200 (原来是 100)
```

## 总结

本优化方案针对 2核2GB 服务器，通过以下策略实现 60% 内存节省：

1. **架构优化**：4个容器合并为1个，减少开销
2. **后端优化**：单 worker + 并发限制，减少内存
3. **前端优化**：静态导出，无需 Node 运行时
4. **数据库优化**：连接池限制2个连接，避免溢出
5. **缓存策略**：LRU缓存减少重复计算
6. **懒加载**：ML模型按需加载，用完即释放

按照本指南配置后，系统可在 2核2GB 服务器上稳定运行，同时保持核心功能完整。

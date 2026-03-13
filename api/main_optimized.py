"""
FastAPI 主应用 - 优化版 (2核2GB服务器专用)

优化点：
- 单 Uvicorn worker 模式
- 限制并发连接数
- 按需加载 ML 模型
- SQLite 连接池优化
- LRU 缓存
"""

import os
import asyncio
import gc
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .routers import (
    strategies,
    signals,
    data,
    forecasting,
    trading,
    models,
    accounts,
    stocktradebyz,
    backtest,
)
from .websocket_manager import WebSocketManager
from .auth import router as auth_router
from core.version import VERSION

logger = logging.getLogger(__name__)

# WebSocket 管理器
ws_manager = WebSocketManager()

# 全局配置（从环境变量读取）
UVICORN_WORKERS = int(os.getenv("UVICORN_WORKERS", "1"))
UVICORN_CONCURRENCY = int(os.getenv("UVICORN_CONCURRENCY", "10"))
LAZY_LOAD_ML_MODELS = os.getenv("LAZY_LOAD_ML_MODELS", "true").lower() == "true"
ENABLE_GZIP = os.getenv("ENABLE_GZIP", "true").lower() == "true"
GZIP_MIN_SIZE = int(os.getenv("GZIP_MIN_SIZE", "1000"))

# 信号量控制并发
request_semaphore = asyncio.Semaphore(UVICORN_CONCURRENCY)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理 - 优化版"""
    logger.info(f"API 服务启动中... (workers={UVICORN_WORKERS}, concurrency={UVICORN_CONCURRENCY})")
    
    # 如果启用懒加载，则不预加载 ML 模型
    if not LAZY_LOAD_ML_MODELS:
        logger.info("预加载 ML 模型...")
        # 这里可以添加模型预加载逻辑
    else:
        logger.info("启用 ML 模型懒加载模式")
    
    yield
    
    # 关闭时
    logger.info("API 服务关闭中...")
    gc.collect()  # 强制垃圾回收


# 创建 FastAPI 应用
app = FastAPI(
    title="Quant-AI Dashboard API",
    description="量化交易系统 API 接口 (优化版)",
    version=VERSION,
    lifespan=lifespan,
    # 限制请求体大小
    max_request_body_size=10 * 1024 * 1024,  # 10MB
)

# GZip 压缩中间件（必须在 CORS 之前）
if ENABLE_GZIP:
    app.add_middleware(
        GZipMiddleware,
        minimum_size=GZIP_MIN_SIZE,
        compresslevel=6,  # 平衡性能和压缩率
    )
    logger.info(f"启用 GZip 压缩 (min_size={GZIP_MIN_SIZE})")

# CORS 配置
_cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:8686,http://localhost:8685")
_cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # 限制允许的 HTTP 方法
    allow_headers=["Authorization", "Content-Type"],  # 限制允许的请求头
    max_age=600,  # 预检请求缓存 10 分钟
)


# 并发控制中间件
@app.middleware("http")
async def concurrency_limit_middleware(request, call_next):
    """限制并发请求数"""
    async with request_semaphore:
        response = await call_next(request)
        return response


# 注册路由
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["策略管理"])
app.include_router(signals.router, prefix="/api/signals", tags=["信号管理"])
app.include_router(data.router, prefix="/api/data", tags=["数据获取"])
app.include_router(forecasting.router, prefix="/api/forecasting", tags=["AI预测"])
app.include_router(trading.router, prefix="/api/trading", tags=["交易执行"])
app.include_router(models.router, prefix="/api/models", tags=["模型管理"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["账户管理"])
app.include_router(stocktradebyz.router, prefix="/api/stz", tags=["Z哥战法"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["策略回测"])


@app.get("/")
async def root():
    """API 根路径"""
    return {
        "message": "Quant-AI Dashboard API (优化版)",
        "version": VERSION,
        "docs": "/docs",
        "health": "/api/health",
        "config": {
            "workers": UVICORN_WORKERS,
            "concurrency": UVICORN_CONCURRENCY,
            "lazy_load_ml": LAZY_LOAD_ML_MODELS,
            "gzip": ENABLE_GZIP,
        }
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    import psutil
    
    # 获取系统资源使用情况
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "status": "healthy",
        "service": "quant-ai-api",
        "version": VERSION,
        "system": {
            "memory_used_percent": memory.percent,
            "memory_available_mb": memory.available // (1024 * 1024),
            "disk_used_percent": (disk.used / disk.total) * 100,
        },
        "config": {
            "workers": UVICORN_WORKERS,
            "concurrency": UVICORN_CONCURRENCY,
        }
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点"""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.send_personal_message(f"收到消息: {data}", websocket)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """信号实时推送 WebSocket"""
    await ws_manager.connect(websocket)
    try:
        while True:
            try:
                from core.signal_store import get_signal_store

                signal_store = get_signal_store()
                latest_signals = signal_store.get_latest_signals(n_days=1)

                if not latest_signals.empty:
                    signals_data = latest_signals.to_dict("records")
                    # 处理时间戳
                    for signal in signals_data:
                        if "timestamp" in signal:
                            ts = signal["timestamp"]
                            if hasattr(ts, "isoformat"):
                                signal["timestamp"] = ts.isoformat()
                            elif isinstance(ts, str):
                                pass
                    
                    await ws_manager.send_personal_message(
                        {"type": "signals_update", "data": signals_data}, websocket
                    )
            except Exception as e:
                logger.error(f"推送信号失败: {e}")

            await asyncio.sleep(5)  # 每5秒推送一次
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8685,
        workers=UVICORN_WORKERS,
        limit_concurrency=UVICORN_CONCURRENCY,
    )

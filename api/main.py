"""
FastAPI 主应用

提供量化交易系统的 RESTful API 和 WebSocket 接口
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
from typing import List, Dict, Optional
import logging

from .routers import (
    strategies,
    signals,
    data,
    forecasting,
    trading,
    models,
    accounts,
)
from .websocket_manager import WebSocketManager
from .auth import router as auth_router
from core.version import VERSION

logger = logging.getLogger(__name__)

# WebSocket 管理器
ws_manager = WebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("API 服务启动中...")
    yield
    # 关闭时
    logger.info("API 服务关闭中...")


# 创建 FastAPI 应用
app = FastAPI(
    title="Quant-AI Dashboard API",
    description="量化交易系统 API 接口",
    version=VERSION,  # 使用应用版本号
    lifespan=lifespan,
)

# CORS 配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["策略管理"])
app.include_router(signals.router, prefix="/api/signals", tags=["信号管理"])
app.include_router(data.router, prefix="/api/data", tags=["数据获取"])
app.include_router(forecasting.router, prefix="/api/forecasting", tags=["AI预测"])
app.include_router(trading.router, prefix="/api/trading", tags=["交易执行"])
app.include_router(models.router, prefix="/api/models", tags=["模型管理"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["账户管理"])


@app.get("/")
async def root():
    """API 根路径"""
    return {
        "message": "Quant-AI Dashboard API",
        "version": VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "quant-ai-api"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点"""
    await ws_manager.connect(websocket)
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            # 处理消息（可以根据消息类型分发）
            await ws_manager.send_personal_message(f"收到消息: {data}", websocket)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """信号实时推送 WebSocket"""
    await ws_manager.connect(websocket)
    try:
        # 定期推送最新信号
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
                                pass  # 已经是字符串
                    
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

    uvicorn.run(app, host="0.0.0.0", port=8000)


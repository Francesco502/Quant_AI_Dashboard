"""
FastAPI 主应用

提供量化交易系统的 RESTful API 和 WebSocket 接口
"""

# 最先加载 .env，确保后续 os.getenv 能读到配置
try:
    from dotenv import load_dotenv
    from pathlib import Path
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path)
except Exception:
    pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import os
from typing import List, Dict, Optional
import logging
import datetime
from urllib.parse import urlparse

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
    llm_analysis,
    market,
    agent,
    portfolio,
    scanner,
    user_config,
    user_assets,
    monitoring,
    external,
    strategy_templates,
)
from .websocket_manager import WebSocketManager
from .auth import (
    router as auth_router,
    AuthenticationMiddleware as AuthMiddleware,
    bootstrap_admin_from_env,
    get_user_by_username,
    validate_auth_security,
)
from .middleware import RateLimitMiddleware, PerformanceMiddleware
from core.user_assets import DEFAULT_ADMIN_ASSET_SEED, get_user_asset_service
from core.version import VERSION
from core.memory_monitor import get_memory_monitor
from core.trading_calendar import get_trading_calendar

logger = logging.getLogger(__name__)

# WebSocket 管理器
ws_manager = WebSocketManager()

DEFAULT_DEV_CORS_ORIGINS = [
    "http://localhost:8686",
    "http://127.0.0.1:8686",
    "http://localhost:8685",
    "http://127.0.0.1:8685",
    "http://localhost:8687",
    "http://127.0.0.1:8687",
]
STRICT_TRUE_VALUES = {"1", "true", "yes", "on"}
PRODUCTION_ENV_VALUES = {"prod", "production"}


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in STRICT_TRUE_VALUES


def _is_production_security_mode() -> bool:
    app_env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "").strip().lower()
    return app_env in PRODUCTION_ENV_VALUES or _env_flag("STRICT_SECURITY_VALIDATION")


def _parse_cors_origins(value: str) -> List[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def _load_cors_origins() -> List[str]:
    configured = os.getenv("CORS_ORIGINS", "").strip()
    if configured:
        return _parse_cors_origins(configured)
    return DEFAULT_DEV_CORS_ORIGINS.copy()


def _is_loopback_origin(origin: str) -> bool:
    hostname = (urlparse(origin).hostname or "").strip().lower()
    return hostname in {"localhost", "127.0.0.1"}


def get_security_readiness_issues(cors_origins: Optional[List[str]] = None) -> List[str]:
    issues = validate_auth_security(strict=False)
    effective_origins = cors_origins if cors_origins is not None else _cors_origins

    if _env_flag("API_EXPECT_SAME_ORIGIN"):
        return issues

    if not os.getenv("CORS_ORIGINS", "").strip():
        issues.append(
            "CORS_ORIGINS is not explicitly configured. Set CORS_ORIGINS or API_EXPECT_SAME_ORIGIN=1 for release deployments."
        )
    elif not effective_origins or all(_is_loopback_origin(origin) for origin in effective_origins):
        issues.append("CORS_ORIGINS only contains localhost origins.")

    return issues


def validate_runtime_security(strict: Optional[bool] = None) -> List[str]:
    should_fail = _is_production_security_mode() if strict is None else strict
    issues = get_security_readiness_issues()

    for issue in issues:
        logger.warning("Security readiness issue: %s", issue)

    if should_fail and issues:
        raise RuntimeError("Runtime security validation failed: " + "; ".join(issues))

    return issues


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("API 服务启动中...")
    validate_runtime_security()
    logger.info("初始化认证与授权系统...")
    try:
        bootstrap_admin_from_env()
        admin_username = (os.getenv("APP_ADMIN_USERNAME") or "admin").strip() or "admin"
        admin_user = get_user_by_username(admin_username)
        if admin_user and admin_user.id is not None:
            seed_result = get_user_asset_service().seed_assets_if_empty(
                int(admin_user.id),
                DEFAULT_ADMIN_ASSET_SEED,
            )
            if seed_result.get("seeded"):
                logger.info(
                    "Seeded %s personal assets for %s",
                    seed_result.get("count", 0),
                    admin_username,
                )
        from core.rbac import get_rbac
        rbac = get_rbac()
        logger.info(f"RBAC系统初始化完成，支持 {len(rbac.get_available_roles())} 个角色")
    except Exception as e:
        logger.error(f"RBAC系统初始化失败: {e}")

    logger.info("初始化审计日志系统...")
    try:
        from core.audit_log import get_audit_logger
        audit_logger = get_audit_logger()
        logger.info("审计日志系统初始化完成")
    except Exception as e:
        logger.error(f"审计日志系统初始化失败: {e}")

    logger.info("初始化限流系统...")
    try:
        from api.middleware import get_rate_limiter
        limiter = get_rate_limiter()
        logger.info("限流系统初始化完成")
    except Exception as e:
        logger.error(f"限流系统初始化失败: {e}")

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

# ====================中间件配置====================

# CORS 配置（从环境变量读取允许的前端域名）
_cors_origins = _load_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# 性能监控中间件 - 记录耗时超过1秒的请求
app.add_middleware(PerformanceMiddleware, record_threshold_ms=1000.0)

# 限流中间件 - 根据用户角色进行限流
app.add_middleware(RateLimitMiddleware)

# 认证中间件 - 为所有API端点添加认证
# 注意：中间件按顺序执行，认证中间件应放在前面
app.add_middleware(AuthMiddleware)


@app.middleware("http")
async def ensure_cors_headers_for_auth_errors(request: Request, call_next):
    """Preserve CORS headers even when inner middleware returns early."""

    response = await call_next(request)
    origin = request.headers.get("origin")
    if origin and origin in _cors_origins:
        response.headers.setdefault("Access-Control-Allow-Origin", origin)
        response.headers.setdefault("Access-Control-Allow-Credentials", "true")
        response.headers.setdefault("Vary", "Origin")
    return response


# ====================注册路由====================

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
app.include_router(llm_analysis.router, prefix="/api/llm-analysis", tags=["LLM决策分析"])
app.include_router(market.router, prefix="/api/market", tags=["市场概览"])
app.include_router(agent.router, prefix="/api/agent", tags=["Agent研究"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["持仓分析"])
app.include_router(scanner.router, prefix="/api/scanner", tags=["选股扫描"])
app.include_router(user_config.router, prefix="/api/user", tags=["用户配置"])
app.include_router(user_assets.router, prefix="/api/user", tags=["个人资产"])
app.include_router(monitoring.router, prefix="/api", tags=["系统监控"])
app.include_router(external.router, prefix="/api/external", tags=["外部数据源"])
app.include_router(strategy_templates.router, prefix="/api", tags=["策略模板"])


# ====================全局异常处理====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理器"""
    logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail} - 路径: {request.url.path}")

    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
        },
    )

    # 添加认证头提示
    if exc.status_code == 401:
        response.headers["WWW-Authenticate"] = "Bearer"

    return response


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """404异常处理器"""
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Endpoint not found",
            "path": request.url.path,
            "method": request.method,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"全局异常: {exc} - 路径: {request.url.path}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "path": request.url.path,
            "method": request.method,
        },
    )


# ====================API端点====================

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
    """健康检查（含内存信息，便于低配环境监控）"""
    try:
        import psutil
        mem = psutil.virtual_memory()

        # 使用自定义内存监控器获取更详细的内存状态
        monitor = get_memory_monitor()
        memory_status = monitor.get_memory_status()

        # 检查内存状态
        is_healthy, memory_msg = monitor.check_memory()

        # 检查交易日（非交易日跳过详细检查）
        calendar = get_trading_calendar()
        is_trading_day = calendar.is_trading_day()

        status = "healthy"
        if not is_healthy:
            status = "critical" if memory_status.is_critical else "warning"

        security_issues = get_security_readiness_issues()

        return {
            "status": status,
            "service": "quant-ai-api",
            "version": VERSION,
            "memory": {
                "total_mb": mem.total // 1024 // 1024,
                "available_mb": mem.available // 1024 // 1024,
                "percent": mem.percent,
                "monitor_used_mb": memory_status.used_mb,
                "monitor_available_mb": memory_status.available_mb,
                "monitor_percent": memory_status.percent,
                "is_warning": memory_status.is_warning,
                "is_critical": memory_status.is_critical,
            },
            "trading_day": is_trading_day,
            "memory_message": memory_msg,
            "security": {
                "ready": not security_issues,
                "strict_mode": _is_production_security_mode(),
                "issues": security_issues,
            },
        }
    except Exception as e:
        logger.error(f"健康检查出错: {e}")
        return {
            "status": "healthy",
            "service": "quant-ai-api",
            "version": VERSION,
            "error": str(e),
            "security": {
                "ready": False,
                "strict_mode": _is_production_security_mode(),
                "issues": [str(e)],
            },
        }


@app.get("/api/rate-limit-info")
async def rate_limit_info(request: Request):
    """
    获取当前用户的限流信息（需要认证）

    返回当前用户的限流配置和剩余请求数
    """
    try:
        from api.middleware import get_rate_limiter

        limiter = get_rate_limiter()
        remaining = limiter.get_remaining_requests(request)
        reset_time = limiter.get_reset_time(request)
        config = limiter.get_config_for_user(limiter.get_user_role(request))

        return {
            "status": "success",
            "rate_limit": {
                "limit": config["tokens"],
                "remaining": remaining,
                "reset_after_seconds": round(reset_time, 2),
                "refill_rate_per_second": config["refill_rate"],
            },
        }
    except Exception as e:
        logger.error(f"获取限流信息失败: {e}")
        return {
            "status": "error",
            "message": f"获取失败: {str(e)}",
        }


@app.get("/api/rate-limit/stats")
async def rate_limit_stats():
    """
    获取限流统计信息（需要管理员权限）

    返回全局限流统计
    """
    try:
        from api.middleware import get_rate_limiter

        limiter = get_rate_limiter()
        stats = limiter.get_performance_stats() if hasattr(limiter, "get_performance_stats") else {}

        return {
            "status": "success",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"获取限流统计失败: {e}")
        return {
            "status": "error",
            "message": f"获取失败: {str(e)}",
        }


@app.get("/api/audit-stats")
async def audit_stats():
    """
    获取审计日志统计信息（需要管理员权限）

    返回审计日志统计
    """
    try:
        from core.audit_log import get_audit_logger

        audit_logger = get_audit_logger()
        stats = audit_logger.get_statistics()

        return {
            "status": "success",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"获取审计统计失败: {e}")
        return {
            "status": "error",
            "message": f"获取失败: {str(e)}",
        }


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


@app.get("/api/cleanup")
async def cleanup_memory():
    """
    清理内存和缓存（低配服务器专用）

    功能：
    - 强制垃圾回收
    - 清理多级缓存
    - 返回清理统计
    """
    try:
        monitor = get_memory_monitor()
        stats = monitor.cleanup_caches()

        return {
            "status": "success",
            "message": "内存清理完成",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"内存清理失败: {e}")
        return {
            "status": "error",
            "message": f"清理失败: {str(e)}",
        }


@app.get("/api/calendar")
async def trading_calendar_info():
    """
    获取交易日历信息

    功能：
    - 判断今天是否为交易日
    - 获取下个交易日
    - 获取市场交易时间
    """
    try:
        calendar = get_trading_calendar()
        today = datetime.date.today()

        return {
            "status": "success",
            "today": today.isoformat(),
            "is_trading_day": {
                "a_share": calendar.is_trading_day(today, market="a_share"),
                "hk_share": calendar.is_trading_day(today, market="hk_share"),
                "us_share": calendar.is_trading_day(today, market="us_share"),
            },
            "next_trading_day": {
                "a_share": calendar.get_next_trading_day(today, market="a_share").isoformat(),
            },
            "market_hours": {
                "a_share": calendar.get_market_hours("a_share"),
                "hk_share": calendar.get_market_hours("hk_share"),
                "us_share": calendar.get_market_hours("us_share"),
            },
        }
    except Exception as e:
        logger.error(f"交易日历获取失败: {e}")
        return {
            "status": "error",
            "message": f"获取失败: {str(e)}",
        }


# 仅为开发环境配置，生产环境使用 uvicorn 命令启动
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8685)

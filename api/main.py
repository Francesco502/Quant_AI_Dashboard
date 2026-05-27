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
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import gc
import os
from typing import List, Dict, Optional
import logging
import datetime
from urllib.parse import urlparse

from .websocket_manager import WebSocketManager
from .auth import (
    AuthenticationMiddleware as AuthMiddleware,
    bootstrap_admin_from_env,
    decode_access_token,
    get_user,
    get_user_by_username,
    require_admin,
    UserInDB,
    validate_auth_security,
)
from .middleware import CorrelationIdMiddleware, PerformanceMiddleware, RateLimitMiddleware
from .router_registry import register_api_routes
from core.logging_config import setup_logging
from core.user_assets import DEFAULT_ADMIN_ASSET_SEED, get_user_asset_service
from core.version import VERSION
from core.memory_monitor import get_memory_monitor
from core.trading_calendar import get_trading_calendar

logger = logging.getLogger(__name__)

# WebSocket 管理器
ws_manager = WebSocketManager()

# 性能优化环境变量
UVICORN_WORKERS = int(os.getenv("UVICORN_WORKERS", "1"))
UVICORN_CONCURRENCY = int(os.getenv("UVICORN_CONCURRENCY", "10"))
LAZY_LOAD_ML_MODELS = os.getenv("LAZY_LOAD_ML_MODELS", "true").lower() == "true"
ENABLE_GZIP = os.getenv("ENABLE_GZIP", "true").lower() == "true"
GZIP_MIN_SIZE = int(os.getenv("GZIP_MIN_SIZE", "1000"))
request_semaphore = asyncio.Semaphore(UVICORN_CONCURRENCY)

DEFAULT_DEV_CORS_ORIGINS = [
    "http://localhost:8686",
    "http://127.0.0.1:8686",
    "http://localhost:8685",
    "http://127.0.0.1:8685",
    "http://localhost:8687",
    "http://127.0.0.1:8687",
    "http://localhost:8786",
    "http://127.0.0.1:8786",
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
    setup_logging()
    logger.info("API 服务启动中...")
    logger.info(f"配置: workers={UVICORN_WORKERS}, concurrency={UVICORN_CONCURRENCY}, lazy_ml={LAZY_LOAD_ML_MODELS}")
    validate_runtime_security()

    if not LAZY_LOAD_ML_MODELS:
        logger.info("预加载 ML 模型...")
    else:
        logger.info("启用 ML 模型懒加载模式")

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
    gc.collect()


# 创建 FastAPI 应用
app = FastAPI(
    title="Quant-AI Dashboard API",
    description="量化交易系统 API 接口",
    version=VERSION,  # 使用应用版本号
    lifespan=lifespan,
    max_request_body_size=10 * 1024 * 1024,  # 10MB
)

# ====================中间件配置====================

# 请求追踪 — 最先执行，为所有后续中间件和日志提供 correlation ID
app.add_middleware(CorrelationIdMiddleware)

# GZip 压缩中间件（必须在 CORS 之前）
if ENABLE_GZIP:
    app.add_middleware(
        GZipMiddleware,
        minimum_size=GZIP_MIN_SIZE,
        compresslevel=6,
    )
    logger.info(f"启用 GZip 压缩 (min_size={GZIP_MIN_SIZE})")

# CORS 配置（从环境变量读取允许的前端域名）
_cors_origins = _load_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

# 性能监控中间件 - 记录耗时超过1秒的请求
app.add_middleware(PerformanceMiddleware, record_threshold_ms=1000.0)

# 限流中间件 - 根据用户角色进行限流
app.add_middleware(RateLimitMiddleware)

# 认证中间件 - 为所有API端点添加认证
# 注意：中间件按顺序执行，认证中间件应放在前面
app.add_middleware(AuthMiddleware)

# API audit logging (records all non-exempt API accesses)
from core.audit_log import APIAuditMiddleware
app.add_middleware(APIAuditMiddleware)

# 并发控制中间件（低配环境限制并发）
@app.middleware("http")
async def concurrency_limit_middleware(request, call_next):
    """限制并发请求数"""
    async with request_semaphore:
        response = await call_next(request)
        return response


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

register_api_routes(app)


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

        # 数据库连接检查
        db_ok = True
        db_error = None
        try:
            from core.database import get_database
            db = get_database()
            if db.conn:
                db.conn.execute("SELECT 1").fetchone()
        except Exception as e:
            db_ok = False
            db_error = str(e)

        # 磁盘空间检查
        disk_ok = True
        disk_info = {}
        try:
            disk = psutil.disk_usage("/")
            disk_info = {
                "total_gb": round(disk.total / (1024**3), 1),
                "used_gb": round(disk.used / (1024**3), 1),
                "free_gb": round(disk.free / (1024**3), 1),
                "percent": disk.percent,
            }
            if disk.percent > 90:
                disk_ok = False
        except Exception:
            disk_ok = False

        # 外部数据源可用性检查
        data_sources_ok = True
        data_source_status = {}
        try:
            from core.data_utils import get_api_key_status
            data_source_status = get_api_key_status()
        except Exception:
            data_source_status = {"error": "unable to check"}

        checks = {
            "memory": is_healthy,
            "database": db_ok,
            "disk": disk_ok,
            "data_sources": data_sources_ok,
        }
        all_healthy = all(checks.values())

        if not all_healthy:
            status = "degraded"
        if not is_healthy:
            status = "critical" if memory_status.is_critical else "warning"

        return {
            "status": status,
            "service": "quant-ai-api",
            "version": VERSION,
            "checks": {
                "memory": {"ok": is_healthy, "message": memory_msg},
                "database": {"ok": db_ok, "error": db_error},
                "disk": {"ok": disk_ok, **disk_info},
                "data_sources": {"ok": data_sources_ok, "configured": data_source_status},
            },
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
            "status": "degraded",
            "service": "quant-ai-api",
            "version": VERSION,
            "error": str(e),
            "checks": {
                "health": {"ok": False, "error": str(e)},
            },
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
async def rate_limit_stats(current_user: UserInDB = Depends(require_admin)):
    """
    获取限流统计信息（需要管理员权限）

    返回全局限流统计
    """
    del current_user
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
async def audit_stats(current_user: UserInDB = Depends(require_admin)):
    """
    获取审计日志统计信息（需要管理员权限）

    返回审计日志统计
    """
    del current_user
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


def _extract_websocket_token(websocket: WebSocket) -> Optional[str]:
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    subprotocols = websocket.headers.get("sec-websocket-protocol", "")
    for item in subprotocols.split(","):
        protocol = item.strip()
        if protocol.lower().startswith("bearer."):
            return protocol.split(".", 1)[1].strip()
    return None


async def _authenticate_websocket(websocket: WebSocket) -> Optional[UserInDB]:
    token = _extract_websocket_token(websocket)
    token_data = decode_access_token(token) if token else None
    user = get_user(token_data.username) if token_data else None
    if user is None or user.disabled:
        await websocket.close(code=1008)
        return None
    return user


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点"""
    current_user = await _authenticate_websocket(websocket)
    if current_user is None:
        return
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
    current_user = await _authenticate_websocket(websocket)
    if current_user is None:
        return
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
async def cleanup_memory(current_user: UserInDB = Depends(require_admin)):
    """
    清理内存和缓存（低配服务器专用）

    功能：
    - 强制垃圾回收
    - 清理多级缓存
    - 返回清理统计
    """
    del current_user
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

"""API中间件

职责：
- API限流中间件
- 请求日志记录
- 性能监控
- 异常处理
"""

from __future__ import annotations

import time
import threading
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, List, Callable, Any
from functools import wraps
import logging

from fastapi import Request, Response, Depends, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.auth import get_current_active_user, UserInDB


logger = logging.getLogger(__name__)


# ==================== 限流相关 ====================

class TokenBucket:
    """令牌桶算法实现"""

    def __init__(self, capacity: int, refill_rate: float, initial_tokens: Optional[float] = None):
        """
        初始化令牌桶

        Args:
            capacity: 桶容量（最大令牌数）
            refill_rate: 补充速率（tokens/second）
            initial_tokens: 初始令牌数（可选，默认为容量）
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = initial_tokens if initial_tokens is not None else float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: float = 1.0) -> bool:
        """
        消费令牌

        Args:
            tokens: 要消费的令牌数

        Returns:
            是否成功消费
        """
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_tokens(self) -> float:
        """获取当前令牌数"""
        with self._lock:
            self._refill()
            return self.tokens

    def get_wait_time(self, tokens: float = 1.0) -> float:
        """获取等待令牌的时间（秒）"""
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                return 0.0
            return (tokens - self.tokens) / self.refill_rate


class SlidingWindowCounter:
    """滑动窗口计数器实现"""

    def __init__(self, window_size: int, max_requests: int):
        """
        初始化滑动窗口计数器

        Args:
            window_size: 窗口大小（秒）
            max_requests: 最大请求数
        """
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests: List[float] = []
        self._lock = threading.Lock()

    def _cleanup(self) -> None:
        """清理过期的请求记录"""
        now = time.time()
        cutoff = now - self.window_size
        self.requests = [t for t in self.requests if t > cutoff]

    def is_allowed(self) -> bool:
        """检查是否允许请求"""
        with self._lock:
            self._cleanup()
            if len(self.requests) < self.max_requests:
                self.requests.append(time.time())
                return True
            return False

    def get_remaining(self) -> int:
        """获取剩余请求数"""
        with self._lock:
            self._cleanup()
            return max(0, self.max_requests - len(self.requests))

    def get_reset_time(self) -> float:
        """获取窗口重置时间（秒）"""
        with self._lock:
            self._cleanup()
            if not self.requests:
                return 0.0
            return self.window_size - (time.time() - self.requests[0])


class RateLimiter:
    """限流器管理器"""

    def __init__(self):
        """初始化限流器"""
        # 每个客户端的限流器：{client_key: (bucket, counter)}
        self.buckets: Dict[str, TokenBucket] = {}
        self.counters: Dict[str, SlidingWindowCounter] = {}
        self._lock = threading.Lock()

        # 默认配置
        self.default_config = {
            "普通用户": {"tokens": 60, "refill_rate": 1.0},  # 60次/分钟
            "管理员": {"tokens": 120, "refill_rate": 2.0},  # 120次/分钟
            "API密钥": {"tokens": 1000, "refill_rate": 10.0},  # 1000次/分钟
        }

    def get_client_key(self, request: Request) -> str:
        """
        获取客户端唯一标识

        Args:
            request: FastAPI请求对象

        Returns:
            客户端key
        """
        # 尝试从请求中获取用户信息
        if hasattr(request.state, "current_user"):
            return f"user:{request.state.current_user.username}"

        # 使用IP地址作为备选
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    def get_user_role(self, request: Request) -> str:
        """
        获取用户角色

        Args:
            request: FastAPI请求对象

        Returns:
            用户角色
        """
        if hasattr(request.state, "current_user"):
            user = request.state.current_user
            return user.role or "viewer"
        return "anonymous"

    def get_config_for_user(self, role: str) -> Dict[str, Any]:
        """
        获取用户的限流配置

        Args:
            role: 用户角色

        Returns:
            限流配置
        """
        role_lower = role.lower()

        if role_lower in ["admin", "administrator"]:
            return self.default_config["管理员"]
        elif role_lower in ["trader", "analyst", "viewer", "user"]:
            return self.default_config["普通用户"]
        else:
            return self.default_config["普通用户"]

    def is_allowed(self, request: Request) -> bool:
        """
        检查请求是否被允许

        Args:
            request: FastAPI请求对象

        Returns:
            是否允许
        """
        client_key = self.get_client_key(request)
        role = self.get_user_role(request)
        config = self.get_config_for_user(role)

        with self._lock:
            if client_key not in self.buckets:
                self.buckets[client_key] = TokenBucket(
                    capacity=config["tokens"],
                    refill_rate=config["refill_rate"]
                )

        bucket = self.buckets[client_key]
        return bucket.consume()

    def get_remaining_requests(self, request: Request) -> int:
        """
        获取剩余请求数

        Args:
            request: FastAPI请求对象

        Returns:
            剩余请求数
        """
        client_key = self.get_client_key(request)
        role = self.get_user_role(request)
        config = self.get_config_for_user(role)

        with self._lock:
            if client_key not in self.buckets:
                self.buckets[client_key] = TokenBucket(
                    capacity=config["tokens"],
                    refill_rate=config["refill_rate"]
                )

        bucket = self.buckets[client_key]
        return int(bucket.get_tokens())

    def get_reset_time(self, request: Request) -> float:
        """
        获取重置时间（秒）

        Args:
            request: FastAPI请求对象

        Returns:
            重置时间
        """
        client_key = self.get_client_key(request)

        with self._lock:
            if client_key not in self.buckets:
                role = self.get_user_role(request)
                config = self.get_config_for_user(role)
                self.buckets[client_key] = TokenBucket(
                    capacity=config["tokens"],
                    refill_rate=config["refill_rate"]
                )

        bucket = self.buckets[client_key]
        return bucket.get_wait_time()

    def record_request(self, request: Request, success: bool = True) -> None:
        """
        记录请求（用于统计）

        Args:
            request: FastAPI请求对象
            success: 是否成功
        """
        # 可以在这里添加额外的统计逻辑
        pass


# 全局限流器实例
_rate_limiter: Optional[RateLimiter] = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """
    获取限流器实例（单例模式）

    Returns:
        RateLimiter实例
    """
    global _rate_limiter

    with _rate_limiter_lock:
        if _rate_limiter is None:
            _rate_limiter = RateLimiter()
        return _rate_limiter


# ==================== 限流中间件 ====================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """API限流中间件"""

    def __init__(
        self,
        app,
        rate_limiter: Optional[RateLimiter] = None,
        exempt_paths: Optional[List[str]] = None,
        custom_limits: Optional[Dict[str, Dict[str, int]]] = None
    ):
        """
        初始化限流中间件

        Args:
            app: FastAPI应用
            rate_limiter: 限流器实例（可选）
            exempt_paths: 免限流路径（可选）
            custom_limits: 自定义限流配置（可选）
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.exempt_paths = exempt_paths or [
            "/api/health",
            "/api/auth/token",
            "/api/auth/register",
            "/docs",
            "/openapi.json",
            "/api/auth/me",
        ]
        self.custom_limits = custom_limits or {}

    async def dispatch(self, request: Request, call_next):
        """中间件分发"""
        path = request.url.path

        # 检查是否为 exempt 路径
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            return await call_next(request)

        # 检查自定义限流配置
        for pattern, limit_config in self.custom_limits.items():
            if path.startswith(pattern):
                # 使用自定义限流配置
                return await self._check_custom_limit(request, call_next, limit_config)

        # 使用默认限流
        if not self.rate_limiter.is_allowed(request):
            remaining = self.rate_limiter.get_remaining_requests(request)
            reset_time = self.rate_limiter.get_reset_time(request)

            # 记录限流事件
            try:
                from core.audit_log import get_audit_logger, AuditAction
                audit_logger = get_audit_logger()
                audit_logger.log_rate_limit(
                    user=getattr(request.state, "current_user", None).__dict__.get("username", "anonymous")
                    if hasattr(request.state, "current_user") else "anonymous",
                    endpoint=path,
                    rate_limit_type="token_bucket",
                    details={
                        "remaining": remaining,
                        "reset_time": reset_time,
                    },
                )
            except Exception:
                pass

            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": round(reset_time, 2),
                    "remaining": remaining,
                },
                headers={
                    "X-RateLimit-Limit": str(self.rate_limiter.get_config_for_user(
                        self.rate_limiter.get_user_role(request)
                    )["tokens"]),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(int(time.time() + reset_time)),
                },
            )
            return response

        # 记录请求
        self.rate_limiter.record_request(request, success=True)

        # 创建响应
        response = await call_next(request)

        # 添加限流头
        remaining = self.rate_limiter.get_remaining_requests(request)
        reset_time = self.rate_limiter.get_reset_time(request)
        config = self.rate_limiter.get_config_for_user(self.rate_limiter.get_user_role(request))

        response.headers["X-RateLimit-Limit"] = str(config["tokens"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + reset_time))

        return response

    async def _check_custom_limit(self, request: Request, call_next, limit_config: Dict[str, int]):
        """检查自定义限流配置"""
        # 简化的自定义限流检查
        window_size = limit_config.get("window", 60)
        max_requests = limit_config.get("max", 60)

        client_key = f"{request.url.path}:{self.rate_limiter.get_client_key(request)}"

        with self._rate_limiter_lock:
            if client_key not in self.rate_limiter.counters:
                self.rate_limiter.counters[client_key] = SlidingWindowCounter(
                    window_size=window_size,
                    max_requests=max_requests
                )

        counter = self.rate_limiter.counters[client_key]

        if not counter.is_allowed():
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": round(counter.get_reset_time(), 2),
                    "remaining": counter.get_remaining(),
                },
            )
            return response

        return await call_next(request)


# ==================== 性能监控中间件 ====================

class PerformanceMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""

    def __init__(self, app, record_threshold_ms: float = 1000.0):
        """
        初始化性能监控中间件

        Args:
            app: FastAPI应用
            record_threshold_ms: 记录阈值（毫秒）
        """
        super().__init__(app)
        self.record_threshold_ms = record_threshold_ms
        self.request_times: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        """中间件分发"""
        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception as e:
            # 记录异常请求
            self._record_request(request, start_time, success=False, error=str(e))
            raise

        duration_ms = (time.time() - start_time) * 1000

        # 记录耗时超过阈值的请求
        if duration_ms > self.record_threshold_ms:
            self._record_request(request, start_time, success=True, duration_ms=duration_ms)

        # 添加性能头
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        return response

    def _record_request(self, request: Request, start_time: float, success: bool, duration_ms: Optional[float] = None, error: Optional[str] = None) -> None:
        """记录请求"""
        duration_ms = duration_ms or (time.time() - start_time) * 1000

        record = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "duration_ms": duration_ms,
            "success": success,
        }

        if error:
            record["error"] = error

        if hasattr(request.state, "current_user"):
            record["user"] = request.state.current_user.username

        with self._lock:
            self.request_times.append(record)
            # 仅保留最近1000条
            if len(self.request_times) > 1000:
                self.request_times.pop(0)

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        with self._lock:
            if not self.request_times:
                return {}

            durations = [r["duration_ms"] for r in self.request_times]

            return {
                "total_requests": len(self.request_times),
                "avg_duration_ms": round(sum(durations) / len(durations), 2),
                "min_duration_ms": round(min(durations), 2),
                "max_duration_ms": round(max(durations), 2),
                "p95_duration_ms": round(sorted(durations)[int(len(durations) * 0.95)], 2),
                "p99_duration_ms": round(sorted(durations)[int(len(durations) * 0.99)], 2),
                "slow_requests": len([d for d in durations if d > self.record_threshold_ms]),
            }


# ==================== 认证中间件 ====================

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """认证中间件 - 为所有API端点添加认证"""

    def __init__(
        self,
        app,
        exempt_paths: Optional[List[str]] = None,
        public_paths: Optional[List[str]] = None
    ):
        """
        初始化认证中间件

        Args:
            app: FastAPI应用
            exempt_paths: 免认证路径（可选）
            public_paths: 公开路径（可选）
        """
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/api/health",
            "/docs",
            "/openapi.json",
            "/api/auth/token",
            "/api/auth/register",
            "/api/auth/me",
        ]
        self.public_paths = public_paths or [
            "/api/auth/token",
            "/api/auth/register",
        ]

    async def dispatch(self, request: Request, call_next):
        """中间件分发"""
        path = request.url.path

        # 检查是否为 exempt 路径
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            return await call_next(request)

        # 检查是否为 public 路径
        if any(path.startswith(public) for public in self.public_paths):
            return await call_next(request)

        # 检查 Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

        # 验证 token
        from api.auth import decode_access_token, get_user
        token = auth_header.split(" ", 1)[1]
        token_data = decode_access_token(token)

        if not token_data:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        # 获取用户
        user = get_user(token_data.username)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"detail": "User not found"},
            )

        # 设置当前用户到 request state
        request.state.current_user = user

        # 继续处理请求
        return await call_next(request)


# ==================== 权限检查依赖 ====================

def require_permission(permission: str):
    """
    权限检查依赖工厂

    Args:
        permission: 所需权限

    Returns:
        依赖函数
    """
    from api.auth import get_current_active_user, UserInDB
    from core.rbac import get_rbac, Permission
    from fastapi import HTTPException, status

    def permission_checker(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
        rbac = get_rbac()
        user_role = current_user.role or "viewer"
        perm = Permission(permission)

        if not rbac.check_permission(user_role, perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要 {permission} 权限"
            )

        return current_user

    return permission_checker


def require_any_permission(permissions: list):
    """
    检查是否有任一权限

    Args:
        permissions: 权限列表

    Returns:
        依赖函数
    """
    from api.auth import get_current_active_user, UserInDB
    from core.rbac import get_rbac
    from fastapi import HTTPException, status

    def permission_checker(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
        rbac = get_rbac()
        user_role = current_user.role or "viewer"

        if not rbac.check_any_permission(user_role, permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要以下任一权限 {permissions}"
            )

        return current_user

    return permission_checker


def require_role(role: str):
    """
    角色检查依赖工厂

    Args:
        role: 所需角色

    Returns:
        依赖函数
    """
    from api.auth import get_current_active_user, UserInDB
    from fastapi import HTTPException, status

    def role_checker(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
        user_role = current_user.role or "viewer"

        if user_role.lower() != role.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要 {role} 角色"
            )

        return current_user

    return role_checker


def require_admin(current_user: "UserInDB" = Depends(get_current_active_user)) -> "UserInDB":
    """
    管理员权限检查

    Args:
        current_user: 当前用户

    Returns:
        当前用户（如果为管理员）

    Raises:
        HTTPException: 如果用户不是管理员
    """
    from api.auth import UserInDB, get_current_active_user
    from fastapi import HTTPException, status

    if not (current_user.role and current_user.role.lower() == "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：需要管理员角色"
        )
    return current_user


# ==================== 限流装饰器 ====================

def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """
    限流装饰器

    Args:
        max_requests: 最大请求数
        window_seconds: 窗口大小（秒）

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        counter = SlidingWindowCounter(window_size=window_seconds, max_requests=max_requests)

        @wraps(func)
        def wrapper(*args, **kwargs):
            if not counter.is_allowed():
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            return func(*args, **kwargs)

        return wrapper

    return decorator


async def async_rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """
    异步限流装饰器

    Args:
        max_requests: 最大请求数
        window_seconds: 窗口大小（秒）

    Returns:
        装饰器函数
    """
    def decorator(func: Callable):
        counter = SlidingWindowCounter(window_size=window_seconds, max_requests=max_requests)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not counter.is_allowed():
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            return await func(*args, **kwargs)

        return wrapper

    return decorator

"""API认证系统

职责：
- JWT Token生成和验证
- OAuth2密码流
- 用户认证
- 认证中间件
- 权限检查
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# JWT配置
DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"
SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 默认24小时

# OAuth2方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


class Token(BaseModel):
    """Token响应模型"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token数据模型"""
    username: Optional[str] = None
    role: Optional[str] = None


class User(BaseModel):
    """用户模型"""
    username: str
    email: Optional[str] = None
    disabled: bool = False
    role: Optional[str] = None


class UserInDB(User):
    """数据库中的用户模型"""
    id: Optional[int] = None
    hashed_password: str


from core.database import Database
from core.rbac import get_rbac, get_user_role_manager, Role, Permission

# 数据库实例
db = Database()


def get_auth_security_issues(secret_key: Optional[str] = None) -> List[str]:
    """Return authentication security issues that should block production release."""
    issues: List[str] = []
    effective_secret = (secret_key if secret_key is not None else SECRET_KEY).strip()

    if not effective_secret or effective_secret == DEFAULT_SECRET_KEY:
        issues.append("SECRET_KEY is using the insecure default value.")

    return issues


def validate_auth_security(strict: bool = False, secret_key: Optional[str] = None) -> List[str]:
    """Validate authentication security configuration."""
    issues = get_auth_security_issues(secret_key=secret_key)
    if strict and issues:
        raise RuntimeError("Authentication security validation failed: " + "; ".join(issues))
    return issues


def get_user_by_username(username: str) -> Optional[UserInDB]:
    """从数据库获取用户"""
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()

        if row:
            # 获取用户角色
            role_manager = get_user_role_manager()
            role = role_manager.get_user_role(username)
            if not role:
                role = Role.ADMIN.value if username.lower() == "admin" else Role.VIEWER.value
                try:
                    role_manager.set_user_role(username, role, assigned_by="system")
                except Exception as role_exc:
                    logger.warning("Failed to persist default role for %s: %s", username, role_exc)
            return UserInDB(
                id=row["id"],
                username=row["username"],
                hashed_password=row["password_hash"],
                email=None,
                disabled=False,
                role=role or Role.VIEWER.value
            )
        return None
    except Exception as e:
        logger.error(f"获取用户失败: {e}")
        return None


def create_user(username: str, password: str, role: str = "viewer") -> bool:
    """创建新用户"""
    try:
        hashed = get_password_hash(password)
        cursor = db.conn.cursor()
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed))
        db.conn.commit()

        # 设置用户角色
        get_user_role_manager().set_user_role(username, role)
        logger.info(f"创建用户: {username}, 角色: {role}")

        return True
    except Exception as e:
        logger.error(f"创建用户失败: {e}")
        return False


def _truncate_password(password: str) -> bytes:
    """将密码编码为 UTF-8 并截断到 72 字节（bcrypt 限制）"""
    encoded = password.encode("utf-8")
    return encoded[:72]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码（使用 bcrypt）"""
    if not hashed_password or not plain_password:
        return False
    try:
        return bcrypt.checkpw(
            _truncate_password(plain_password),
            hashed_password.encode("utf-8") if isinstance(hashed_password, str) else hashed_password,
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """获取密码哈希（直接使用 bcrypt）"""
    return bcrypt.hashpw(_truncate_password(password), bcrypt.gensalt()).decode("utf-8")


def _get_bootstrap_admin_username() -> str:
    username = (os.getenv("APP_ADMIN_USERNAME") or "admin").strip()
    return username or "admin"


def _get_bootstrap_admin_password_hash() -> Optional[str]:
    configured_hash = (os.getenv("APP_LOGIN_PASSWORD_HASH") or "").strip()
    if configured_hash:
        return configured_hash

    configured_password = os.getenv("APP_LOGIN_PASSWORD")
    if configured_password:
        configured_password = configured_password.strip()
        if configured_password:
            return get_password_hash(configured_password)

    return None


def _sync_existing_bootstrap_admin(username: str) -> bool:
    """Keep the configured bootstrap admin credentials aligned with the current environment."""
    user = get_user_by_username(username)
    if not user:
        return False

    configured_hash = (os.getenv("APP_LOGIN_PASSWORD_HASH") or "").strip()
    configured_password = (os.getenv("APP_LOGIN_PASSWORD") or "").strip()
    next_hash: Optional[str] = None

    if configured_hash and configured_hash != user.hashed_password:
        next_hash = configured_hash
    elif configured_password and not verify_password(configured_password, user.hashed_password):
        next_hash = get_password_hash(configured_password)

    updated = False
    if next_hash:
        cursor = db.conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (next_hash, username),
        )
        db.conn.commit()
        updated = True
        logger.info("已同步管理员账号密码: %s", username)

    role_manager = get_user_role_manager()
    current_role = role_manager.get_user_role(username)
    if current_role != Role.ADMIN.value:
        role_manager.set_user_role(username, Role.ADMIN.value, assigned_by="system")
        updated = True

    return updated


def bootstrap_admin_from_env() -> bool:
    """Create the bootstrap admin only when credentials are explicitly configured."""
    username = _get_bootstrap_admin_username()

    try:
        hashed_password = _get_bootstrap_admin_password_hash()
        if get_user_by_username(username):
            if not hashed_password:
                return False
            return _sync_existing_bootstrap_admin(username)

        if not hashed_password:
            logger.warning(
                "未创建默认管理员：请通过 APP_LOGIN_PASSWORD 或 APP_LOGIN_PASSWORD_HASH 显式配置首个管理员账号"
            )
            return False

        cursor = db.conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hashed_password),
        )
        db.conn.commit()

        get_user_role_manager().set_user_role(username, Role.ADMIN.value, assigned_by="system")
        logger.info("已初始化管理员账号: %s", username)
        return True
    except Exception as e:
        logger.warning("初始化管理员失败: %s", e, exc_info=True)
        return False


def get_user(username: str) -> Optional[UserInDB]:
    """获取用户（从数据库）"""
    return get_user_by_username(username)


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """验证用户"""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """解码访问令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            return None
        return TokenData(username=username, role=role)
    except JWTError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """获取当前用户（从token）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    """获取当前活跃用户"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_permission(permission: str | Permission):
    """
    权限检查依赖工厂
    返回一个依赖函数，用于检查当前用户是否拥有指定权限

    Args:
        permission: 所需权限

    Returns:
        依赖函数，可用于FastAPI的Depends
    """
    def _check_permission(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
        if isinstance(permission, str):
            perm = Permission(permission)
        else:
            perm = permission

        rbac = get_rbac()
        user_role = current_user.role or "viewer"

        if not rbac.check_permission(user_role, perm):
            logger.warning(
                f"权限不足: 用户 {current_user.username} 缺少权限 {perm.value} (角色: {user_role})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要 {perm.value} 权限"
            )

        return current_user

    return _check_permission


def require_any_permission(permissions: List[str | Permission]):
    """
    检查是否有任一权限的依赖工厂
    用户拥有任一指定权限即可通过

    Args:
        permissions: 权限列表

    Returns:
        依赖函数，可用于FastAPI的Depends
    """
    def _check_any_permission(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
        rbac = get_rbac()
        user_role = current_user.role or "viewer"

        if not rbac.check_any_permission(user_role, permissions):
            logger.warning(
                f"权限不足: 用户 {current_user.username} 缺少任一权限 {permissions} (角色: {user_role})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要以下任一权限 {permissions}"
            )

        return current_user

    return _check_any_permission


def require_role(role: str | Role):
    """
    角色检查依赖工厂
    检查当前用户是否拥有指定角色

    Args:
        role: 所需角色

    Returns:
        依赖函数，可用于FastAPI的Depends
    """
    def _check_role(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
        if isinstance(role, Role):
            role_value = role.value
        else:
            role_value = role

        user_role = current_user.role or "viewer"

        if user_role != role_value:
            logger.warning(
                f"角色不匹配: 用户 {current_user.username} 角色为 {user_role}，需要 {role_value}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要 {role_value} 角色"
            )

        return current_user

    return _check_role


def require_admin(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
    """
    管理员权限检查
    仅管理员可访问

    Args:
        current_user: 当前用户

    Returns:
        当前用户（如果为管理员）

    Raises:
        HTTPException: 如果用户不是管理员
    """
    if not (current_user.role and current_user.role.lower() == "admin"):
        logger.warning(f"管理员权限不足: 用户 {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：需要管理员角色"
        )
    return current_user


async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """登录并获取访问令牌"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        # 记录失败的登录尝试
        try:
            from core.audit_log import get_audit_logger, AuditAction
            audit_logger = get_audit_logger()
            audit_logger.log_login(form_data.username, success=False)
        except Exception:
            pass  # 审计日志失败不应影响登录流程

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 记录成功的登录
    try:
        from core.audit_log import get_audit_logger, AuditAction
        audit_logger = get_audit_logger()
        audit_logger.log_login(user.username, success=True)
    except Exception:
        pass  # 审计日志失败不应影响登录流程

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


# 认证中间件 - 为所有API端点添加认证
class AuthenticationMiddleware:
    """Authentication Middleware for FastAPI"""

    def __init__(self, app):
        self.app = app
        self.exempt_paths = {"/api/auth/token", "/api/auth/register", "/api/health", "/docs", "/openapi.json", "/api/auth/me"}
        self.public_paths = {"/api/auth/token", "/api/auth/register"}

    async def __call__(self, scope, receive, send):
        """Middleware调用"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        method = scope.get("method", "").upper()
        path = request.url.path

        # CORS preflight should not be blocked by auth middleware.
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # 检查是否为 exempt 路径
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            await self.app(scope, receive, send)
            return

        # 检查是否有 Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            response = JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
            )
            await response(scope, receive, send)
            return

        # 验证 token
        token = auth_header.split(" ", 1)[1]
        token_data = decode_access_token(token)
        if not token_data:
            response = JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"},
            )
            await response(scope, receive, send)
            return

        # 设置当前用户到 request state
        user = get_user(token_data.username)
        if not user:
            response = JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "User not found"},
            )
            await response(scope, receive, send)
            return

        request.state.current_user = user

        # 继续处理请求
        await self.app(scope, receive, send)


# 创建认证路由
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """登录接口（获取JWT Token）"""
    return await login_for_access_token(form_data)


class RegisterRequest(BaseModel):
    """注册请求模型"""
    username: str
    password: str
    email: Optional[str] = None


@router.post("/register")
async def register_user(request: RegisterRequest):
    """用户注册接口（公开）"""
    # 校验用户名长度
    if len(request.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少3个字符")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6个字符")

    # 检查用户名是否已存在
    existing = get_user_by_username(request.username)
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    # 创建用户
    success = create_user(request.username, request.password, role="viewer")
    if not success:
        raise HTTPException(status_code=500, detail="注册失败，请稍后重试")

    # 记录注册动作
    try:
        from core.audit_log import get_audit_logger, AuditAction
        audit_logger = get_audit_logger()
        audit_logger.log(
            action=AuditAction.CREATE,
            user=request.username,
            resource="user",
            resource_type="user",
            details={"action": "register", "email": request.email},
            success=True,
        )
    except Exception:
        pass

    return {"status": "success", "message": "注册成功", "username": request.username}


@router.get("/me")
async def read_users_me(current_user: UserInDB = Depends(get_current_active_user)):
    """获取当前用户信息（需要认证）"""
    return {
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "disabled": current_user.disabled,
        "permissions": [p.value for p in get_rbac().get_user_permissions(current_user.role or Role.VIEWER.value)],
    }


@router.get("/permissions")
async def get_user_permissions(current_user: UserInDB = Depends(get_current_active_user)):
    """获取当前用户的权限列表"""
    from core.rbac import get_rbac
    rbac = get_rbac()
    permissions = rbac.get_user_permissions(current_user.role or "viewer")
    return {
        "username": current_user.username,
        "role": current_user.role,
        "permissions": [p.value for p in permissions],
    }


class PermissionCheckRequest(BaseModel):
    """权限检查请求"""
    permission: str


@router.post("/check-permission")
async def check_permission(
    request: PermissionCheckRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """检查当前用户是否有指定权限"""
    from core.rbac import get_rbac, Permission
    rbac = get_rbac()
    perm = Permission(request.permission)
    has_perm = rbac.check_permission(current_user.role or "viewer", perm)
    return {
        "username": current_user.username,
        "permission": request.permission,
        "has_permission": has_perm,
    }


class RoleCheckRequest(BaseModel):
    """角色检查请求"""
    role: str


@router.post("/check-role")
async def check_role(
    request: RoleCheckRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """检查当前用户是否拥有指定角色"""
    has_role = current_user.role and current_user.role.lower() == request.role.lower()
    return {
        "username": current_user.username,
        "current_role": current_user.role,
        "requested_role": request.role,
        "has_role": has_role,
    }


class UserRoleUpdateRequest(BaseModel):
    role: str


def _ensure_user_exists(username: str) -> UserInDB:
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _build_user_list() -> List[Dict[str, Any]]:
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT id, username, created_at FROM users ORDER BY username COLLATE NOCASE ASC"
    )
    rows = cursor.fetchall()
    role_manager = get_user_role_manager()
    stored_roles = role_manager.list_roles()

    users: List[Dict[str, Any]] = []
    for row in rows:
        username = row["username"]
        role_entry = stored_roles.get(username)
        role = role_entry.role if role_entry else None
        if not role:
            role = Role.ADMIN.value if username.lower() == "admin" else Role.VIEWER.value
            role_manager.set_user_role(username, role, assigned_by="system")
            stored_roles = role_manager.list_roles()
            role_entry = stored_roles.get(username)

        users.append(
            {
                "id": row["id"],
                "username": username,
                "role": role or Role.VIEWER.value,
                "assigned_at": (
                    role_entry.assigned_at
                    if role_entry and role_entry.assigned_at
                    else str(row["created_at"] or "")
                ),
                "assigned_by": role_entry.assigned_by if role_entry else "system",
            }
        )

    return users


def _delete_user_data(username: str) -> None:
    cursor = db.conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row or row["id"] is None:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = int(row["id"])
    cursor.execute("SELECT id FROM accounts WHERE user_id = ?", (user_id,))
    account_ids = [int(item["id"]) for item in cursor.fetchall()]

    for account_id in account_ids:
        cursor.execute("DELETE FROM fills WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM orders WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM equity_history WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM trade_history WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM positions WHERE account_id = ?", (account_id,))

    cursor.execute("DELETE FROM accounts WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM user_assets WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM user_strategies WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.conn.commit()


@router.get("/users")
async def list_users(current_user: UserInDB = Depends(require_admin)):
    del current_user
    users = _build_user_list()
    return {
        "status": "success",
        "count": len(users),
        "users": users,
    }


@router.put("/users/{username}/role")
async def update_user_role(
    username: str,
    request: UserRoleUpdateRequest,
    current_user: UserInDB = Depends(require_admin),
):
    normalized_role = request.role.strip().lower()
    try:
        Role(normalized_role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}") from exc

    _ensure_user_exists(username)

    if username == current_user.username and normalized_role != Role.ADMIN.value:
        raise HTTPException(status_code=400, detail="You cannot remove your own admin role")

    success = get_user_role_manager().set_user_role(
        username,
        normalized_role,
        assigned_by=current_user.username,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user role")

    return {
        "status": "success",
        "message": f"Role for {username} updated to {normalized_role}",
        "username": username,
        "new_role": normalized_role,
    }


@router.delete("/users/{username}")
async def delete_user(
    username: str,
    current_user: UserInDB = Depends(require_admin),
):
    bootstrap_admin = _get_bootstrap_admin_username().lower()
    if username.lower() == bootstrap_admin:
        raise HTTPException(status_code=400, detail="Bootstrap admin cannot be deleted")
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    _ensure_user_exists(username)

    try:
        _delete_user_data(username)
        get_user_role_manager().remove_user_role(username)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to delete user %s: %s", username, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {exc}") from exc

    return {
        "status": "success",
        "message": f"User {username} deleted",
        "username": username,
    }

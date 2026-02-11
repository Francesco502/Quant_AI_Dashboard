"""API认证系统

职责：
- JWT Token生成和验证
- OAuth2密码流
- 用户认证
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# JWT配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")


class Token(BaseModel):
    """Token响应模型"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token数据模型"""
    username: Optional[str] = None


class User(BaseModel):
    """用户模型"""
    username: str
    email: Optional[str] = None
    disabled: bool = False
    role: Optional[str] = None


class UserInDB(User):
    """数据库中的用户模型"""
    hashed_password: str


from core.database import Database

# 数据库实例
db = Database()

def get_user_by_username(username: str) -> Optional[UserInDB]:
    """从数据库获取用户"""
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            # 如果是旧的 fake users, 它们没有 id. 但这里是从 DB 取的。
            # 兼容性处理：如果数据库为空，尝试初始化 admin
            return UserInDB(
                username=row["username"],
                hashed_password=row["password_hash"],
                role="admin" # 简化：默认 admin，后续可在 DB 加 role 字段
            )
        return None
    except Exception as e:
        logger.error(f"获取用户失败: {e}")
        return None

def create_user(username: str, password: str) -> bool:
    """创建新用户"""
    try:
        hashed = get_password_hash(password)
        cursor = db.conn.cursor()
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed))
        db.conn.commit()
        return True
    except Exception as e:
        logger.error(f"创建用户失败: {e}")
        return False

# 初始化默认 Admin (如果不存在)，使用 bcrypt 直接哈希避免 passlib 与 bcrypt 4.x 不兼容
def _ensure_default_admin() -> None:
    try:
        if get_user_by_username("admin"):
            return
        if create_user("admin", "admin123"):
            logger.info("初始化默认管理员用户: admin / admin123")
        else:
            logger.warning("默认管理员 admin 创建失败（可能已存在或数据库错误）")
    except Exception as e:
        logger.warning("初始化默认管理员失败: %s", e, exc_info=True)


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


_ensure_default_admin()


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
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


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


# 创建认证路由
from fastapi import APIRouter

router = APIRouter()

@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """登录接口（获取JWT Token）"""
    return await login_for_access_token(form_data)


class RegisterRequest(BaseModel):
    """注册请求模型"""
    username: str
    password: str


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
    success = create_user(request.username, request.password)
    if not success:
        raise HTTPException(status_code=500, detail="注册失败，请稍后重试")

    return {"status": "success", "message": "注册成功", "username": request.username}


@router.get("/me")
async def read_users_me(current_user: UserInDB = Depends(get_current_active_user)):
    """获取当前用户信息（需要认证）"""
    return {
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "disabled": current_user.disabled,
    }

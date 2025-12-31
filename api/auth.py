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
from passlib.context import CryptContext
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# JWT配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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


# 模拟用户数据库（生产环境应使用真实数据库）
fake_users_db: dict[str, UserInDB] = {
    "admin": UserInDB(
        username="admin",
        email="admin@example.com",
        hashed_password=pwd_context.hash("admin123"),
        disabled=False,
        role="admin"
    ),
    "trader": UserInDB(
        username="trader",
        email="trader@example.com",
        hashed_password=pwd_context.hash("trader123"),
        disabled=False,
        role="trader"
    ),
    "viewer": UserInDB(
        username="viewer",
        email="viewer@example.com",
        hashed_password=pwd_context.hash("viewer123"),
        disabled=False,
        role="viewer"
    ),
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)


def get_user(username: str) -> Optional[UserInDB]:
    """获取用户（从数据库）"""
    return fake_users_db.get(username)


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


@router.get("/me")
async def read_users_me(current_user: UserInDB = Depends(get_current_active_user)):
    """获取当前用户信息（需要认证）"""
    return {
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "disabled": current_user.disabled,
    }


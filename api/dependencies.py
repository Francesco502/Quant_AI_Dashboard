"""API依赖项

职责：
- 权限检查依赖
- 用户信息获取
- RBAC封装
"""

from __future__ import annotations

# 添加 logging 导入（移到顶部）
import logging

logger = logging.getLogger(__name__)

from fastapi import Depends, HTTPException, status
from typing import List

from .auth import get_current_active_user, UserInDB, require_permission, require_any_permission, require_role, require_admin
from core.rbac import get_rbac, Permission, Role
from core.audit_log import get_audit_logger, AuditAction


__all__ = [
    "require_permission",
    "require_any_permission",
    "require_role",
    "require_admin",
    "require_trade_permission",
    "require_data_access",
    "require_strategy_permission",
    "log_access",
    "Permission",
    "Role",
]


def require_trade_permission(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
    """
    交易相关操作权限检查
    允许 TRADER 和 ADMIN 角色

    Args:
        current_user: 当前用户

    Returns:
        当前用户（如果权限允许）

    Raises:
        HTTPException: 如果用户没有权限
    """
    rbac = get_rbac()
    user_role = current_user.role or "viewer"

    # 允许 TRADER、ANALYST、ADMIN 执行交易相关操作
    allowed_permissions = [Permission.EXECUTE_TRADE, Permission.MANAGE_STRATEGY]

    if not rbac.check_any_permission(user_role, allowed_permissions):
        logger.warning(
            f"交易权限不足: 用户 {current_user.username} 缺少交易权限 (角色: {user_role})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：需要交易员或更高权限"
        )

    return current_user


def require_data_access(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
    """
    数据访问权限检查
    允许 ANALYST、TRADER、ADMIN 角色

    Args:
        current_user: 当前用户

    Returns:
        当前用户（如果权限允许）

    Raises:
        HTTPException: 如果用户没有权限
    """
    rbac = get_rbac()
    user_role = current_user.role or "viewer"

    if not rbac.check_permission(user_role, Permission.VIEW_DATA):
        logger.warning(
            f"数据访问权限不足: 用户 {current_user.username} 缺少数据访问权限 (角色: {user_role})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：需要数据访问权限"
        )

    return current_user


def require_strategy_permission(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
    """
    策略管理权限检查
    允许 TRADER、ANALYST、ADMIN 角色

    Args:
        current_user: 当前用户

    Returns:
        当前用户（如果权限允许）

    Raises:
        HTTPException: 如果用户没有权限
    """
    rbac = get_rbac()
    user_role = current_user.role or "viewer"

    allowed_permissions = [Permission.MANAGE_STRATEGY, Permission.VIEW_STRATEGY]

    if not rbac.check_any_permission(user_role, allowed_permissions):
        logger.warning(
            f"策略权限不足: 用户 {current_user.username} 缺少策略权限 (角色: {user_role})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：需要策略管理权限"
        )

    return current_user


def log_access(action: AuditAction | str, resource: str):
    """
    记录访问日志的依赖工厂

    Args:
        action: 操作类型
        resource: 资源标识

    Returns:
        依赖函数
    """
    def access_logger(current_user: UserInDB = Depends(get_current_active_user)):
        audit_logger = get_audit_logger()
        audit_logger.log(
            action=action,
            user=current_user.username,
            resource=resource,
            resource_type="api",
        )
        return current_user

    return access_logger

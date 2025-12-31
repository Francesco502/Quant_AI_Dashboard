"""API依赖项

职责：
- 权限检查依赖
- 用户信息获取
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from typing import List

from .auth import get_current_active_user, UserInDB
from core.rbac import get_rbac, Permission, Role
from core.audit_log import get_audit_logger, AuditAction


def require_permission(permission: Permission | str):
    """
    权限检查依赖工厂

    Args:
        permission: 所需权限

    Returns:
        依赖函数
    """
    def permission_checker(current_user: UserInDB = Depends(get_current_active_user)):
        rbac = get_rbac()
        user_role = current_user.role or "viewer"
        
        if not rbac.check_permission(user_role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要 {permission} 权限"
            )
        
        return current_user
    
    return permission_checker


def require_any_permission(permissions: List[Permission | str]):
    """
    检查是否有任一权限

    Args:
        permissions: 权限列表

    Returns:
        依赖函数
    """
    def permission_checker(current_user: UserInDB = Depends(get_current_active_user)):
        rbac = get_rbac()
        user_role = current_user.role or "viewer"
        
        if not rbac.has_any_permission(user_role, permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要以下任一权限 {permissions}"
            )
        
        return current_user
    
    return permission_checker


def require_role(role: Role | str):
    """
    角色检查依赖工厂

    Args:
        role: 所需角色

    Returns:
        依赖函数
    """
    def role_checker(current_user: UserInDB = Depends(get_current_active_user)):
        user_role = current_user.role or "viewer"
        
        if isinstance(role, Role):
            role = role.value
        
        if user_role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要 {role} 角色"
            )
        
        return current_user
    
    return role_checker


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


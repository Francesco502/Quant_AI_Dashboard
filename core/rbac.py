"""基于角色的访问控制（RBAC）

职责：
- 角色和权限定义
- 权限检查
- 角色管理
"""

from __future__ import annotations

from enum import Enum
from typing import List, Dict, Set
from dataclasses import dataclass
import logging


logger = logging.getLogger(__name__)


class Role(str, Enum):
    """角色定义"""
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"
    ANALYST = "analyst"


class Permission(str, Enum):
    """权限定义"""
    # 数据权限
    VIEW_DATA = "view_data"
    EXPORT_DATA = "export_data"
    
    # 交易权限
    EXECUTE_TRADE = "execute_trade"
    MANAGE_ACCOUNT = "manage_account"
    
    # 策略权限
    MANAGE_STRATEGY = "manage_strategy"
    VIEW_STRATEGY = "view_strategy"
    
    # 系统权限
    MANAGE_USER = "manage_user"
    MANAGE_SYSTEM = "manage_system"
    VIEW_AUDIT_LOG = "view_audit_log"


@dataclass
class RolePermission:
    """角色权限配置"""
    role: Role
    permissions: List[Permission]


class RBAC:
    """基于角色的访问控制"""
    
    def __init__(self):
        """初始化RBAC系统"""
        # 定义角色权限映射
        self.role_permissions: Dict[Role, Set[Permission]] = {
            Role.ADMIN: {
                Permission.VIEW_DATA,
                Permission.EXPORT_DATA,
                Permission.EXECUTE_TRADE,
                Permission.MANAGE_ACCOUNT,
                Permission.MANAGE_STRATEGY,
                Permission.VIEW_STRATEGY,
                Permission.MANAGE_USER,
                Permission.MANAGE_SYSTEM,
                Permission.VIEW_AUDIT_LOG,
            },
            Role.TRADER: {
                Permission.VIEW_DATA,
                Permission.EXPORT_DATA,
                Permission.EXECUTE_TRADE,
                Permission.MANAGE_ACCOUNT,
                Permission.VIEW_STRATEGY,
            },
            Role.ANALYST: {
                Permission.VIEW_DATA,
                Permission.EXPORT_DATA,
                Permission.MANAGE_STRATEGY,
                Permission.VIEW_STRATEGY,
            },
            Role.VIEWER: {
                Permission.VIEW_DATA,
            },
        }
        
        logger.info("RBAC系统初始化完成")
    
    def check_permission(self, user_role: str | Role, permission: str | Permission) -> bool:
        """
        检查用户是否有指定权限

        Args:
            user_role: 用户角色
            permission: 权限

        Returns:
            是否有权限
        """
        # 转换为枚举类型
        if isinstance(user_role, str):
            try:
                user_role = Role(user_role)
            except ValueError:
                logger.warning(f"未知角色: {user_role}")
                return False
        
        if isinstance(permission, str):
            try:
                permission = Permission(permission)
            except ValueError:
                logger.warning(f"未知权限: {permission}")
                return False
        
        # 检查权限
        permissions = self.role_permissions.get(user_role, set())
        return permission in permissions
    
    def get_user_permissions(self, user_role: str | Role) -> List[Permission]:
        """
        获取用户的所有权限

        Args:
            user_role: 用户角色

        Returns:
            权限列表
        """
        if isinstance(user_role, str):
            try:
                user_role = Role(user_role)
            except ValueError:
                return []
        
        permissions = self.role_permissions.get(user_role, set())
        return list(permissions)
    
    def has_any_permission(
        self,
        user_role: str | Role,
        permissions: List[str | Permission]
    ) -> bool:
        """
        检查用户是否有任一权限

        Args:
            user_role: 用户角色
            permissions: 权限列表

        Returns:
            是否有任一权限
        """
        return any(self.check_permission(user_role, perm) for perm in permissions)
    
    def has_all_permissions(
        self,
        user_role: str | Role,
        permissions: List[str | Permission]
    ) -> bool:
        """
        检查用户是否有所有权限

        Args:
            user_role: 用户角色
            permissions: 权限列表

        Returns:
            是否有所有权限
        """
        return all(self.check_permission(user_role, perm) for perm in permissions)
    
    def add_role_permission(self, role: Role, permission: Permission):
        """添加角色权限（动态配置）"""
        if role not in self.role_permissions:
            self.role_permissions[role] = set()
        self.role_permissions[role].add(permission)
        logger.info(f"添加权限: {role.value} -> {permission.value}")
    
    def remove_role_permission(self, role: Role, permission: Permission):
        """移除角色权限"""
        if role in self.role_permissions:
            self.role_permissions[role].discard(permission)
            logger.info(f"移除权限: {role.value} -> {permission.value}")


# 全局RBAC实例
_rbac_instance: RBAC = None


def get_rbac() -> RBAC:
    """获取RBAC实例（单例模式）"""
    global _rbac_instance
    if _rbac_instance is None:
        _rbac_instance = RBAC()
    return _rbac_instance


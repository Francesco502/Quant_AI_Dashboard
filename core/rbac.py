"""完整的访问控制系统

职责：
- 角色定义（ADMIN/TRADER/ANALYST/VIEWER四 tiers）
- 权限管理（VIEW_DATA/EXECUTE_TRADE/MANAGE_STRATEGY/MANAGE_USER/MANAGE_SYSTEM）
- RBAC权限检查
- 角色管理（创建/更新/删除角色）

优化说明：
- 2026-03-03: 完整实现四 tier RBAC 系统
"""

from __future__ import annotations

from enum import Enum
from typing import List, Set, Dict, Optional
import logging
import json
import os

from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger(__name__)


class Role(str, Enum):
    """角色定义（四 tier 访问控制）"""

    ADMIN = "admin"  # 管理员：完全控制权限
    TRADER = "trader"  # 交易员：查看数据、执行交易、管理策略
    ANALYST = "analyst"  # 分析师：查看数据、管理策略（不可执行交易）
    VIEWER = "viewer"  # 查看者：只读权限


class Permission(str, Enum):
    """权限定义"""

    # 数据权限
    VIEW_DATA = "view_data"  # 查看数据
    EXPORT_DATA = "export_data"  # 导出数据

    # 交易权限
    EXECUTE_TRADE = "execute_trade"  # 执行交易
    MANAGE_ACCOUNT = "manage_account"  # 管理账户

    # 策略权限
    MANAGE_STRATEGY = "manage_strategy"  # 管理策略
    VIEW_STRATEGY = "view_strategy"  # 查看策略

    # 用户权限
    MANAGE_USER = "manage_user"  # 管理用户

    # 系统权限
    MANAGE_SYSTEM = "manage_system"  # 管理系统
    VIEW_SYSTEM_LOG = "view_system_log"  # 查看系统日志


# 角色权限映射（定义每个角色的权限）
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # 管理员拥有所有权限
        Permission.VIEW_DATA,
        Permission.EXPORT_DATA,
        Permission.EXECUTE_TRADE,
        Permission.MANAGE_ACCOUNT,
        Permission.MANAGE_STRATEGY,
        Permission.VIEW_STRATEGY,
        Permission.MANAGE_USER,
        Permission.MANAGE_SYSTEM,
        Permission.VIEW_SYSTEM_LOG,
    },
    Role.TRADER: {
        # 交易员：查看数据、执行交易、管理策略
        Permission.VIEW_DATA,
        Permission.EXPORT_DATA,
        Permission.EXECUTE_TRADE,
        Permission.MANAGE_ACCOUNT,
        Permission.MANAGE_STRATEGY,
        Permission.VIEW_STRATEGY,
    },
    Role.ANALYST: {
        # 分析师：查看数据、管理策略（不可执行交易）
        Permission.VIEW_DATA,
        Permission.EXPORT_DATA,
        Permission.MANAGE_STRATEGY,
        Permission.VIEW_STRATEGY,
    },
    Role.VIEWER: {
        # 查看者：只读权限
        Permission.VIEW_DATA,
        Permission.VIEW_STRATEGY,
    },
}


class RBAC:
    """完整的访问控制系统"""

    def __init__(self, role_permissions: Optional[Dict[Role, Set[Permission]]] = None):
        """
        初始化RBAC系统

        Args:
            role_permissions: 自定义角色权限映射（可选）
        """
        self.role_permissions: Dict[Role, Set[Permission]] = (
            role_permissions if role_permissions else ROLE_PERMISSIONS
        )

        # 构建权限到角色的反向映射（用于查询）
        self._permission_roles: Dict[Permission, List[Role]] = {}
        for role, perms in self.role_permissions.items():
            for perm in perms:
                if perm not in self._permission_roles:
                    self._permission_roles[perm] = []
                self._permission_roles[perm].append(role)

        logger.info("RBAC系统初始化完成（完整版：四 tier 权限）")

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
                user_role = Role(user_role.lower())
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

    def check_any_permission(
        self, user_role: str | Role, permissions: List[str | Permission]
    ) -> bool:
        """
        检查用户是否有任一权限

        Args:
            user_role: 用户角色
            permissions: 权限列表

        Returns:
            是否有任一权限
        """
        for perm in permissions:
            if self.check_permission(user_role, perm):
                return True
        return False

    def check_all_permissions(
        self, user_role: str | Role, permissions: List[str | Permission]
    ) -> bool:
        """
        检查用户是否拥有所有指定权限

        Args:
            user_role: 用户角色
            permissions: 权限列表

        Returns:
            是否拥有所有权限
        """
        for perm in permissions:
            if not self.check_permission(user_role, perm):
                return False
        return True

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
                user_role = Role(user_role.lower())
            except ValueError:
                return []

        permissions = self.role_permissions.get(user_role, set())
        return list(permissions)

    def get_roles_for_permission(self, permission: str | Permission) -> List[Role]:
        """
        获取拥有指定权限的所有角色

        Args:
            permission: 权限

        Returns:
            角色列表
        """
        if isinstance(permission, str):
            try:
                permission = Permission(permission)
            except ValueError:
                return []

        return self._permission_roles.get(permission, [])

    def is_admin(self, user_role: str | Role) -> bool:
        """检查是否为管理员"""
        if isinstance(user_role, str):
            try:
                user_role = Role(user_role.lower())
            except ValueError:
                return False
        return user_role == Role.ADMIN

    def has_execute_permission(self, user_role: str | Role) -> bool:
        """检查是否有执行权限（交易或管理）"""
        return self.check_permission(user_role, Permission.EXECUTE_TRADE) or self.check_permission(user_role, Permission.MANAGE_STRATEGY)

    def has_data_access(self, user_role: str | Role) -> bool:
        """检查是否有数据访问权限"""
        return self.check_permission(user_role, Permission.VIEW_DATA)

    def has_strategy_access(self, user_role: str | Role) -> bool:
        """检查是否有策略访问权限"""
        return self.check_permission(user_role, Permission.MANAGE_STRATEGY) or self.check_permission(user_role, Permission.VIEW_STRATEGY)

    def get_available_roles(self) -> List[Role]:
        """获取所有可用角色"""
        return list(self.role_permissions.keys())

    def get_role_hierarchy(self) -> Dict[Role, List[Role]]:
        """
        获取角色层级关系（用于权限继承）

        Returns:
            角色层级映射
        """
        return {
            Role.ADMIN: [],  # 管理员没有上级
            Role.TRADER: [Role.ADMIN],
            Role.ANALYST: [Role.ADMIN],
            Role.VIEWER: [Role.TRADER, Role.ANALYST],
        }


# 全局RBAC实例
_rbac_instance: Optional[RBAC] = None


def get_rbac() -> RBAC:
    """
    获取RBAC实例（单例模式）

    Returns:
        RBAC实例
    """
    global _rbac_instance
    if _rbac_instance is None:
        _rbac_instance = RBAC()
    return _rbac_instance


# 用户角色存储（用于模拟数据库）
_user_roles_file = Path(__file__).parent / "data" / "user_roles.json"


@dataclass
class UserRoleEntry:
    """用户角色条目"""
    username: str
    role: str
    assigned_at: str
    assigned_by: Optional[str] = None


class UserRoleManager:
    """用户角色管理器"""

    def __init__(self, file_path: Optional[str] = None):
        """
        初始化角色管理器

        Args:
            file_path: 用户角色文件路径（可选，默认使用 data/user_roles.json）
        """
        if file_path is None:
            from .data_store import BASE_DIR
            file_path = os.path.join(BASE_DIR, "user_roles.json")

        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # 加载现有角色
        self._roles: Dict[str, UserRoleEntry] = {}
        self._load_roles()

    def _load_roles(self) -> None:
        """从文件加载角色"""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for username, role_data in data.get("roles", {}).items():
                        self._roles[username] = UserRoleEntry(
                            username=username,
                            role=role_data.get("role", "viewer"),
                            assigned_at=role_data.get("assigned_at", ""),
                            assigned_by=role_data.get("assigned_by"),
                        )
                logger.info(f"加载用户角色文件: {self.file_path}")
            except Exception as e:
                logger.error(f"加载用户角色文件失败: {e}")

    def _save_roles(self) -> bool:
        """保存角色到文件"""
        try:
            data = {
                "roles": {
                    username: {
                        "role": entry.role,
                        "assigned_at": entry.assigned_at,
                        "assigned_by": entry.assigned_by,
                    }
                    for username, entry in self._roles.items()
                },
                "updated_at": datetime.now().isoformat(),
            }
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存用户角色文件失败: {e}")
            return False

    def get_user_role(self, username: str) -> Optional[str]:
        """
        获取用户角色

        Args:
            username: 用户名

        Returns:
            用户角色，不存在返回 None
        """
        entry = self._roles.get(username)
        return entry.role if entry else None

    def set_user_role(self, username: str, role: str | Role, assigned_by: Optional[str] = None) -> bool:
        """
        设置用户角色

        Args:
            username: 用户名
            role: 新角色
            assigned_by: 分配者（可选）

        Returns:
            是否成功
        """
        from datetime import datetime

        if isinstance(role, Role):
            role = role.value

        # 验证角色有效性
        try:
            Role(role)
        except ValueError:
            logger.warning(f"无效角色: {role}")
            return False

        self._roles[username] = UserRoleEntry(
            username=username,
            role=role,
            assigned_at=datetime.now().isoformat(),
            assigned_by=assigned_by,
        )

        return self._save_roles()

    def remove_user_role(self, username: str) -> bool:
        """
        移除用户角色

        Args:
            username: 用户名

        Returns:
            是否成功
        """
        if username in self._roles:
            del self._roles[username]
            return self._save_roles()
        return False

    def list_roles(self) -> Dict[str, UserRoleEntry]:
        """列出所有用户角色"""
        return self._roles.copy()

    def get_users_by_role(self, role: str | Role) -> List[str]:
        """
        获取拥有指定角色的所有用户

        Args:
            role: 角色

        Returns:
            用户名列表
        """
        if isinstance(role, Role):
            role = role.value

        return [
            username
            for username, entry in self._roles.items()
            if entry.role == role
        ]


# 全局角色管理器实例
_user_role_manager: Optional[UserRoleManager] = None


def get_user_role_manager(file_path: Optional[str] = None) -> UserRoleManager:
    """
    获取角色管理器实例（单例模式）

    Args:
        file_path: 用户角色文件路径（可选）

    Returns:
        UserRoleManager实例
    """
    global _user_role_manager
    if _user_role_manager is None:
        _user_role_manager = UserRoleManager(file_path)
    return _user_role_manager


# 便捷函数
def check_user_permission(username: str, permission: str | Permission) -> bool:
    """
    检查用户是否有指定权限（便捷函数）

    Args:
        username: 用户名
        permission: 权限

    Returns:
        是否有权限
    """
    rbac = get_rbac()
    role = get_user_role_manager().get_user_role(username)
    if role is None:
        return False
    return rbac.check_permission(role, permission)


def get_user_permission_list(username: str) -> List[Permission]:
    """
    获取用户的所有权限（便捷函数）

    Args:
        username: 用户名

    Returns:
        权限列表
    """
    rbac = get_rbac()
    role = get_user_role_manager().get_user_role(username)
    if role is None:
        return []
    return rbac.get_user_permissions(role)


from datetime import datetime

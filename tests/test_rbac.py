"""RBAC测试"""

import pytest
from datetime import datetime
from core.rbac import RBAC, Role, Permission, get_rbac, UserRoleManager, get_user_role_manager, UserRoleManager, get_user_role_manager


class TestRBAC:
    """测试RBAC系统"""

    @pytest.fixture
    def rbac(self):
        """创建RBAC实例"""
        return RBAC()

    def test_check_permission_admin(self, rbac):
        """测试管理员权限"""
        assert rbac.check_permission(Role.ADMIN, Permission.VIEW_DATA) is True
        assert rbac.check_permission(Role.ADMIN, Permission.EXECUTE_TRADE) is True
        assert rbac.check_permission(Role.ADMIN, Permission.MANAGE_USER) is True
        assert rbac.check_permission(Role.ADMIN, Permission.MANAGE_SYSTEM) is True

    def test_check_permission_trader(self, rbac):
        """测试交易员权限"""
        assert rbac.check_permission(Role.TRADER, Permission.VIEW_DATA) is True
        assert rbac.check_permission(Role.TRADER, Permission.EXECUTE_TRADE) is True
        assert rbac.check_permission(Role.TRADER, Permission.MANAGE_STRATEGY) is True
        assert rbac.check_permission(Role.TRADER, Permission.MANAGE_ACCOUNT) is True
        assert rbac.check_permission(Role.TRADER, Permission.MANAGE_USER) is False  # TRADER无用户管理权限

    def test_check_permission_analyst(self, rbac):
        """测试分析师权限"""
        assert rbac.check_permission(Role.ANALYST, Permission.VIEW_DATA) is True
        assert rbac.check_permission(Role.ANALYST, Permission.MANAGE_STRATEGY) is True
        assert rbac.check_permission(Role.ANALYST, Permission.VIEW_STRATEGY) is True
        assert rbac.check_permission(Role.ANALYST, Permission.EXECUTE_TRADE) is False  # ANALYST无执行交易权限

    def test_check_permission_viewer(self, rbac):
        """测试查看者权限"""
        assert rbac.check_permission(Role.VIEWER, Permission.VIEW_DATA) is True
        assert rbac.check_permission(Role.VIEWER, Permission.VIEW_STRATEGY) is True
        assert rbac.check_permission(Role.VIEWER, Permission.EXECUTE_TRADE) is False
        assert rbac.check_permission(Role.VIEWER, Permission.MANAGE_STRATEGY) is False

    def test_check_any_permission(self, rbac):
        """测试任一权限检查"""
        permissions = [Permission.EXECUTE_TRADE, Permission.MANAGE_STRATEGY]
        assert rbac.check_any_permission(Role.TRADER, permissions) is True
        assert rbac.check_any_permission(Role.ANALYST, permissions) is True  # ANALYST有MANAGE_STRATEGY
        assert rbac.check_any_permission(Role.VIEWER, permissions) is False

    def test_get_user_permissions(self, rbac):
        """测试获取用户权限"""
        admin_perms = rbac.get_user_permissions(Role.ADMIN)
        assert Permission.VIEW_DATA in admin_perms
        assert Permission.EXECUTE_TRADE in admin_perms
        assert Permission.MANAGE_USER in admin_perms

        trader_perms = rbac.get_user_permissions(Role.TRADER)
        assert Permission.VIEW_DATA in trader_perms
        assert Permission.EXECUTE_TRADE in trader_perms
        assert Permission.MANAGE_USER not in trader_perms

    def test_is_admin(self, rbac):
        """测试是否管理员"""
        assert rbac.is_admin(Role.ADMIN) is True
        assert rbac.is_admin(Role.TRADER) is False
        assert rbac.is_admin(Role.ANALYST) is False
        assert rbac.is_admin(Role.VIEWER) is False

    def test_get_rbac_singleton(self):
        """测试RBAC单例模式"""
        rbac1 = get_rbac()
        rbac2 = get_rbac()
        assert rbac1 is rbac2

    def test_role_hierarchy(self, rbac):
        """测试角色层级关系"""
        hierarchy = rbac.get_role_hierarchy()
        assert Role.ADMIN in hierarchy
        assert Role.TRADER in hierarchy
        assert Role.ANALYST in hierarchy
        assert Role.VIEWER in hierarchy


class TestUserRoleManager:
    """测试用户角色管理器"""

    def test_get_user_role(self):
        """测试获取用户角色"""
        manager = UserRoleManager()
        # 测试不存在的用户
        assert manager.get_user_role("nonexistent_user") is None

    def test_set_user_role(self):
        """测试设置用户角色"""
        manager = UserRoleManager()
        username = "test_user_" + str(hash(datetime.now()))
        success = manager.set_user_role(username, Role.TRADER.value)
        assert success is True
        assert manager.get_user_role(username) == Role.TRADER.value

    def test_list_roles(self):
        """测试列出所有角色"""
        manager = UserRoleManager()
        roles = manager.list_roles()
        assert isinstance(roles, dict)


class TestIntegration:
    """集成测试"""

    def test_full_permission_check(self):
        """测试完整权限检查流程"""
        rbac = get_rbac()
        manager = get_user_role_manager()

        # 为测试用户设置角色
        test_user = "test_integration_user"
        manager.set_user_role(test_user, Role.ANALYST.value)

        # 检查权限
        role = manager.get_user_role(test_user)
        assert role == Role.ANALYST.value
        assert rbac.check_permission(role, Permission.VIEW_DATA) is True
        assert rbac.check_permission(role, Permission.MANAGE_STRATEGY) is True
        assert rbac.check_permission(role, Permission.EXECUTE_TRADE) is False

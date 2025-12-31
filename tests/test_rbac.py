"""RBAC测试"""

import pytest
from core.rbac import RBAC, Role, Permission, get_rbac


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
    
    def test_check_permission_trader(self, rbac):
        """测试交易员权限"""
        assert rbac.check_permission(Role.TRADER, Permission.VIEW_DATA) is True
        assert rbac.check_permission(Role.TRADER, Permission.EXECUTE_TRADE) is True
        assert rbac.check_permission(Role.TRADER, Permission.MANAGE_USER) is False
    
    def test_check_permission_viewer(self, rbac):
        """测试查看者权限"""
        assert rbac.check_permission(Role.VIEWER, Permission.VIEW_DATA) is True
        assert rbac.check_permission(Role.VIEWER, Permission.EXECUTE_TRADE) is False
        assert rbac.check_permission(Role.VIEWER, Permission.MANAGE_STRATEGY) is False
    
    def test_get_user_permissions(self, rbac):
        """测试获取用户权限"""
        admin_perms = rbac.get_user_permissions(Role.ADMIN)
        assert Permission.VIEW_DATA in admin_perms
        assert Permission.EXECUTE_TRADE in admin_perms
        
        viewer_perms = rbac.get_user_permissions(Role.VIEWER)
        assert Permission.VIEW_DATA in viewer_perms
        assert Permission.EXECUTE_TRADE not in viewer_perms
    
    def test_has_any_permission(self, rbac):
        """测试是否有任一权限"""
        assert rbac.has_any_permission(
            Role.TRADER,
            [Permission.VIEW_DATA, Permission.MANAGE_USER]
        ) is True
        
        assert rbac.has_any_permission(
            Role.VIEWER,
            [Permission.EXECUTE_TRADE, Permission.MANAGE_USER]
        ) is False
    
    def test_add_remove_permission(self, rbac):
        """测试添加和移除权限"""
        # 添加权限
        rbac.add_role_permission(Role.VIEWER, Permission.EXPORT_DATA)
        assert rbac.check_permission(Role.VIEWER, Permission.EXPORT_DATA) is True
        
        # 移除权限
        rbac.remove_role_permission(Role.VIEWER, Permission.EXPORT_DATA)
        assert rbac.check_permission(Role.VIEWER, Permission.EXPORT_DATA) is False
    
    def test_get_rbac_singleton(self):
        """测试RBAC单例模式"""
        rbac1 = get_rbac()
        rbac2 = get_rbac()
        assert rbac1 is rbac2


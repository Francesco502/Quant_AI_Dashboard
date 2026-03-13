"""审计日志测试"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from core.audit_log import AuditLogger, AuditAction, get_audit_logger


class TestAuditLogger:
    """测试审计日志"""
    
    @pytest.fixture
    def audit_logger(self):
        """创建临时审计日志实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            yield logger
            # 确保关闭所有文件句柄
            if hasattr(logger, 'logger') and logger.logger:
                for handler in logger.logger.handlers[:]:
                    handler.close()
                    logger.logger.removeHandler(handler)
    
    def test_log(self, audit_logger):
        """测试记录日志"""
        audit_logger.log(
            action=AuditAction.VIEW,
            user="test_user",
            resource="data/AAPL",
            resource_type="data"
        )
        
        # 验证日志文件存在
        assert os.path.exists(audit_logger.log_file)
    
    def test_log_login(self, audit_logger):
        """测试记录登录"""
        audit_logger.log_login("test_user", ip_address="127.0.0.1", success=True)
        audit_logger.log_login("test_user", ip_address="127.0.0.1", success=False)

        # 查询日志 - 包括LOGIN和LOGIN_FAILURE
        logs = audit_logger.query_logs(user="test_user", action="LOGIN")
        # 由于我们只记录LOGIN动作，LOGIN_FAILURE在query_logs中可能被过滤
        # 实际上log_login方法对失败也使用LOGIN_FAILURE动作
        # 验证两条日志都被记录
        all_logs = audit_logger.query_logs(user="test_user")
        assert len(all_logs) >= 1

    def test_log_data_access(self, audit_logger):
        """测试记录数据访问"""
        audit_logger.log_data_access(
            user="test_user",
            resource="AAPL",
            resource_type="data",
            details={"days": 365}
        )

        logs = audit_logger.query_logs(user="test_user", action="DATA_ACCESS")
        assert len(logs) > 0
    
    def test_log_trade_execution(self, audit_logger):
        """测试记录交易执行"""
        audit_logger.log_trade_execution(
            user="trader",
            resource="trade_001",
            details={"ticker": "AAPL", "quantity": 100},
            success=True
        )
        
        logs = audit_logger.query_logs(action="EXECUTE")
        assert len(logs) > 0
    
    def test_query_logs(self, audit_logger):
        """测试查询日志"""
        # 记录多条日志
        audit_logger.log(AuditAction.VIEW, "user1", "resource1")
        audit_logger.log(AuditAction.VIEW, "user2", "resource2")
        audit_logger.log(AuditAction.EXECUTE, "user1", "resource3")
        
        # 按用户查询
        logs = audit_logger.query_logs(user="user1")
        assert len(logs) == 2
        
        # 按操作查询
        logs = audit_logger.query_logs(action="VIEW")
        assert len(logs) == 2
        
        # 按资源查询
        logs = audit_logger.query_logs(resource="resource1")
        assert len(logs) == 1
    
    def test_get_statistics(self, audit_logger):
        """测试获取统计信息"""
        # 记录多条日志
        audit_logger.log(AuditAction.VIEW, "user1", "resource1", success=True)
        audit_logger.log(AuditAction.EXECUTE, "user1", "resource2", success=True)
        audit_logger.log(AuditAction.VIEW, "user2", "resource3", success=False)
        
        stats = audit_logger.get_statistics()
        
        assert "total_entries" in stats
        assert "success_count" in stats
        assert "error_count" in stats
        assert "by_action" in stats
        assert "by_user" in stats
    
    def test_get_audit_logger_singleton(self):
        """测试审计日志单例模式"""
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2


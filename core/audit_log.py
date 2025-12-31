"""审计日志系统

职责：
- 记录所有关键操作
- 支持审计追踪
- 日志查询和分析
"""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """审计操作类型"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"
    VIEW = "VIEW"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    CONFIGURE = "CONFIGURE"


@dataclass
class AuditLogEntry:
    """审计日志条目"""
    timestamp: str
    action: str
    user: str
    resource: str
    resource_type: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, log_dir: Optional[str] = None):
        """
        初始化审计日志记录器

        Args:
            log_dir: 日志目录（可选，默认使用logs/audit）
        """
        if log_dir is None:
            from .data_store import BASE_DIR
            log_dir = os.path.join(BASE_DIR, "..", "logs", "audit")
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 日志文件（按日期分割）
        self.log_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.log"
        
        # 配置日志记录器
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        
        # 文件处理器
        if not self.logger.handlers:
            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        logger.info(f"审计日志系统初始化完成: {self.log_dir}")
    
    def log(
        self,
        action: str | AuditAction,
        user: str,
        resource: str,
        resource_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """
        记录审计日志

        Args:
            action: 操作类型
            user: 用户名
            resource: 资源标识
            resource_type: 资源类型（可选）
            details: 详细信息（可选）
            ip_address: IP地址（可选）
            user_agent: 用户代理（可选）
            success: 是否成功
            error_message: 错误消息（可选）
        """
        if isinstance(action, AuditAction):
            action = action.value
        
        entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            action=action,
            user=user,
            resource=resource,
            resource_type=resource_type,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )
        
        # 记录到日志文件
        log_message = json.dumps(asdict(entry), ensure_ascii=False)
        self.logger.info(log_message)
        
        # 同时写入JSON文件（便于查询）
        json_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(json_file, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    
    def log_login(self, user: str, ip_address: Optional[str] = None, success: bool = True):
        """记录登录操作"""
        self.log(
            action=AuditAction.LOGIN,
            user=user,
            resource="system",
            resource_type="authentication",
            ip_address=ip_address,
            success=success,
        )
    
    def log_data_access(
        self,
        user: str,
        resource: str,
        resource_type: str = "data",
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None
    ):
        """记录数据访问"""
        self.log(
            action=AuditAction.VIEW,
            user=user,
            resource=resource,
            resource_type=resource_type,
            details=details,
            ip_address=ip_address,
        )
    
    def log_trade_execution(
        self,
        user: str,
        resource: str,
        details: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """记录交易执行"""
        self.log(
            action=AuditAction.EXECUTE,
            user=user,
            resource=resource,
            resource_type="trade",
            details=details,
            success=success,
            error_message=error_message,
        )
    
    def log_strategy_change(
        self,
        user: str,
        action: str,
        resource: str,
        details: Optional[Dict] = None
    ):
        """记录策略变更"""
        self.log(
            action=action,
            user=user,
            resource=resource,
            resource_type="strategy",
            details=details,
        )
    
    def query_logs(
        self,
        user: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        查询审计日志

        Args:
            user: 用户名（可选）
            action: 操作类型（可选）
            resource: 资源标识（可选）
            start_date: 起始日期（可选）
            end_date: 结束日期（可选）
            limit: 返回数量限制

        Returns:
            日志条目列表
        """
        entries = []
        
        # 读取所有日志文件
        for json_file in self.log_dir.glob("audit_*.jsonl"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line)
                            
                            # 过滤条件
                            if user and entry.get("user") != user:
                                continue
                            if action and entry.get("action") != action:
                                continue
                            if resource and entry.get("resource") != resource:
                                continue
                            
                            # 日期过滤
                            if start_date or end_date:
                                entry_time = datetime.fromisoformat(entry.get("timestamp", ""))
                                if start_date and entry_time < start_date:
                                    continue
                                if end_date and entry_time > end_date:
                                    continue
                            
                            entries.append(entry)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.error(f"读取日志文件失败: {json_file} - {e}")
        
        # 按时间倒序排序
        entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return entries[:limit]
    
    def get_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取审计日志统计信息

        Args:
            start_date: 起始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            统计信息字典
        """
        entries = self.query_logs(start_date=start_date, end_date=end_date, limit=10000)
        
        # 统计
        by_action = {}
        by_user = {}
        by_resource_type = {}
        success_count = 0
        error_count = 0
        
        for entry in entries:
            action = entry.get("action", "UNKNOWN")
            user = entry.get("user", "UNKNOWN")
            resource_type = entry.get("resource_type", "UNKNOWN")
            
            by_action[action] = by_action.get(action, 0) + 1
            by_user[user] = by_user.get(user, 0) + 1
            by_resource_type[resource_type] = by_resource_type.get(resource_type, 0) + 1
            
            if entry.get("success", True):
                success_count += 1
            else:
                error_count += 1
        
        return {
            "total_entries": len(entries),
            "success_count": success_count,
            "error_count": error_count,
            "by_action": by_action,
            "by_user": by_user,
            "by_resource_type": by_resource_type,
        }


# 全局审计日志实例
_audit_logger_instance: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """获取审计日志实例（单例模式）"""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger()
    return _audit_logger_instance


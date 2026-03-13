"""审计日志系统

职责：
- 记录所有关键操作
- 支持审计追踪
- 日志查询和分析
- API访问日志
- 敏感操作日志
"""

from __future__ import annotations

import os
import json
import logging
import socket
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import threading


logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """审计操作类型"""
    # 用户相关
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    VIEW = "VIEW"

    # 认证相关
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    TOKEN_REFRESH = "TOKEN_REFRESH"

    # 交易相关
    EXECUTE = "EXECUTE"
    ORDER_CREATE = "ORDER_CREATE"
    ORDER_CANCEL = "ORDER_CANCEL"
    TRADE = "TRADE"

    # 策略相关
    STRATEGY_CREATE = "STRATEGY_CREATE"
    STRATEGY_UPDATE = "STRATEGY_UPDATE"
    STRATEGY_DELETE = "STRATEGY_DELETE"
    STRATEGY_ENABLE = "STRATEGY_ENABLE"
    STRATEGY_DISABLE = "STRATEGY_DISABLE"

    # 数据相关
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    DATA_ACCESS = "DATA_ACCESS"

    # 用户管理
    USER_CREATE = "USER_CREATE"
    USER_UPDATE = "USER_UPDATE"
    USER_DELETE = "USER_DELETE"
    ROLE_ASSIGN = "ROLE_ASSIGN"
    PERMISSION_GRANT = "PERMISSION_GRANT"

    # 系统管理
    CONFIGURE = "CONFIGURE"
    SYSTEM_UPDATE = "SYSTEM_UPDATE"
    BACKUP = "BACKUP"
    RESTORE = "RESTORE"

    # API访问
    API_ACCESS = "API_ACCESS"
    API_RATE_LIMITED = "API_RATE_LIMITED"


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
    request_id: Optional[str] = None
    duration_ms: Optional[float] = None


class AuditLogger:
    """审计日志记录器"""

    def __init__(self, log_dir: Optional[str] = None):
        """
        初始化审计日志记录器

        Args:
            log_dir: 日志目录（可选，默认使用data/logs/audit）
        """
        if log_dir is None:
            from .data_store import BASE_DIR
            log_dir = os.path.join(BASE_DIR, "logs", "audit")

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 日志文件（按日期分割）
        self.log_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.log"

        # 配置日志记录器
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)

        # 文件处理器（线程安全）
        if not self.logger.handlers:
            # 确保目录存在
            self.log_dir.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        logger.info(f"审计日志系统初始化完成: {self.log_dir}")

        # 内存日志缓存（用于快速查询最近的日志）
        self._memory_cache: List[Dict[str, Any]] = []
        self._max_cache_size = 1000
        self._cache_lock = threading.Lock()

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
        error_message: Optional[str] = None,
        request_id: Optional[str] = None,
        duration_ms: Optional[float] = None
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
            request_id: 请求ID（可选）
            duration_ms: 执行耗时（可选）
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
            request_id=request_id,
            duration_ms=duration_ms,
        )

        # 记录到日志文件
        log_message = json.dumps(asdict(entry), ensure_ascii=False)
        self.logger.info(log_message)

        # 写入JSON文件（便于查询）
        json_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        try:
            with open(json_file, "a", encoding="utf-8") as f:
                f.write(log_message + "\n")
        except Exception as e:
            logger.error(f"写入审计日志文件失败: {e}")

        # 添加到内存缓存
        self._add_to_cache(asdict(entry))

    def _add_to_cache(self, entry: Dict[str, Any]) -> None:
        """添加到内存缓存（线程安全）"""
        with self._cache_lock:
            self._memory_cache.append(entry)
            if len(self._memory_cache) > self._max_cache_size:
                self._memory_cache.pop(0)

    def log_login(self, user: str, ip_address: Optional[str] = None, success: bool = True,
                  user_agent: Optional[str] = None) -> None:
        """记录登录操作"""
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILURE
        self.log(
            action=action,
            user=user,
            resource="system",
            resource_type="authentication",
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            details={"login_type": "password"},
        )

    def log_data_access(
        self,
        user: str,
        resource: str,
        resource_type: str = "data",
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        success: bool = True
    ) -> None:
        """记录数据访问"""
        self.log(
            action=AuditAction.DATA_ACCESS,
            user=user,
            resource=resource,
            resource_type=resource_type,
            details=details,
            ip_address=ip_address,
            success=success,
        )

    def log_trade_execution(
        self,
        user: str,
        resource: str,
        details: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
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
        details: Optional[Dict] = None,
        success: bool = True
    ) -> None:
        """记录策略变更"""
        self.log(
            action=action,
            user=user,
            resource=resource,
            resource_type="strategy",
            details=details,
            success=success,
        )

    def log_user_management(
        self,
        user: str,
        action: str,
        target_user: str,
        details: Optional[Dict] = None,
        success: bool = True
    ) -> None:
        """记录用户管理操作"""
        self.log(
            action=action,
            user=user,
            resource=target_user,
            resource_type="user",
            details=details,
            success=success,
        )

    def log_role_assignment(
        self,
        user: str,
        target_user: str,
        new_role: str,
        details: Optional[Dict] = None,
        success: bool = True
    ) -> None:
        """记录角色分配"""
        self.log(
            action=AuditAction.ROLE_ASSIGN,
            user=user,
            resource=target_user,
            resource_type="user",
            details={"new_role": new_role, **(details or {})},
            success=success,
        )

    def log_api_access(
        self,
        user: str,
        endpoint: str,
        method: str = "GET",
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
        duration_ms: Optional[float] = None,
        request_id: Optional[str] = None
    ) -> None:
        """记录API访问"""
        self.log(
            action=AuditAction.API_ACCESS,
            user=user,
            resource=endpoint,
            resource_type="api",
            details={
                "method": method,
                "endpoint": endpoint,
                **(details or {})
            },
            ip_address=ip_address,
            success=success,
            duration_ms=duration_ms,
            request_id=request_id,
        )

    def log_rate_limit(
        self,
        user: str,
        endpoint: str,
        rate_limit_type: str = "minute",
        details: Optional[Dict] = None
    ) -> None:
        """记录API限流事件"""
        self.log(
            action=AuditAction.API_RATE_LIMITED,
            user=user,
            resource=endpoint,
            resource_type="api",
            details={
                "rate_limit_type": rate_limit_type,
                **(details or {})
            },
            success=False,
        )

    def log_sensitive_operation(
        self,
        user: str,
        operation: str,
        resource: str,
        details: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """记录敏感操作（高优先级日志）"""
        # 添加额外的安全信息
        sensitive_details = {
            "operation": operation,
            "is_sensitive": True,
            **(details or {})
        }
        self.log(
            action=AuditAction.EXECUTE,
            user=user,
            resource=resource,
            resource_type="sensitive",
            details=sensitive_details,
            success=success,
            error_message=error_message,
        )

    def query_logs(
        self,
        user: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        success: Optional[bool] = None,
        resource_type: Optional[str] = None
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
            success: 成功状态过滤（可选）
            resource_type: 资源类型过滤（可选）

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
                            if success is not None and entry.get("success") != success:
                                continue
                            if resource_type and entry.get("resource_type") != resource_type:
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
                        except ValueError:
                            continue
            except Exception as e:
                logger.error(f"读取日志文件失败: {json_file} - {e}")

        # 按时间倒序排序
        entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return entries[:limit]

    def get_recent_logs(self, limit: int = 50, success: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        获取最近的日志（先查缓存）

        Args:
            limit: 返回数量限制
            success: 成功状态过滤（可选）

        Returns:
            日志条目列表
        """
        # 先从内存缓存获取
        with self._cache_lock:
            cache_entries = list(self._memory_cache)

        if success is not None:
            cache_entries = [e for e in cache_entries if e.get("success") == success]

        cache_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        if len(cache_entries) >= limit:
            return cache_entries[:limit]

        # 缓存不足，从文件补充
        file_entries = self.query_logs(limit=limit - len(cache_entries), success=success)
        all_entries = cache_entries + file_entries
        all_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return all_entries[:limit]

    def get_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        resource_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取审计日志统计信息

        Args:
            start_date: 起始日期（可选）
            end_date: 结束日期（可选）
            resource_type: 资源类型过滤（可选）

        Returns:
            统计信息字典
        """
        entries = self.query_logs(start_date=start_date, end_date=end_date, limit=10000)

        if resource_type:
            entries = [e for e in entries if e.get("resource_type") == resource_type]

        # 统计
        by_action = {}
        by_user = {}
        by_resource_type = {}
        by_date = {}
        success_count = 0
        error_count = 0
        total_duration = 0.0

        for entry in entries:
            action = entry.get("action", "UNKNOWN")
            user = entry.get("user", "UNKNOWN")
            resource_type_entry = entry.get("resource_type", "UNKNOWN")

            by_action[action] = by_action.get(action, 0) + 1
            by_user[user] = by_user.get(user, 0) + 1
            by_resource_type[resource_type_entry] = by_resource_type.get(resource_type_entry, 0) + 1

            # 按日期统计
            date = entry.get("timestamp", "")[:10]  # YYYY-MM-DD
            by_date[date] = by_date.get(date, 0) + 1

            if entry.get("success", True):
                success_count += 1
            else:
                error_count += 1

            if entry.get("duration_ms"):
                total_duration += entry["duration_ms"]

        return {
            "total_entries": len(entries),
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": success_count / len(entries) if entries else 0,
            "total_duration_ms": round(total_duration, 2),
            "avg_duration_ms": round(total_duration / len(entries), 2) if entries else 0,
            "by_action": by_action,
            "by_user": by_user,
            "by_resource_type": by_resource_type,
            "by_date": by_date,
        }

    def get_user_activity(
        self,
        username: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        获取用户活动统计

        Args:
            username: 用户名
            days: 天数

        Returns:
            活动统计字典
        """
        from datetime import timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        entries = self.query_logs(
            user=username,
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )

        # 统计
        actions = {}
        resources = {}
        success_count = 0
        error_count = 0

        for entry in entries:
            action = entry.get("action", "UNKNOWN")
            resource = entry.get("resource", "UNKNOWN")

            actions[action] = actions.get(action, 0) + 1
            resources[resource] = resources.get(resource, 0) + 1

            if entry.get("success"):
                success_count += 1
            else:
                error_count += 1

        return {
            "username": username,
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_actions": len(entries),
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": round(success_count / len(entries), 2) if entries else 0,
            "actions_breakdown": actions,
            "resources_accessed": dict(list(resources.items())[:20]),  # 仅返回前20个
        }

    def export_logs(
        self,
        user: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json"
    ) -> str:
        """
        导出审计日志

        Args:
            user: 用户名（可选）
            start_date: 起始日期（可选）
            end_date: 结束日期（可选）
            format: 导出格式（json/csv）

        Returns:
            导出的文件路径
        """
        import csv

        entries = self.query_logs(user=user, start_date=start_date, end_date=end_date, limit=10000)

        # 生成导出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = self.log_dir / "exports"
        export_dir.mkdir(exist_ok=True)

        if format == "csv":
            export_file = export_dir / f"audit_export_{timestamp}.csv"
            with open(export_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "timestamp", "action", "user", "resource", "resource_type",
                    "success", "error_message", "ip_address"
                ])
                writer.writeheader()
                for entry in entries:
                    writer.writerow({
                        k: entry.get(k, "") for k in writer.fieldnames
                    })
        else:  # json
            export_file = export_dir / f"audit_export_{timestamp}.json"
            with open(export_file, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)

        logger.info(f"审计日志导出: {export_file}")
        return str(export_file)


# 全局审计日志实例
_audit_logger_instance: Optional[AuditLogger] = None
_audit_logger_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """
    获取审计日志实例（单例模式，线程安全）

    Returns:
        AuditLogger实例
    """
    global _audit_logger_instance

    with _audit_logger_lock:
        if _audit_logger_instance is None:
            _audit_logger_instance = AuditLogger()
        return _audit_logger_instance


def clear_audit_logger() -> None:
    """清除全局审计日志实例（用于测试）"""
    global _audit_logger_instance
    _audit_logger_instance = None


class APIAuditMiddleware:
    """API审计中间件 - 自动记录所有API访问"""

    def __init__(self, app):
        self.app = app
        self.exempt_paths = {"/api/health", "/api/auth/token", "/api/auth/register", "/docs", "/openapi.json", "/api/auth/me"}

    async def __call__(self, scope, receive, send):
        """Middleware调用"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        # 检查是否为 exempt 路径
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            await self.app(scope, receive, send)
            return

        # 记录开始时间
        start_time = datetime.now()

        # 构建请求信息
        headers = dict(request.headers)
        client_host = request.client.host if request.client else None

        # 尝试获取用户信息
        user = "anonymous"
        if hasattr(request.state, "current_user"):
            user = request.state.current_user.username

        # 获取请求ID
        request_id = headers.get("x-request-id")

        try:
            # 处理请求
            async def wrapped_send(message):
                """包装 send 以记录响应"""
                if message["type"] == "http.response.start":
                    # 计算耗时
                    duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                    # 记录日志
                    try:
                        audit_logger = get_audit_logger()
                        audit_logger.log_api_access(
                            user=user,
                            endpoint=path,
                            method=request.method,
                            details={
                                "status_code": message.get("status", 200),
                                "headers": {k: v for k, v in headers.items() if k.lower() not in ["authorization"]},
                            },
                            ip_address=client_host,
                            success=True,
                            duration_ms=duration_ms,
                            request_id=request_id,
                        )
                    except Exception as e:
                        logger.error(f"记录审计日志失败: {e}")

                await send(message)

            await self.app(scope, receive, wrapped_send)

        except Exception as e:
            # 记录异常
            try:
                audit_logger = get_audit_logger()
                audit_logger.log_api_access(
                    user=user,
                    endpoint=path,
                    method=request.method,
                    details={"error": str(e)},
                    ip_address=client_host,
                    success=False,
                    request_id=request_id,
                )
            except Exception:
                pass

            raise

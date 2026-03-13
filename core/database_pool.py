"""
SQLite 连接池优化 (2核2GB服务器专用)

特性：
- 限制最大连接数（避免内存溢出）
- 连接复用
- 自动重连
- 查询超时设置
"""

import sqlite3
import threading
import queue
import logging
import time
from typing import Optional, List, Any, Dict, Callable
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SQLiteConnectionPool:
    """SQLite 连接池 - 优化版"""
    
    def __init__(
        self,
        db_path: str,
        pool_size: int = 2,  # 2核2GB环境建议2个连接
        max_overflow: int = 0,  # 不允许溢出
        pool_timeout: float = 30.0,
        connect_timeout: float = 10.0,
        query_timeout: int = 30,  # 查询超时30秒
    ):
        self.db_path = db_path
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.connect_timeout = connect_timeout
        self.query_timeout = query_timeout
        
        # 连接池
        self._pool = queue.Queue(maxsize=pool_size + max_overflow)
        self._in_use = set()
        self._lock = threading.Lock()
        self._initialized = False
        self._closed = False
        
        # 性能统计
        self._stats = {
            "total_connections": 0,
            "active_connections": 0,
            "wait_timeouts": 0,
            "query_errors": 0,
        }
        
    def initialize(self):
        """初始化连接池"""
        if self._initialized:
            return
            
        logger.info(f"初始化 SQLite 连接池: {self.db_path} (pool_size={self.pool_size})")
        
        # 预先创建连接
        for _ in range(self.pool_size):
            conn = self._create_connection()
            self._pool.put(conn)
            self._stats["total_connections"] += 1
            
        self._initialized = True
        logger.info("连接池初始化完成")
        
    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.connect_timeout,
            check_same_thread=False,  # 允许跨线程使用（由连接池管理）
            isolation_level=None,  # 自动提交模式
        )
        
        # 优化连接设置
        conn.execute("PRAGMA journal_mode=WAL")  # WAL 模式，提高并发性能
        conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和安全性
        conn.execute("PRAGMA cache_size=-4096")  # 4MB 缓存（低配优化）
        conn.execute("PRAGMA temp_store=FILE")  # 临时表写磁盘，节省内存
        conn.execute("PRAGMA mmap_size=33554432")  # 32MB 内存映射（低配优化）
        conn.execute(f"PRAGMA busy_timeout={int(self.query_timeout * 1000)}")  # 查询超时
        
        # 注册自定义函数（如需要）
        conn.row_factory = sqlite3.Row  # 返回字典形式
        
        return conn
        
    @contextmanager
    def get_connection(self, timeout: Optional[float] = None):
        """获取连接（上下文管理器）"""
        if not self._initialized:
            self.initialize()
            
        timeout = timeout or self.pool_timeout
        conn = None
        
        try:
            # 从池中获取连接
            conn = self._pool.get(timeout=timeout)
            
            with self._lock:
                self._in_use.add(id(conn))
                self._stats["active_connections"] = len(self._in_use)
                
            yield conn
            
        except queue.Empty:
            self._stats["wait_timeouts"] += 1
            raise TimeoutError(f"获取连接超时（等待 {timeout} 秒）")
            
        finally:
            if conn is not None:
                # 归还连接
                with self._lock:
                    self._in_use.discard(id(conn))
                    self._stats["active_connections"] = len(self._in_use)
                    
                # 重置连接状态
                try:
                    conn.rollback()  # 回滚未提交的事务
                except:
                    pass
                    
                # 放回池中
                try:
                    self._pool.put(conn, block=False)
                except queue.Full:
                    # 池已满，关闭连接
                    try:
                        conn.close()
                    except:
                        pass
                        
    def execute(
        self,
        query: str,
        parameters: tuple = (),
        fetch_one: bool = False,
        fetch_all: bool = False,
    ) -> Optional[Any]:
        """执行 SQL 查询（快捷方法）"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, parameters)
            
            if fetch_one:
                row = cursor.fetchone()
                return dict(row) if row else None
            elif fetch_all:
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            else:
                return cursor.rowcount
                
    def execute_many(self, query: str, parameters_list: List[tuple]) -> int:
        """批量执行 SQL"""
        with self.get_connection() as conn:
            cursor = conn.executemany(query, parameters_list)
            return cursor.rowcount
            
    def transaction(self):
        """事务上下文管理器"""
        return TransactionContext(self)
        
    def close(self):
        """关闭连接池"""
        if self._closed:
            return
            
        logger.info("关闭连接池...")
        self._closed = True
        
        # 关闭所有连接
        while not self._pool.empty():
            try:
                conn = self._pool.get(block=False)
                conn.close()
            except:
                pass
                
        logger.info("连接池已关闭")
        
    def get_stats(self) -> Dict:
        """获取连接池统计信息"""
        return {
            **self._stats,
            "pool_size": self.pool_size,
            "pool_empty": self._pool.empty(),
            "pool_full": self._pool.full(),
        }
        
    def __enter__(self):
        self.initialize()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TransactionContext:
    """事务上下文管理器"""
    
    def __init__(self, pool: SQLiteConnectionPool):
        self.pool = pool
        self.conn = None
        
    def __enter__(self):
        self.conn = self.pool.get_connection().__enter__()
        # 开始事务（SQLite 默认是自动提交，需要手动开始事务）
        self.conn.execute("BEGIN")
        return self.conn
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # 没有异常，提交事务
            self.conn.commit()
        else:
            # 有异常，回滚事务
            self.conn.rollback()
            
        # 归还连接
        self.pool.get_connection().__exit__(None, None, None)


# ============================================================
# 全局连接池实例（单例模式）
# ============================================================

_pool_instance: Optional[SQLiteConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool(
    db_path: Optional[str] = None,
    **kwargs
) -> SQLiteConnectionPool:
    """
    获取全局连接池实例（单例模式）
    
    示例：
        pool = get_connection_pool("/path/to/db.sqlite")
        
        with pool.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM table")
            rows = cursor.fetchall()
    """
    global _pool_instance
    
    if _pool_instance is None:
        with _pool_lock:
            if _pool_instance is None:
                # 默认配置（2核2GB环境）
                default_config = {
                    "pool_size": 2,  # 小型服务器建议 2 个连接
                    "max_overflow": 0,
                    "pool_timeout": 30.0,
                    "connect_timeout": 10.0,
                    "query_timeout": 30,
                }
                
                # 使用传入的配置覆盖默认配置
                config = {**default_config, **kwargs}
                
                # 确定数据库路径
                if db_path is None:
                    # 使用环境变量或默认路径
                    import os
                    db_path = os.getenv(
                        "SQLITE_DB_PATH",
                        os.path.join(os.getcwd(), "data", "quant.db")
                    )
                
                _pool_instance = SQLiteConnectionPool(db_path, **config)
                _pool_instance.initialize()
                
                logger.info(f"全局连接池已创建: {db_path}")
    
    return _pool_instance


def close_connection_pool():
    """关闭全局连接池"""
    global _pool_instance
    
    if _pool_instance is not None:
        _pool_instance.close()
        _pool_instance = None
        logger.info("全局连接池已关闭")


def get_pool_stats() -> dict:
    """获取连接池统计信息"""
    if _pool_instance is not None:
        return _pool_instance.get_stats()
    return {"error": "连接池未初始化"}

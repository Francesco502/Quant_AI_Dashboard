"""
LRU 缓存模块 (2核2GB服务器专用)

特性：
- 内存受限的 LRU 缓存
- 自动过期
- 内存使用监控
- 线程安全
"""

import time
import threading
import functools
import logging
from typing import Dict, Any, Optional, Callable, TypeVar, Generic
from collections import OrderedDict

logger = logging.getLogger(__name__)

T = TypeVar('T')


class LRUCache(Generic[T]):
    """
    线程安全的 LRU 缓存
    
    特性：
    - 基于 OrderedDict 实现 O(1) 操作
    - 支持 TTL（生存时间）
    - 内存使用上限
    - 自动清理过期项
    """
    
    def __init__(
        self,
        max_size: int = 50,  # 最大缓存项数（低配优化）
        ttl: Optional[float] = None,  # 默认 TTL（秒）
        max_memory_mb: Optional[float] = 20.0,  # 最大内存使用 20MB（低配优化）
        cleanup_interval: int = 100,  # 每 N 次操作执行清理
    ):
        self.max_size = max_size
        self.default_ttl = ttl
        self.max_memory_mb = max_memory_mb
        self.cleanup_interval = cleanup_interval
        
        # 缓存存储
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()
        
        # 统计
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
            "cleanups": 0,
        }
        
        self._operation_count = 0
        
    def _is_expired(self, item: Dict[str, Any]) -> bool:
        """检查缓存项是否过期"""
        if item["expires_at"] is None:
            return False
        return time.time() > item["expires_at"]
        
    def _cleanup_expired(self):
        """清理过期项"""
        expired_keys = []
        
        for key, item in self._cache.items():
            if self._is_expired(item):
                expired_keys.append(key)
                
        for key in expired_keys:
            del self._cache[key]
            self._stats["expirations"] += 1
            
        if expired_keys:
            logger.debug(f"LRU 清理: 移除 {len(expired_keys)} 个过期项")
            
    def _evict_if_needed(self):
        """如果需要，淘汰最少使用的项"""
        while len(self._cache) >= self.max_size:
            try:
                # 移除最老的项
                key, item = self._cache.popitem(last=False)
                self._stats["evictions"] += 1
                logger.debug(f"LRU 淘汰: {key}")
            except KeyError:
                break
                
    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """获取缓存项"""
        with self._lock:
            self._operation_count += 1
            
            # 定期清理
            if self._operation_count % self.cleanup_interval == 0:
                self._cleanup_expired()
                self._stats["cleanups"] += 1
                
            if key not in self._cache:
                self._stats["misses"] += 1
                return default
                
            item = self._cache[key]
            
            # 检查是否过期
            if self._is_expired(item):
                del self._cache[key]
                self._stats["expirations"] += 1
                self._stats["misses"] += 1
                return default
                
            # 移动到末尾（最近使用）
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            
            return item["value"]
            
    def set(
        self,
        key: str,
        value: T,
        ttl: Optional[float] = None,
    ) -> None:
        """设置缓存项"""
        with self._lock:
            # 计算过期时间
            expires_at = None
            if ttl is not None:
                expires_at = time.time() + ttl
            elif self.default_ttl is not None:
                expires_at = time.time() + self.default_ttl
                
            # 淘汰旧项
            self._evict_if_needed()
            
            # 设置新值
            self._cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": time.time(),
            }
            
    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
            
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            logger.info("LRU 缓存已清空")
            
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (
                self._stats["hits"] / total_requests * 100
                if total_requests > 0
                else 0
            )
            
            return {
                **self._stats,
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate": round(hit_rate, 2),
                "total_requests": total_requests,
            }


# ============================================================
# 全局缓存实例（单例模式）
# ============================================================

_global_cache: Optional[LRUCache] = None
_cache_lock = threading.Lock()


def get_cache(
    max_size: int = 100,
    ttl: Optional[float] = None,
) -> LRUCache:
    """
    获取全局缓存实例（单例模式）
    
    示例：
        cache = get_cache(max_size=200, ttl=300)  # 缓存5分钟
        
        # 获取或计算
        result = cache.get("key")
        if result is None:
            result = expensive_computation()
            cache.set("key", result, ttl=600)
    """
    global _global_cache
    
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = LRUCache(
                    max_size=max_size,
                    ttl=ttl,
                    max_memory_mb=50,  # 限制50MB
                )
                logger.info(f"全局 LRU 缓存已创建 (max_size={max_size}, ttl={ttl})")
    
    return _global_cache


def cached(
    max_size: int = 128,
    ttl: Optional[float] = None,
    key_func: Optional[Callable] = None,
):
    """
    缓存装饰器
    
    示例：
        @cached(max_size=100, ttl=300)
        def get_user(user_id: int) -> dict:
            return db.query(User).get(user_id).to_dict()
            
        @cached(ttl=60, key_func=lambda symbol, period: f"{symbol}_{period}")
        def get_price(symbol: str, period: str) -> list:
            return fetch_price_from_api(symbol, period)
    """
    cache = LRUCache(max_size=max_size, ttl=ttl)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 默认使用函数名 + 参数
                cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
                
            # 尝试从缓存获取
            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"缓存命中: {cache_key}")
                return result
                
            # 执行函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            cache.set(cache_key, result)
            logger.debug(f"缓存存储: {cache_key}")
            
            return result
            
        # 暴露缓存操作方法
        wrapper.cache = cache
        wrapper.clear_cache = cache.clear
        wrapper.get_cache_stats = cache.get_stats
        
        return wrapper
    return decorator


def clear_global_cache():
    """清空全局缓存"""
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()
        logger.info("全局缓存已清空")


def get_cache_stats() -> Dict:
    """获取全局缓存统计"""
    global _global_cache
    if _global_cache is not None:
        return _global_cache.get_stats()
    return {"error": "缓存未初始化"}

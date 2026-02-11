"""多级缓存系统

职责：
- 建立多级缓存（内存、磁盘）
- 减少重复计算
- 支持TTL和缓存失效
"""

from __future__ import annotations

import os
import json
import pickle
import hashlib
import time
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from pathlib import Path
import logging




logger = logging.getLogger(__name__)


class MemoryCache:
    """L1缓存：内存缓存（最快）"""
    
    def __init__(self, max_size: int = 1000):
        """
        初始化内存缓存

        Args:
            max_size: 最大缓存项数
        """
        self.cache: Dict[str, tuple[Any, float]] = {}
        self.max_size = max_size
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            return value
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存值"""
        # 如果超过最大大小，删除最旧的项
        if len(self.cache) >= self.max_size:
            # 删除最旧的项（简单策略：删除第一个）
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        timestamp = time.time() + (ttl if ttl else float('inf'))
        self.cache[key] = (value, timestamp)
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
    
    def _cleanup_expired(self):
        """清理过期项"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if timestamp < current_time
        ]
        for key in expired_keys:
            del self.cache[key]


class DiskCache:
    """L2缓存：磁盘缓存"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        初始化磁盘缓存

        Args:
            cache_dir: 缓存目录（可选，默认使用data/cache）
        """
        if cache_dir is None:
            from .data_store import BASE_DIR
            cache_dir = os.path.join(BASE_DIR, "cache")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        # 使用哈希避免文件名过长
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.pkl"
    
    def _get_meta_path(self, key: str) -> Path:
        """获取元数据文件路径"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.meta"
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        cache_path = self._get_cache_path(key)
        meta_path = self._get_meta_path(key)
        
        if not cache_path.exists() or not meta_path.exists():
            return None
        
        try:
            # 检查是否过期
            with open(meta_path, "r") as f:
                meta = json.load(f)
            
            if "expires_at" in meta:
                expires_at = datetime.fromisoformat(meta["expires_at"])
                if datetime.now() > expires_at:
                    # 已过期，删除文件
                    cache_path.unlink()
                    meta_path.unlink()
                    return None
            
            # 读取缓存值
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"读取磁盘缓存失败: {key} - {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存值"""
        cache_path = self._get_cache_path(key)
        meta_path = self._get_meta_path(key)
        
        try:
            # 保存缓存值
            with open(cache_path, "wb") as f:
                pickle.dump(value, f)
            
            # 保存元数据
            meta = {
                "key": key,
                "created_at": datetime.now().isoformat(),
            }
            
            if ttl:
                expires_at = datetime.now() + timedelta(seconds=ttl)
                meta["expires_at"] = expires_at.isoformat()
            
            with open(meta_path, "w") as f:
                json.dump(meta, f)
        except Exception as e:
            logger.error(f"写入磁盘缓存失败: {key} - {e}")
    
    def clear(self):
        """清空缓存"""
        for file in self.cache_dir.glob("*.pkl"):
            file.unlink()
        for file in self.cache_dir.glob("*.meta"):
            file.unlink()
    
    def delete(self, key: str):
        """删除指定缓存"""
        cache_path = self._get_cache_path(key)
        meta_path = self._get_meta_path(key)
        
        if cache_path.exists():
            cache_path.unlink()
        if meta_path.exists():
            meta_path.unlink()


class MultiLevelCache:
    """多级缓存系统"""
    
    def __init__(
        self,
        l1_max_size: int = 1000,
        cache_dir: Optional[str] = None
    ):
        """
        初始化多级缓存

        Args:
            l1_max_size: L1缓存最大项数
            cache_dir: L2缓存目录
        """
        self.l1_cache = MemoryCache(max_size=l1_max_size)
        self.l2_cache = DiskCache(cache_dir=cache_dir)
    
    def get(
        self,
        key: str,
        default: Any = None
    ) -> Any:
        """
        获取缓存值（按L1 -> L2 的顺序）

        Args:
            key: 缓存键
            default: 默认值

        Returns:
            缓存值或默认值
        """
        # L1缓存
        value = self.l1_cache.get(key)
        if value is not None:
            return value
        
        # L2缓存
        value = self.l2_cache.get(key)
        if value is not None:
            # 提升到L1
            self.l1_cache.set(key, value)
            return value
        
        return default
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        level: Optional[int] = None
    ):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
            level: 缓存级别（1=L1, 2=L2, None=全部）
        """
        if level is None or level == 1:
            self.l1_cache.set(key, value, ttl)
        
        if level is None or level == 2:
            self.l2_cache.set(key, value, ttl)
    
    def delete(self, key: str):
        """删除缓存（所有级别）"""
        self.l1_cache.cache.pop(key, None)
        self.l2_cache.delete(key)
    
    def clear(self):
        """清空所有缓存"""
        self.l1_cache.clear()
        self.l2_cache.clear()
    
    def get_statistics(self) -> Dict:
        """获取缓存统计信息"""
        return {
            "l1_size": len(self.l1_cache.cache),
            "l1_max_size": self.l1_cache.max_size,
            "l2_dir": str(self.l2_cache.cache_dir),
            "l2_file_count": len(list(self.l2_cache.cache_dir.glob("*.pkl"))),
        }


# 全局缓存实例（延迟初始化）
_cache_instance: Optional[MultiLevelCache] = None


def get_cache() -> MultiLevelCache:
    """获取缓存实例（单例模式）"""
    global _cache_instance
    
    if _cache_instance is None:
        _cache_instance = MultiLevelCache()
    
    return _cache_instance


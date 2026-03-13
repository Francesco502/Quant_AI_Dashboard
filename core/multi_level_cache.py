"""多级缓存系统（优化版）

职责：
- 建立多级缓存（内存、磁盘）
- 减少重复计算
- 支持 TTL 和缓存失效
- LRU 淘汰策略，限制内存占用

优化说明：
- 2026-03-03: 添加 LRU 淘汰策略，限制内存缓存大小
- 2026-03-03: 添加缓存统计和清理方法
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
from collections import OrderedDict


logger = logging.getLogger(__name__)


class MemoryCache:
    """L1 缓存：内存缓存（最快）- LRU 实现"""

    def __init__(self, max_size: int = 500):  # 默认从 1000 降为 500，减少内存占用
        """
        初始化内存缓存

        Args:
            max_size: 最大缓存项数（默认 500，减少内存占用）
        """
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值（LRU：访问后移到末尾）"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            # 检查是否过期
            if timestamp < time.time():
                del self.cache[key]
                self.misses += 1
                return None
            # 移到末尾（最近使用）
            self.cache.move_to_end(key)
            self.hits += 1
            return value
        self.misses += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存值（LRU：新项放在末尾）"""
        # 如果超过最大大小，删除最旧的项（头部）
        if len(self.cache) >= self.max_size:
            # 删除最旧的项（LRU 淘汰）
            self.cache.popitem(last=False)

        timestamp = time.time() + (ttl if ttl else float('inf'))
        self.cache[key] = (value, timestamp)
        # 移到末尾（最近使用）
        self.cache.move_to_end(key)

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f'{hit_rate:.2%}',
            'current_size': len(self.cache),
            'max_size': self.max_size,
        }

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
    """L2 缓存：磁盘缓存"""

    def __init__(self, cache_dir: Optional[str] = None):
        """
        初始化磁盘缓存

        Args:
            cache_dir: 缓存目录（可选，默认使用 data/cache）
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

        if not cache_path.exists():
            return None

        try:
            # 检查元数据（TTL）
            if meta_path.exists():
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                if meta.get('expire_at', float('inf')) < time.time():
                    # 已过期，删除
                    cache_path.unlink(missing_ok=True)
                    meta_path.unlink(missing_ok=True)
                    return None

            # 读取缓存
            with open(cache_path, 'rb') as f:
                value = pickle.load(f)
            return value
        except Exception as e:
            logger.warning(f"磁盘缓存读取失败：{key}, {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存值"""
        cache_path = self._get_cache_path(key)
        meta_path = self._get_meta_path(key)

        try:
            # 写入缓存
            with open(cache_path, 'wb') as f:
                pickle.dump(value, f)

            # 写入元数据
            meta = {
                'created_at': time.time(),
                'key': key,
            }
            if ttl is not None:
                meta['expire_at'] = time.time() + ttl

            with open(meta_path, 'w') as f:
                json.dump(meta, f)

        except Exception as e:
            logger.warning(f"磁盘缓存写入失败：{key}, {e}")

    def clear(self):
        """清空缓存"""
        for file in self.cache_dir.glob("*.pkl"):
            file.unlink(missing_ok=True)
        for file in self.cache_dir.glob("*.meta"):
            file.unlink(missing_ok=True)


class MultiLevelCache:
    """多级缓存管理器"""

    def __init__(
        self,
        memory_cache_size: int = 500,
        disk_cache_dir: Optional[str] = None,
        default_ttl: Optional[int] = None,
    ):
        """
        初始化多级缓存

        Args:
            memory_cache_size: 内存缓存大小（默认 500）
            disk_cache_dir: 磁盘缓存目录
            default_ttl: 默认 TTL（秒）
        """
        self.memory_cache = MemoryCache(max_size=memory_cache_size)
        self.disk_cache = DiskCache(cache_dir=disk_cache_dir)
        self.default_ttl = default_ttl or 3600  # 默认 1 小时

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存（先内存，后磁盘）

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回 None
        """
        # 1. 尝试内存缓存
        value = self.memory_cache.get(key)
        if value is not None:
            return value

        # 2. 尝试磁盘缓存
        value = self.disk_cache.get(key)
        if value is not None:
            # 写回内存缓存
            self.memory_cache.set(key, value, ttl=self.default_ttl)
            return value

        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置缓存（同时写入内存和磁盘）

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
        """
        ttl = ttl if ttl is not None else self.default_ttl

        # 1. 写入内存缓存
        self.memory_cache.set(key, value, ttl=ttl)

        # 2. 写入磁盘缓存
        self.disk_cache.set(key, value, ttl=ttl)

    def delete(self, key: str):
        """
        删除缓存

        Args:
            key: 缓存键
        """
        # 删除内存缓存
        if key in self.memory_cache.cache:
            del self.memory_cache.cache[key]

        # 删除磁盘缓存
        cache_path = self.disk_cache._get_cache_path(key)
        meta_path = self.disk_cache._get_meta_path(key)
        cache_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)

    def clear(self):
        """清空所有缓存"""
        self.memory_cache.clear()
        self.disk_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            'memory_cache': self.memory_cache.get_stats(),
            'disk_cache': {
                'directory': str(self.disk_cache.cache_dir),
            },
        }


# 全局缓存实例
_cache: Optional[MultiLevelCache] = None


def get_cache(
    memory_cache_size: int = 500,
    disk_cache_dir: Optional[str] = None,
    default_ttl: Optional[int] = None,
) -> MultiLevelCache:
    """
    获取缓存实例（单例模式）

    Args:
        memory_cache_size: 内存缓存大小
        disk_cache_dir: 磁盘缓存目录
        default_ttl: 默认 TTL

    Returns:
        缓存实例
    """
    global _cache
    if _cache is None:
        _cache = MultiLevelCache(
            memory_cache_size=memory_cache_size,
            disk_cache_dir=disk_cache_dir,
            default_ttl=default_ttl,
        )
    return _cache

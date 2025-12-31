"""多级缓存测试"""

import pytest
import tempfile
import os
from core.multi_level_cache import MultiLevelCache, MemoryCache, DiskCache


class TestMemoryCache:
    """测试内存缓存"""
    
    @pytest.fixture
    def cache(self):
        """创建内存缓存实例"""
        return MemoryCache(max_size=10)
    
    def test_get_set(self, cache):
        """测试获取和设置"""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
    
    def test_max_size(self, cache):
        """测试最大大小限制"""
        # 添加超过最大大小的项
        for i in range(15):
            cache.set(f"key{i}", f"value{i}")
        
        # 应该只保留最新的10个
        assert len(cache.cache) <= 10
    
    def test_clear(self, cache):
        """测试清空缓存"""
        cache.set("key1", "value1")
        cache.clear()
        assert cache.get("key1") is None


class TestDiskCache:
    """测试磁盘缓存"""
    
    @pytest.fixture
    def cache(self):
        """创建临时磁盘缓存"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir)
            yield cache
    
    def test_get_set(self, cache):
        """测试获取和设置"""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
    
    def test_ttl(self, cache):
        """测试TTL过期"""
        cache.set("key1", "value1", ttl=0.1)  # 0.1秒过期
        
        # 立即获取应该成功
        assert cache.get("key1") == "value1"
        
        # 等待过期
        import time
        time.sleep(0.2)
        
        # 应该返回None
        assert cache.get("key1") is None
    
    def test_delete(self, cache):
        """测试删除"""
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None


class TestMultiLevelCache:
    """测试多级缓存"""
    
    @pytest.fixture
    def cache(self):
        """创建多级缓存实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MultiLevelCache(cache_dir=tmpdir, use_streamlit_cache=False)
            yield cache
    
    def test_l1_cache(self, cache):
        """测试L1缓存"""
        cache.set("key1", "value1", level=1)
        assert cache.get("key1") == "value1"
    
    def test_l2_cache(self, cache):
        """测试L2缓存"""
        cache.set("key1", "value1", level=2)
        assert cache.get("key1") == "value1"
        
        # 应该提升到L1
        assert cache.l1_cache.get("key1") == "value1"
    
    def test_multi_level(self, cache):
        """测试多级缓存流程"""
        # 设置到L2
        cache.set("key1", "value1", level=2)
        
        # 清空L1
        cache.l1_cache.clear()
        
        # 从L2获取，应该提升到L1
        value = cache.get("key1")
        assert value == "value1"
        assert cache.l1_cache.get("key1") == "value1"
    
    def test_delete(self, cache):
        """测试删除"""
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None
    
    def test_clear(self, cache):
        """测试清空"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None


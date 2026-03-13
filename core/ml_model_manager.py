"""
ML 模型懒加载管理器 (2核2GB服务器专用)

特性：
- 按需加载 ML 模型（Prophet/XGBoost/LightGBM/LSTM）
- 自动卸载不常用的模型
- 内存使用监控
- 线程安全
"""

import os
import gc
import time
import threading
import logging
from typing import Dict, Any, Optional, Callable, Type, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ModelStatus(Enum):
    """模型状态"""
    UNLOADED = "unloaded"  # 未加载
    LOADING = "loading"    # 加载中
    LOADED = "loaded"      # 已加载
    ERROR = "error"        # 加载失败


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    model_class: Optional[Type] = None
    model_instance: Any = None
    status: ModelStatus = ModelStatus.UNLOADED
    last_used: float = field(default_factory=time.time)
    load_count: int = 0
    error_count: int = 0
    memory_estimate_mb: float = 0.0
    auto_unload_after: Optional[float] = 120.0  # 2分钟后自动卸载（低配优化）
    
    def touch(self):
        """更新最后使用时间"""
        self.last_used = time.time()


class MLModelManager:
    """
    ML 模型管理器
    
    单例模式，全局统一管理 ML 模型的加载和卸载
    """
    
    _instance: Optional['MLModelManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(
        self,
        max_memory_mb: float = 200.0,  # 最大内存使用 200MB（低配优化）
        auto_unload_interval: float = 30.0,  # 每30秒检查一次（低配优化）
    ):
        if self._initialized:
            return
            
        self.max_memory_mb = max_memory_mb
        self.auto_unload_interval = auto_unload_interval
        
        self._models: Dict[str, ModelInfo] = {}
        self._lock = threading.RLock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        
        self._initialized = True
        
        # 启动自动清理线程
        self._start_cleanup_thread()
        
        logger.info(f"MLModelManager 初始化完成 (max_memory={max_memory_mb}MB)")
    
    def register_model(
        self,
        name: str,
        model_class: Optional[Type] = None,
        memory_estimate_mb: float = 100.0,
        auto_unload_after: Optional[float] = 120.0,  # 低配优化：2分钟
    ) -> ModelInfo:
        """
        注册模型（不加载）
        
        Args:
            name: 模型名称
            model_class: 模型类（用于延迟实例化）
            memory_estimate_mb: 预估内存使用
            auto_unload_after: 自动卸载时间（秒）
        """
        with self._lock:
            if name not in self._models:
                self._models[name] = ModelInfo(
                    name=name,
                    model_class=model_class,
                    memory_estimate_mb=memory_estimate_mb,
                    auto_unload_after=auto_unload_after,
                )
                logger.debug(f"模型已注册: {name}")
            return self._models[name]
    
    def load_model(
        self,
        name: str,
        loader: Optional[Callable[[], Any]] = None,
        force_reload: bool = False,
    ) -> Any:
        """
        加载模型（懒加载）
        
        Args:
            name: 模型名称
            loader: 加载函数（如果 model_class 不够）
            force_reload: 强制重新加载
            
        Returns:
            模型实例
        """
        with self._lock:
            if name not in self._models:
                raise ValueError(f"模型未注册: {name}")
            
            info = self._models[name]
            
            # 检查是否需要加载
            if info.status == ModelStatus.LOADED and not force_reload:
                info.touch()
                return info.model_instance
            
            if info.status == ModelStatus.LOADING:
                # 等待加载完成
                # 简化实现：直接返回 None，实际应该使用 Condition
                logger.warning(f"模型 {name} 正在加载中...")
                return None
            
            # 开始加载
            info.status = ModelStatus.LOADING
            info.load_count += 1
        
        # 在锁外执行加载（避免阻塞其他线程）
        try:
            logger.info(f"加载模型: {name}")
            
            if loader:
                model_instance = loader()
            elif info.model_class:
                model_instance = info.model_class()
            else:
                raise ValueError(f"模型 {name} 没有指定加载方式")
            
            # 更新状态
            with self._lock:
                info.model_instance = model_instance
                info.status = ModelStatus.LOADED
                info.touch()
            
            logger.info(f"模型加载完成: {name}")
            return model_instance
            
        except Exception as e:
            with self._lock:
                info.status = ModelStatus.ERROR
                info.error_count += 1
            
            logger.error(f"模型加载失败 {name}: {e}")
            raise
    
    def unload_model(self, name: str) -> bool:
        """
        卸载模型，释放内存
        
        Args:
            name: 模型名称
            
        Returns:
            是否成功卸载
        """
        with self._lock:
            if name not in self._models:
                return False
            
            info = self._models[name]
            
            if info.status != ModelStatus.LOADED:
                return False
            
            # 释放引用
            info.model_instance = None
            info.status = ModelStatus.UNLOADED
        
        # 强制垃圾回收
        gc.collect()
        
        logger.info(f"模型已卸载: {name}")
        return True
    
    def get_model(self, name: str) -> Optional[Any]:
        """获取已加载的模型实例"""
        with self._lock:
            if name in self._models:
                info = self._models[name]
                if info.status == ModelStatus.LOADED:
                    info.touch()
                    return info.model_instance
        return None
    
    def get_model_info(self, name: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        with self._lock:
            return self._models.get(name)
    
    def list_models(self) -> List[str]:
        """列出所有已注册的模型"""
        with self._lock:
            return list(self._models.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        with self._lock:
            total_memory = sum(
                info.memory_estimate_mb
                for info in self._models.values()
                if info.status == ModelStatus.LOADED
            )
            
            return {
                "total_models": len(self._models),
                "loaded_models": sum(
                    1 for info in self._models.values()
                    if info.status == ModelStatus.LOADED
                ),
                "loading_models": sum(
                    1 for info in self._models.values()
                    if info.status == ModelStatus.LOADING
                ),
                "error_models": sum(
                    1 for info in self._models.values()
                    if info.status == ModelStatus.ERROR
                ),
                "estimated_memory_mb": total_memory,
                "max_memory_mb": self.max_memory_mb,
                "memory_usage_percent": (
                    (total_memory / self.max_memory_mb) * 100
                    if self.max_memory_mb > 0
                    else 0
                ),
            }
    
    def _start_cleanup_thread(self):
        """启动自动清理线程"""
        def cleanup_worker():
            while not self._stop_cleanup.wait(timeout=self.auto_unload_interval):
                self._auto_cleanup()
        
        self._cleanup_thread = threading.Thread(
            target=cleanup_worker,
            name="MLModelManager-Cleanup",
            daemon=True,
        )
        self._cleanup_thread.start()
        logger.debug("自动清理线程已启动")
    
    def _auto_cleanup(self):
        """自动清理不常用的模型"""
        with self._lock:
            now = time.time()
            to_unload = []
            
            for name, info in self._models.items():
                if info.status != ModelStatus.LOADED:
                    continue
                
                # 检查是否超过自动卸载时间
                if info.auto_unload_after is not None:
                    idle_time = now - info.last_used
                    if idle_time > info.auto_unload_after:
                        to_unload.append(name)
            
            # 检查内存使用
            stats = self.get_stats()
            if stats["memory_usage_percent"] > 80:
                # 内存使用超过80%，按最后使用时间排序，卸载最老的
                loaded_models = [
                    (name, info)
                    for name, info in self._models.items()
                    if info.status == ModelStatus.LOADED
                ]
                loaded_models.sort(key=lambda x: x[1].last_used)
                
                # 卸载一半的模型
                to_unload.extend([name for name, _ in loaded_models[:len(loaded_models)//2]])
        
        # 在锁外执行卸载
        for name in to_unload:
            self.unload_model(name)
    
    def shutdown(self):
        """关闭管理器，释放所有资源"""
        logger.info("关闭 MLModelManager...")
        
        # 停止清理线程
        self._stop_cleanup.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        
        # 卸载所有模型
        with self._lock:
            for name in list(self._models.keys()):
                self.unload_model(name)
        
        # 强制垃圾回收
        gc.collect()
        
        logger.info("MLModelManager 已关闭")


# ============================================================
# 全局模型管理器实例（单例模式）
# ============================================================

_model_manager: Optional[MLModelManager] = None
_manager_lock = threading.Lock()


def get_model_manager(
    max_memory_mb: float = 500.0,
) -> MLModelManager:
    """
    获取全局模型管理器实例（单例模式）
    
    示例：
        manager = get_model_manager(max_memory_mb=400)
        
        # 注册模型
        manager.register_model(
            "prophet_forecaster",
            model_class=Prophet,
            memory_estimate_mb=150,
        )
        
        # 懒加载
        model = manager.load_model("prophet_forecaster")
        
        # 使用
        forecast = model.predict(...)
        
        # 手动卸载（或等待自动卸载）
        manager.unload_model("prophet_forecaster")
    """
    global _model_manager
    
    if _model_manager is None:
        with _manager_lock:
            if _model_manager is None:
                _model_manager = MLModelManager(max_memory_mb=max_memory_mb)
                logger.info(f"全局 MLModelManager 已创建 (max_memory={max_memory_mb}MB)")
    
    return _model_manager


def shutdown_model_manager():
    """关闭全局模型管理器"""
    global _model_manager
    
    if _model_manager is not None:
        _model_manager.shutdown()
        _model_manager = None
        logger.info("全局 MLModelManager 已关闭")


def get_model_manager_stats() -> Dict[str, Any]:
    """获取模型管理器统计信息"""
    global _model_manager
    
    if _model_manager is not None:
        return _model_manager.get_stats()
    return {"error": "模型管理器未初始化"}

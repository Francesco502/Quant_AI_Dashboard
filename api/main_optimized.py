"""
FastAPI 应用入口 - 优化版（2核2GB 服务器专用）

此模块现在委托给 api.main，后者已内置性能优化开关（GZip、并发控制、ML 懒加载）。
保留此模块是为了向后兼容可能直接引用 api.main_optimized:app 的部署配置。
"""

from .main import app

__all__ = ["app"]

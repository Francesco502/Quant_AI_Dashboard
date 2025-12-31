"""版本信息模块"""

# 应用版本号
__version__ = "0.1.4"
VERSION = __version__

# 版本信息详情
VERSION_INFO = {
    "version": __version__,
    "major": 0,
    "minor": 1,
    "patch": 4,
    "build_date": "2025-12-30",
}

def get_version() -> str:
    """获取版本号"""
    return __version__

def get_version_info() -> dict:
    """获取版本信息"""
    return VERSION_INFO.copy()


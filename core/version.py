"""版本信息模块"""

# 应用版本号
__version__ = "0.2.0"
VERSION = __version__

# 版本信息详情
VERSION_INFO = {
    "version": __version__,
    "major": 0,
    "minor": 2,
    "patch": 0,
    "build_date": "2026-02-06",
}

def get_version() -> str:
    """获取版本号"""
    return __version__

def get_version_info() -> dict:
    """获取版本信息"""
    return VERSION_INFO.copy()

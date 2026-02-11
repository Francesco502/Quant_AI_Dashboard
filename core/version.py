"""版本信息模块"""

# 应用版本号
__version__ = "1.0.0"
VERSION = __version__

# 版本信息详情
VERSION_INFO = {
    "version": __version__,
    "major": 1,
    "minor": 0,
    "patch": 0,
    "build_date": "2026-02-11",
}

def get_version() -> str:
    """获取版本号"""
    return __version__

def get_version_info() -> dict:
    """获取版本信息"""
    return VERSION_INFO.copy()

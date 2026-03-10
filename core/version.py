"""Application version metadata."""

__version__ = "1.0.0"
VERSION = __version__

VERSION_INFO = {
    "version": __version__,
    "major": 1,
    "minor": 0,
    "patch": 0,
    "build_date": "2026-03-10",
}


def get_version() -> str:
    """Return semantic version string."""
    return __version__


def get_version_info() -> dict:
    """Return version detail dictionary."""
    return VERSION_INFO.copy()

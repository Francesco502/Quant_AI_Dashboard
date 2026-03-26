"""Application version metadata."""

__version__ = "2.1.4"
VERSION = __version__

VERSION_INFO = {
    "version": __version__,
    "major": 2,
    "minor": 1,
    "patch": 4,
    "prerelease": None,
    "build_date": "2026-03-26",
}


def get_version() -> str:
    """Return semantic version string."""
    return __version__


def get_version_info() -> dict:
    """Return version detail dictionary."""
    return VERSION_INFO.copy()

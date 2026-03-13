"""Application version metadata."""

__version__ = "2.0.0-alpha.1"
VERSION = __version__

VERSION_INFO = {
    "version": __version__,
    "major": 2,
    "minor": 0,
    "patch": 0,
    "prerelease": "alpha.1",
    "build_date": "2026-03-12",
}


def get_version() -> str:
    """Return semantic version string."""
    return __version__


def get_version_info() -> dict:
    """Return version detail dictionary."""
    return VERSION_INFO.copy()

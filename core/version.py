"""Application version metadata."""

__version__ = "2.2.0"
VERSION = __version__

VERSION_INFO = {
    "version": __version__,
    "major": 2,
    "minor": 2,
    "patch": 0,
    "prerelease": None,
    "build_date": "2026-04-15",
}


def get_version() -> str:
    """Return semantic version string."""

    return __version__


def get_version_info() -> dict:
    """Return version detail dictionary."""

    return VERSION_INFO.copy()

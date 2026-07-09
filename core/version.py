"""Application version metadata."""

__version__ = "3.0.0"
VERSION = __version__

VERSION_INFO = {
    "version": __version__,
    "major": 3,
    "minor": 0,
    "patch": 0,
    "prerelease": None,
    "build_date": "2026-07-09",
}


def get_version() -> str:
    """Return semantic version string."""

    return __version__


def get_version_info() -> dict:
    """Return version detail dictionary."""

    return VERSION_INFO.copy()

"""Release version consistency checks."""

from __future__ import annotations

import json
from pathlib import Path

from core.version import VERSION, VERSION_INFO


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_240_across_backend_frontend_and_docs():
    package_json = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "web" / "package-lock.json").read_text(encoding="utf-8"))

    assert VERSION == "2.4.0"
    assert VERSION_INFO["minor"] == 4
    assert VERSION_INFO["patch"] == 0
    assert package_json["version"] == "2.4.0"
    assert package_lock["version"] == "2.4.0"
    assert package_lock["packages"][""]["version"] == "2.4.0"
    assert (ROOT / "docs" / "releases" / "RELEASE_NOTES_v2.4.0.md").exists()

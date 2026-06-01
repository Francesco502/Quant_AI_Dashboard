"""Release version consistency checks."""

from __future__ import annotations

import json
from pathlib import Path

from core.version import VERSION, VERSION_INFO


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_240_across_backend_frontend_and_docs():
    package_json = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "web" / "package-lock.json").read_text(encoding="utf-8"))
    docker_compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerfile_optimized = (ROOT / "Dockerfile.optimized").read_text(encoding="utf-8")
    entrypoint = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
    supervisord = (ROOT / "docker" / "supervisord.conf").read_text(encoding="utf-8")
    release_notes = (ROOT / "docs" / "releases" / "RELEASE_NOTES_v2.4.0.md").read_text(encoding="utf-8")

    assert VERSION == "2.4.0"
    assert VERSION_INFO["minor"] == 4
    assert VERSION_INFO["patch"] == 0
    assert VERSION_INFO["build_date"] == "2026-06-01"
    assert package_json["version"] == "2.4.0"
    assert package_lock["version"] == "2.4.0"
    assert package_lock["packages"][""]["version"] == "2.4.0"
    assert "Release date: 2026-06-01" in release_notes
    assert "francescoli/quant_app:v2.4.0" in docker_compose
    assert "v2.4.0" in dockerfile
    assert "v2.4.0" in dockerfile_optimized
    assert "v2.4.0" in entrypoint
    assert "v2.4.0" in supervisord

"""Release version consistency checks."""

from __future__ import annotations

import json
from pathlib import Path

from core.version import VERSION, VERSION_INFO


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_300_across_backend_frontend_and_docs():
    package_json = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "web" / "package-lock.json").read_text(encoding="utf-8"))
    docker_compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerfile_optimized = (ROOT / "Dockerfile.optimized").read_text(encoding="utf-8")
    entrypoint = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
    supervisord = (ROOT / "docker" / "supervisord.conf").read_text(encoding="utf-8")
    worker_compose = (ROOT / "docker-compose.worker.yml").read_text(encoding="utf-8")
    release_notes = (ROOT / "docs" / "releases" / "RELEASE_NOTES_v3.0.0.md").read_text(encoding="utf-8")

    assert VERSION == "3.0.0"
    assert VERSION_INFO["major"] == 3
    assert VERSION_INFO["minor"] == 0
    assert VERSION_INFO["patch"] == 0
    assert VERSION_INFO["build_date"] == "2026-07-09"
    assert package_json["version"] == "3.0.0"
    assert package_lock["version"] == "3.0.0"
    assert package_lock["packages"][""]["version"] == "3.0.0"
    assert "Release date: 2026-07-09" in release_notes
    assert "francescoli/quant_app:v3.0.0" in docker_compose
    assert "francescoli/quant_app-worker:v3.0.0" in worker_compose
    assert "v3.0.0" in dockerfile
    assert "v3.0.0" in dockerfile_optimized
    assert "v3.0.0" in entrypoint
    assert "v3.0.0" in supervisord

"""Backup creation and listing for personal dashboard data."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .data_store import BASE_DIR
from .version import VERSION


class BackupManager:
    def __init__(self, data_dir: str | Path | None = None, backups_dir: str | Path | None = None):
        self.data_dir = Path(data_dir or BASE_DIR)
        self.backups_dir = Path(backups_dir or self.data_dir / "backups")
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def _manifest(self, *, include_database: bool, include_configs: bool, include_user_files: bool) -> Dict[str, Any]:
        return {
            "version": VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "included": {
                "database": include_database,
                "configs": include_configs,
                "user_files": include_user_files,
            },
        }

    def create_backup(
        self,
        *,
        include_database: bool = True,
        include_configs: bool = True,
        include_user_files: bool = True,
    ) -> Dict[str, Any]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backups_dir / f"quant_ai_backup_{timestamp}.zip"
        manifest = self._manifest(
            include_database=include_database,
            include_configs=include_configs,
            include_user_files=include_user_files,
        )

        with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

            if include_database:
                db_path = self.data_dir / "quant.db"
                if db_path.exists():
                    archive.write(db_path, "data/quant.db")

            if include_configs:
                for path in self.data_dir.glob("*.json"):
                    archive.write(path, f"data/{path.name}")

            if include_user_files:
                for subdir in ("logs/audit", "exports"):
                    base = self.data_dir / subdir
                    if not base.exists():
                        continue
                    for path in base.rglob("*"):
                        if path.is_file():
                            archive.write(path, f"data/{path.relative_to(self.data_dir).as_posix()}")

        return {
            "status": "success",
            "path": str(backup_path),
            "filename": backup_path.name,
            "size_bytes": backup_path.stat().st_size,
            "manifest": manifest,
        }

    def list_backups(self) -> List[Dict[str, Any]]:
        backups: List[Dict[str, Any]] = []
        for path in sorted(self.backups_dir.glob("quant_ai_backup_*.zip"), reverse=True):
            manifest: Dict[str, Any] | None = None
            try:
                with zipfile.ZipFile(path) as archive:
                    if "manifest.json" in archive.namelist():
                        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            except (OSError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError):
                manifest = None
            backups.append({
                "filename": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "created_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "manifest": manifest,
            })
        return backups

    def resolve_backup_path(self, backup_name: str) -> Path:
        backup_path = self.backups_dir / Path(backup_name).name
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_name}")
        return backup_path

    def _restore_member(self, archive: zipfile.ZipFile, member: str) -> None:
        target = (self.data_dir / Path(member).relative_to("data")).resolve()
        data_root = self.data_dir.resolve()
        if data_root not in target.parents and target != data_root:
            raise ValueError(f"Unsafe backup member: {member}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)

    def restore_backup(
        self,
        backup_name: str,
        *,
        restore_database: bool = False,
        restore_configs: bool = False,
        restore_user_files: bool = False,
    ) -> Dict[str, Any]:
        backup_path = self.resolve_backup_path(backup_name)

        restored: List[str] = []
        with zipfile.ZipFile(backup_path) as archive:
            names = archive.namelist()
            for member in names:
                if member == "data/quant.db":
                    if restore_database:
                        self._restore_member(archive, member)
                        restored.append(member)
                    continue

                if member.startswith("data/") and member.endswith(".json") and "/" not in member.removeprefix("data/"):
                    if restore_configs:
                        self._restore_member(archive, member)
                        restored.append(member)
                    continue

                if member.startswith("data/exports/") or member.startswith("data/logs/audit/"):
                    if restore_user_files and not member.endswith("/"):
                        self._restore_member(archive, member)
                        restored.append(member)

        return {"status": "success", "restored": restored, "filename": backup_path.name}


def get_backup_manager() -> BackupManager:
    return BackupManager()

"""Backup and restore routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.auth import UserInDB
from api.dependencies import require_admin
from core.backup_manager import get_backup_manager
from core.review_audit import get_review_audit_service


router = APIRouter(prefix="/backup", tags=["备份恢复"])


class CreateBackupRequest(BaseModel):
    include_database: bool = True
    include_configs: bool = True
    include_user_files: bool = True


class BackupItem(BaseModel):
    filename: str
    path: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None


class BackupCreateResponse(BaseModel):
    status: str
    filename: str
    path: Optional[str] = None
    size_bytes: int
    manifest: Dict[str, Any]


class BackupListResponse(BaseModel):
    status: str
    count: int
    backups: List[BackupItem]


class RestoreBackupRequest(BaseModel):
    filename: str
    restore_database: bool = False
    restore_configs: bool = False
    restore_user_files: bool = False


class RestoreBackupResponse(BaseModel):
    status: str
    restored: List[str]
    filename: str


@router.post("/create", response_model=BackupCreateResponse)
async def create_backup(
    request: CreateBackupRequest,
    current_user: UserInDB = Depends(require_admin),
) -> BackupCreateResponse:
    try:
        result = get_backup_manager().create_backup(
            include_database=request.include_database,
            include_configs=request.include_configs,
            include_user_files=request.include_user_files,
        )
        get_review_audit_service().record_event(
            user=current_user.username,
            action="BACKUP_CREATE",
            resource=result.get("filename", "backup"),
            resource_type="backup",
            details={"size_bytes": result.get("size_bytes"), "manifest": result.get("manifest")},
        )
        return result
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/list", response_model=BackupListResponse)
async def list_backups(current_user: UserInDB = Depends(require_admin)) -> BackupListResponse:
    del current_user
    backups = get_backup_manager().list_backups()
    return {"status": "success", "count": len(backups), "backups": backups}


@router.get("/download/{filename}")
async def download_backup(filename: str, current_user: UserInDB = Depends(require_admin)) -> FileResponse:
    del current_user
    try:
        backup_path = get_backup_manager().resolve_backup_path(filename)
        return FileResponse(
            backup_path,
            media_type="application/zip",
            filename=backup_path.name,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/restore", response_model=RestoreBackupResponse)
async def restore_backup(
    request: RestoreBackupRequest,
    current_user: UserInDB = Depends(require_admin),
) -> RestoreBackupResponse:
    try:
        result = get_backup_manager().restore_backup(
            request.filename,
            restore_database=request.restore_database,
            restore_configs=request.restore_configs,
            restore_user_files=request.restore_user_files,
        )
        get_review_audit_service().record_event(
            user=current_user.username,
            action="BACKUP_RESTORE",
            resource=request.filename,
            resource_type="backup",
            details={
                "restore_database": request.restore_database,
                "restore_configs": request.restore_configs,
                "restore_user_files": request.restore_user_files,
                "restored": result.get("restored", []),
            },
        )
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

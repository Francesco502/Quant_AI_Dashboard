"""Review audit routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.auth import UserInDB, get_current_active_user
from core.review_audit import get_review_audit_service


router = APIRouter(prefix="/audit", tags=["复盘审计"])


class AuditEventRequest(BaseModel):
    action: str = Field(..., min_length=1)
    resource: str = Field(..., min_length=1)
    resource_type: str = Field(..., min_length=1)
    details: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None


class AuditEventResponse(BaseModel):
    timestamp: Optional[str] = None
    action: str
    user: Optional[str] = None
    resource: str
    resource_type: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: Optional[str] = None


class AuditEventListResponse(BaseModel):
    status: str
    count: int
    events: List[AuditEventResponse]


class AuditRecordResponse(BaseModel):
    status: str
    action: str
    resource: str
    resource_type: str


@router.get("/events", response_model=AuditEventListResponse)
async def list_audit_events(
    resource_type: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    limit: int = Query(default=80, ge=1, le=500),
    current_user: UserInDB = Depends(get_current_active_user),
) -> AuditEventListResponse:
    events = get_review_audit_service().list_events(
        user=current_user.username,
        action=action,
        resource_type=resource_type,
        limit=limit,
    )
    return {"status": "success", "count": len(events), "events": events}


@router.post("/events", response_model=AuditRecordResponse)
async def record_audit_event(
    request: AuditEventRequest,
    current_user: UserInDB = Depends(get_current_active_user),
) -> AuditRecordResponse:
    return get_review_audit_service().record_event(
        user=current_user.username,
        action=request.action,
        resource=request.resource,
        resource_type=request.resource_type,
        details=request.details,
        success=request.success,
        error_message=request.error_message,
    )

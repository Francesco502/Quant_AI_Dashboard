"""Review-oriented audit helpers for daily workflow events."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .audit_log import AuditLogger


class ReviewAuditService:
    """Small wrapper around AuditLogger with workflow-oriented names."""

    def __init__(self, log_dir: Optional[str] = None):
        self.audit_logger = AuditLogger(log_dir=log_dir)

    def record_event(
        self,
        *,
        user: str,
        action: str,
        resource: str,
        resource_type: str,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.audit_logger.log(
            action=action,
            user=user,
            resource=resource,
            resource_type=resource_type,
            details=details or {},
            success=success,
            error_message=error_message,
        )
        return {
            "status": "success",
            "action": action,
            "resource": resource,
            "resource_type": resource_type,
        }

    def list_events(
        self,
        *,
        user: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        return self.audit_logger.query_logs(
            user=user,
            action=action,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )


_review_audit_service: Optional[ReviewAuditService] = None


def get_review_audit_service() -> ReviewAuditService:
    global _review_audit_service
    if _review_audit_service is None:
        _review_audit_service = ReviewAuditService()
    return _review_audit_service

from __future__ import annotations

from fastapi import APIRouter, Request

from stock_tax_app.engine.models import AuditSummary

router = APIRouter()


@router.get("/api/audit", response_model=AuditSummary)
def get_audit_summary(request: Request) -> AuditSummary:
    return request.app.state.runtime.current().audit_summary

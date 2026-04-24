from __future__ import annotations

from fastapi import APIRouter, Request

from stock_tax_app.engine.models import ImportSummary

router = APIRouter()


@router.get("/api/import", response_model=ImportSummary)
def get_import_summary(request: Request) -> ImportSummary:
    return request.app.state.runtime.current().import_summary

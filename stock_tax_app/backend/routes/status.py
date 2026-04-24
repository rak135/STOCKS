from __future__ import annotations

from fastapi import APIRouter, Request

from stock_tax_app.engine.models import AppStatus

router = APIRouter()


@router.get("/api/status", response_model=AppStatus)
def get_status(request: Request) -> AppStatus:
    return request.app.state.runtime.current().app_status

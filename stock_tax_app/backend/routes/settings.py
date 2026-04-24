from __future__ import annotations

from fastapi import APIRouter, Request

from stock_tax_app.engine.models import AppSettings

router = APIRouter()


@router.get("/api/settings", response_model=AppSettings)
def get_settings(request: Request) -> AppSettings:
    return request.app.state.runtime.current().settings

from __future__ import annotations

from fastapi import APIRouter, Request

from stock_tax_app.engine.models import FxYear

router = APIRouter()


@router.get("/api/fx", response_model=list[FxYear])
def get_fx_years(request: Request) -> list[FxYear]:
    return request.app.state.runtime.current().fx_years

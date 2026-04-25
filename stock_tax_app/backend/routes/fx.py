from __future__ import annotations

from fastapi import APIRouter, Request

from stock_tax_app.engine.models import FxYearList

router = APIRouter()


@router.get("/api/fx", response_model=FxYearList)
def get_fx_years(request: Request) -> FxYearList:
    return request.app.state.runtime.current().fx_years

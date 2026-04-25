from __future__ import annotations

from fastapi import APIRouter, Request

from stock_tax_app.engine.models import OpenPositionList

router = APIRouter()


@router.get("/api/open-positions", response_model=OpenPositionList)
def get_open_positions(request: Request) -> OpenPositionList:
    return request.app.state.runtime.current().open_positions

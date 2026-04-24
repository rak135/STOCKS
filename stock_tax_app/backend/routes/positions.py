from __future__ import annotations

from fastapi import APIRouter, Request

from stock_tax_app.engine.models import OpenPosition

router = APIRouter()


@router.get("/api/open-positions", response_model=list[OpenPosition])
def get_open_positions(request: Request) -> list[OpenPosition]:
    return request.app.state.runtime.current().open_positions

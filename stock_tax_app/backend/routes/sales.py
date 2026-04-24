from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request

from stock_tax_app.engine.models import ReviewStatus, Sell, SellSummary

router = APIRouter()


class SellReviewPatch(BaseModel):
    review_status: ReviewStatus | None = None
    note: str | None = None


@router.get("/api/sales", response_model=list[SellSummary])
def get_sales(request: Request) -> list[SellSummary]:
    return [
        SellSummary(
            id=sell.id,
            year=sell.year,
            date=sell.date,
            ticker=sell.ticker,
            instrument_id=sell.instrument_id,
            broker=sell.broker,
            quantity=sell.quantity,
            price_usd=sell.price_usd,
            proceeds_czk=sell.proceeds_czk,
            method=sell.method,
            matched_quantity=sell.matched_quantity,
            unmatched_quantity=sell.unmatched_quantity,
            classification=sell.classification,
            review_status=sell.review_status,
        )
        for sell in request.app.state.runtime.current().sales
    ]


@router.get("/api/sales/{sell_id}", response_model=Sell)
def get_sale(sell_id: str, request: Request) -> Sell:
    for sell in request.app.state.runtime.current().sales:
        if sell.id == sell_id:
            return sell
    raise HTTPException(status_code=404, detail=f"Unknown sell id: {sell_id}")


@router.patch("/api/sales/{sell_id}/review", response_model=Sell)
def patch_sale_review(sell_id: str, payload: SellReviewPatch, request: Request) -> Sell:
    current = request.app.state.runtime.current()
    if not any(sell.id == sell_id for sell in current.sales):
        raise HTTPException(status_code=404, detail=f"Unknown sell id: {sell_id}")
    updated = request.app.state.runtime.update_sell_review(
        sell_id,
        review_status=payload.review_status,
        note=payload.note,
    )
    for sell in updated.sales:
        if sell.id == sell_id:
            return sell
    raise HTTPException(status_code=404, detail=f"Unknown sell id after update: {sell_id}")

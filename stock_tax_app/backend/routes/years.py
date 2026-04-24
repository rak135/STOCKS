from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request

from stock_tax_app.engine import policy
from stock_tax_app.engine.models import TaxYear

router = APIRouter()


class YearPatchRequest(BaseModel):
    method: str | None = None


@router.get("/api/years", response_model=list[TaxYear])
def get_years(request: Request) -> list[TaxYear]:
    return request.app.state.runtime.current().tax_years


@router.patch("/api/years/{year}", response_model=TaxYear)
def patch_year(year: int, payload: YearPatchRequest, request: Request) -> TaxYear:
    if payload.method is not None:
        violation = policy.check_year_mutation(year, "method")
        if violation is not None:
            raise HTTPException(status_code=409, detail=violation.message)
    raise HTTPException(status_code=501, detail="Year editing is not implemented yet.")

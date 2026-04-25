from __future__ import annotations

import math

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request

from stock_tax_app.engine.fx import SUPPORTED_FX_METHODS
from stock_tax_app.engine import policy
from stock_tax_app.engine.models import TaxYear, TaxYearList
from stock_tax_app.state import project_store

router = APIRouter()


class YearPatchRequest(BaseModel):
    method: str | None = None
    fx_method: str | None = None
    tax_rate: object | None = None
    apply_100k_exemption: object | None = None


def _normalize_method(value: str) -> str:
    resolved = value.strip().upper()
    if resolved not in policy.SUPPORTED_METHODS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported method {value!r}. "
                f"Supported: {', '.join(policy.SUPPORTED_METHODS)}"
            ),
        )
    return resolved


def _normalize_fx_method(value: str) -> str:
    resolved = value.strip().upper()
    if resolved not in SUPPORTED_FX_METHODS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported fx_method {value!r}. "
                f"Supported: {', '.join(SUPPORTED_FX_METHODS)}"
            ),
        )
    return resolved


def _normalize_tax_rate(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(status_code=422, detail="tax_rate must be a numeric value >= 0")
    resolved = float(value)
    if not math.isfinite(resolved) or resolved < 0:
        raise HTTPException(status_code=422, detail="tax_rate must be a numeric value >= 0")
    return resolved


def _normalize_apply_100k(value: object) -> bool:
    if not isinstance(value, bool):
        raise HTTPException(status_code=422, detail="apply_100k_exemption must be a boolean")
    return value


def _find_year_or_404(request: Request, year: int) -> None:
    current_years = {item.year for item in request.app.state.runtime.current().tax_years.items}
    if year not in current_years:
        raise HTTPException(status_code=404, detail=f"Unknown tax year: {year}")


def _assert_mutation_allowed(year: int, fields: list[str]) -> None:
    for field in fields:
        violation = policy.check_year_mutation(year, field)
        if violation is not None:
            raise HTTPException(status_code=409, detail=violation.message)


@router.get("/api/years", response_model=TaxYearList)
def get_years(request: Request) -> TaxYearList:
    return request.app.state.runtime.current().tax_years


@router.patch("/api/years/{year}", response_model=TaxYear)
def patch_year(year: int, payload: YearPatchRequest, request: Request) -> TaxYear:
    _find_year_or_404(request, year)
    current = request.app.state.runtime.current()
    existing_year = next((item for item in current.tax_years.items if item.year == year), None)
    if existing_year is None:
        raise HTTPException(status_code=404, detail=f"Unknown tax year: {year}")

    has_method = payload.method is not None
    has_fx_method = payload.fx_method is not None
    has_tax_rate = payload.tax_rate is not None
    has_apply_100k = payload.apply_100k_exemption is not None

    fields_to_mutate: list[str] = []
    if has_method:
        fields_to_mutate.append("method")
    if has_fx_method:
        fields_to_mutate.append("fx_method")
    if has_tax_rate:
        fields_to_mutate.append("tax_rate")
    if has_apply_100k:
        fields_to_mutate.append("apply_100k_exemption")

    if not fields_to_mutate:
        raise HTTPException(status_code=400, detail="No editable year fields were provided.")

    _assert_mutation_allowed(year, fields_to_mutate)

    method_value = _normalize_method(payload.method) if has_method and payload.method is not None else None
    fx_method_value = _normalize_fx_method(payload.fx_method) if has_fx_method and payload.fx_method is not None else None
    tax_rate_value = _normalize_tax_rate(payload.tax_rate) if has_tax_rate else None
    apply_100k_value = _normalize_apply_100k(payload.apply_100k_exemption) if has_apply_100k else None

    state = project_store.load_project_state(request.app.state.runtime.project_dir)

    if payload.method is not None:
        settings = state.year_settings.setdefault(year, {})
        existing_overrides = state.method_selection.get(year, {})
        if (
            "method" not in settings
            and existing_overrides
            and len(set(existing_overrides.values())) == 1
        ):
            # Older PATCH behavior materialized a year choice into per-instrument rows.
            # Drop that synthetic slice so the explicit year default can take effect.
            state.method_selection.pop(year, None)
        settings["method"] = method_value or policy.default_method_for(year)

    if has_fx_method or has_tax_rate or has_apply_100k:
        settings = state.year_settings.setdefault(year, {})
        if has_fx_method:
            settings["fx_method"] = fx_method_value
        if has_tax_rate:
            settings["tax_rate"] = tax_rate_value
        if has_apply_100k:
            settings["apply_100k"] = apply_100k_value

    project_store.save_project_state(request.app.state.runtime.project_dir, state)
    updated = request.app.state.runtime.calculate(write_workbook=False)
    for item in updated.tax_years.items:
        if item.year == year:
            return item

    updated_payload = existing_year.model_dump()
    updated_payload["method_source"] = "project_state"
    updated_payload["settings_source"] = "project_state"
    if method_value is not None:
        updated_payload["method"] = method_value
    if fx_method_value is not None:
        updated_payload["fx_method"] = fx_method_value
    if tax_rate_value is not None:
        updated_payload["tax_rate"] = tax_rate_value
    if apply_100k_value is not None:
        updated_payload["exemption_100k"] = apply_100k_value
    return TaxYear(**updated_payload)

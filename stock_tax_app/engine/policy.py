"""Server-side year policy.

Single source of truth for which years are filed, which are auto-locked,
what the default method per year is, and which mutations the backend
refuses to accept.

UI-only state (reviewed/flagged/notes) is *not* governed by this module;
it lives in :mod:`stock_tax_app.engine.ui_state` and never affects tax
calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set


SUPPORTED_METHODS = ("FIFO", "LIFO", "MIN_GAIN", "MAX_GAIN")
DEFAULT_METHOD = "FIFO"


# ---------------------------------------------------------------------
# Filed & locked years (hard rules, enforced server-side)
# ---------------------------------------------------------------------

#: Years that were already filed with the Czech tax authority, and the
#: matching method used in the filed return.
FILED_YEARS: Dict[int, str] = {
    2024: "LIFO",
}

#: Years auto-locked by default as a consequence of having been filed.
#: The workbook/build pipeline may still allow an explicit operator
#: unlock; this set only provides the default lock state.
AUTO_LOCKED_YEARS: Set[int] = set(FILED_YEARS.keys())

#: Default matching method per year when no operator selection exists.
#: Historical non-filed years (2020–2023) default to LIFO for
#: consistency with the filed 2024 return. Later years fall back to the
#: generator default unless explicitly configured by the operator.
DEFAULT_METHOD_BY_YEAR: Dict[int, str] = {
    2020: "LIFO", 2021: "LIFO", 2022: "LIFO", 2023: "LIFO",
    2024: "LIFO",
    2025: "FIFO",
}

YEAR_DEFAULT_METHODS = DEFAULT_METHOD_BY_YEAR

#: Fallback method for years not in :data:`DEFAULT_METHOD_BY_YEAR`.
FALLBACK_DEFAULT_METHOD = DEFAULT_METHOD


# ---------------------------------------------------------------------
# Queries used by the backend
# ---------------------------------------------------------------------

def is_filed(year: int) -> bool:
    return year in FILED_YEARS


def is_locked(year: int) -> bool:
    """Return the default lock state for a year.

    Filed years start locked by default, but lock state is still a soft
    operator control rather than permanent immutability.
    """
    return year in AUTO_LOCKED_YEARS


def filed_method(year: int) -> str | None:
    return FILED_YEARS.get(year)


def normalize_method(method: str | None) -> str:
    resolved = str(method or DEFAULT_METHOD).upper()
    if resolved not in SUPPORTED_METHODS:
        return DEFAULT_METHOD
    return resolved


def default_method_for(year: int) -> str:
    return DEFAULT_METHOD_BY_YEAR.get(year, FALLBACK_DEFAULT_METHOD)


def resolved_method_for(year: int, method: str | None = None) -> str:
    if is_filed(year):
        return filed_method(year) or DEFAULT_METHOD
    if method is None or str(method).strip() == "":
        return default_method_for(year)
    return normalize_method(method)


def show_method_comparison(year: int) -> bool:
    """Filed years must never surface method comparison as an
    optimisation opportunity."""
    return not is_filed(year)


# ---------------------------------------------------------------------
# Mutation guards
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class PolicyViolation:
    code: str
    message: str


def check_year_mutation(
    year: int,
    field: str,
) -> PolicyViolation | None:
    """Return a :class:`PolicyViolation` if the mutation is forbidden.

    The UI disables the corresponding control, but the backend must also
    refuse — never rely on the UI to enforce this.
    """
    if is_locked(year):
        return PolicyViolation(
            code="year_locked",
            message=(
                f"{year} is locked (filed under {filed_method(year)}). "
                f"Unlock first to change {field}."
            ),
        )
    return None


def check_unlock(year: int) -> PolicyViolation | None:
    """Explicit unlock is always allowed by policy.

    The current API still lacks a dedicated unlock route; callers that do
    expose an explicit unlock flow should treat lock state as soft.
    """
    return None


def check_review_status(value: str) -> PolicyViolation | None:
    if value not in ("unreviewed", "reviewed", "flagged"):
        return PolicyViolation(
            code="invalid_review_status",
            message=f"review_status must be one of unreviewed/reviewed/flagged, got {value!r}",
        )
    return None

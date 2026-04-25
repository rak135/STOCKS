"""Local JSON persistence for UI-only state.

`.ui_state.json` sits next to the Excel workbook. It holds whatever the
operator has done in the UI that is *not* part of the tax calculation:

- reviewed / flagged / unreviewed per sell
- free-text review notes per sell
- reconciliation notes per year (when the operator explicitly accepts a
  difference between workbook and filed tax with a justification)
- UI preferences (last-opened section, sidebar width, …) — future use

These fields never feed into :func:`stock_tax_app.engine.core.run`. They
are layered onto the :class:`EngineResult` *after* calculation.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from . import policy

UI_STATE_FILENAME = ".ui_state.json"
_SCHEMA_VERSION = 1


@dataclass
class SellReview:
    review_status: str = "unreviewed"  # unreviewed | reviewed | flagged
    note: str = ""


@dataclass
class YearReconciliationNote:
    note: str = ""
    accepted_difference_czk: Optional[float] = None


@dataclass
class UIState:
    #: sell_id -> SellReview
    sells: Dict[str, SellReview] = field(default_factory=dict)
    #: year -> YearReconciliationNote
    years: Dict[int, YearReconciliationNote] = field(default_factory=dict)
    #: version of the on-disk schema we loaded
    schema_version: int = _SCHEMA_VERSION

    # ---- queries ---------------------------------------------------

    def review_for(self, sell_id: str) -> SellReview:
        return self.sells.get(canonical_sell_id(sell_id), SellReview())

    def reconciliation_for(self, year: int) -> YearReconciliationNote:
        return self.years.get(year, YearReconciliationNote())

    # ---- mutations -------------------------------------------------

    def set_review(
        self,
        sell_id: str,
        *,
        review_status: Optional[str] = None,
        note: Optional[str] = None,
    ) -> SellReview:
        if review_status is not None:
            violation = policy.check_review_status(review_status)
            if violation is not None:
                raise ValueError(violation.message)
        canonical_sell = canonical_sell_id(sell_id)
        current = self.sells.get(canonical_sell, SellReview())
        updated = SellReview(
            review_status=review_status if review_status is not None else current.review_status,
            note=note if note is not None else current.note,
        )
        self.sells[canonical_sell] = updated
        return updated


def canonical_sell_id(sell_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(sell_id or ""))


def _normalized_sell_review(review_status: Any, note: Any) -> SellReview:
    resolved_status = str(review_status or "unreviewed").strip() or "unreviewed"
    violation = policy.check_review_status(resolved_status)
    if violation is not None:
        resolved_status = "unreviewed"
    return SellReview(
        review_status=resolved_status,
        note=str(note or ""),
    )


def export_review_state(state: UIState) -> Dict[str, Dict[str, str]]:
    return {
        canonical_sell_id(sell_id): {
            "review_status": review.review_status,
            "operator_note": review.note,
        }
        for sell_id, review in state.sells.items()
    }


def load_with_legacy_review_fallback(
    workbook_path: Path,
    legacy_review_state: Dict[str, Dict[str, Any]] | None = None,
) -> tuple[UIState, int, int]:
    """Load canonical UI state and optionally adopt legacy workbook reviews.

    `.ui_state.json` is canonical. Workbook `Review_State` is consulted only
    for sell IDs that do not already exist in the backend-owned UI state.
    Conflicting workbook values are ignored.
    """
    state = load(workbook_path)
    adopted = 0
    conflicts = 0
    dirty = False
    for sell_id, legacy in (legacy_review_state or {}).items():
        canonical_sell = canonical_sell_id(sell_id)
        legacy_review = _normalized_sell_review(
            legacy.get("review_status"),
            legacy.get("operator_note"),
        )
        current = state.sells.get(canonical_sell)
        if current is None:
            state.sells[canonical_sell] = legacy_review
            adopted += 1
            dirty = True
            continue
        if (
            current.review_status != legacy_review.review_status
            or current.note != legacy_review.note
        ):
            conflicts += 1
    if dirty:
        save(workbook_path, state)
    return state, adopted, conflicts


# ---------------------------------------------------------------------
# Disk I/O
# ---------------------------------------------------------------------

def state_path_for(workbook_path: Path) -> Path:
    return workbook_path.parent / UI_STATE_FILENAME


def load(workbook_path: Path) -> UIState:
    """Load the UI state next to *workbook_path*. Missing/corrupt file
    returns an empty :class:`UIState` — never raises."""
    p = state_path_for(workbook_path)
    if not p.exists():
        return UIState()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UIState()

    sells = {
        canonical_sell_id(sid): _normalized_sell_review(
            obj.get("review_status"),
            obj.get("note"),
        )
        for sid, obj in (raw.get("sells") or {}).items()
    }
    years_raw = raw.get("years") or {}
    years: Dict[int, YearReconciliationNote] = {}
    for k, obj in years_raw.items():
        try:
            y = int(k)
        except (TypeError, ValueError):
            continue
        years[y] = YearReconciliationNote(
            note=str(obj.get("note") or ""),
            accepted_difference_czk=obj.get("accepted_difference_czk"),
        )
    return UIState(
        sells=sells,
        years=years,
        schema_version=int(raw.get("schema_version") or _SCHEMA_VERSION),
    )


def save(workbook_path: Path, state: UIState) -> None:
    """Atomically write the state next to *workbook_path*."""
    p = state_path_for(workbook_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "sells": {
            canonical_sell_id(sid): {"review_status": r.review_status, "note": r.note}
            for sid, r in state.sells.items()
        },
        "years": {
            str(y): {
                "note": r.note,
                "accepted_difference_czk": r.accepted_difference_czk,
            }
            for y, r in state.years.items()
        },
    }
    # Atomic write: tmp + os.replace
    fd, tmp_path = tempfile.mkstemp(prefix=".ui_state.", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_path, p)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

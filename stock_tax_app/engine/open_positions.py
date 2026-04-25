"""Open-position and reported-position provenance logic.

Behavior-preserving extraction from build_stock_tax_workbook.py.
No tax logic, no matching, no corporate actions.

All parameters that reference monolith-defined types (RawRow, Lot)
use Any typing to avoid import cycles.  Callable utilities
(safe_float, parse_trade_date) are injected by the monolith wrapper.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple


def extract_position_rows_with_provenance(
    raw_rows: List[Any],
    instrument_map: Dict[str, Dict[str, str]],
    *,
    safe_float: Callable[[str, Any], Tuple[Optional[float], bool]],
    parse_trade_date: Callable[[str], Optional[Any]],
) -> Tuple[Dict[str, float], Dict[str, List[Dict[str, Any]]]]:
    """Extract Yahoo position rows plus source provenance by instrument.

    Position rows are CSV rows that have no Trade Date and no Transaction
    Type but do have a Quantity value.  Returns (qty_by_instrument,
    provenance_by_instrument).
    """
    out: Dict[str, float] = defaultdict(float)
    provenance: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for raw in raw_rows:
        tt = (raw.data.get("Transaction Type") or "").strip()
        td = (raw.data.get("Trade Date") or "").strip()
        if tt or td:
            continue
        qty_raw = raw.data.get("Quantity")
        qty, ok = safe_float(qty_raw or "", default=None)
        if not ok or qty is None:
            continue
        symbol = (raw.data.get("Symbol") or "").strip()
        inst = (instrument_map.get(symbol, {}).get("Instrument_ID") or symbol)
        if not inst:
            continue
        out[inst] += qty
        snapshot_date = parse_trade_date((raw.data.get("Date") or "").strip())
        provenance[inst].append(
            {
                "source_file": raw.source_file,
                "source_row": raw.source_row,
                "broker": raw.source_broker or None,
                "account": raw.source_account or None,
                "snapshot_date": snapshot_date,
                "source_type": "csv_position_row",
            }
        )
    return dict(out), dict(provenance)


def extract_position_rows(
    raw_rows: List[Any],
    instrument_map: Dict[str, Dict[str, str]],
    *,
    safe_float: Callable[[str, Any], Tuple[Optional[float], bool]],
    parse_trade_date: Callable[[str], Optional[Any]],
) -> Dict[str, float]:
    """Extract Yahoo position rows (no Trade Date/Tx Type, has Quantity)."""
    out, _ = extract_position_rows_with_provenance(
        raw_rows,
        instrument_map,
        safe_float=safe_float,
        parse_trade_date=parse_trade_date,
    )
    return out


def build_open_position_rows(
    raw_rows: List[Any],
    instrument_map: Dict[str, Dict[str, str]],
    lots: List[Any],
    *,
    safe_float: Callable[[str, Any], Tuple[Optional[float], bool]],
    parse_trade_date: Callable[[str], Optional[Any]],
    ok_tolerance: float = 1e-4,
    warn_tolerance: float = 1e-2,
) -> List[Dict[str, Any]]:
    """Build open-position reconciliation rows.

    Compares broker-reported quantities (from position rows in the CSV) to
    calculated remaining quantities (from lot simulation).
    """
    yahoo, position_provenance = extract_position_rows_with_provenance(
        raw_rows,
        instrument_map,
        safe_float=safe_float,
        parse_trade_date=parse_trade_date,
    )
    calc: Dict[str, float] = defaultdict(float)
    for lot in lots:
        if lot.quantity_remaining > 1e-9:
            calc[lot.instrument_id] += lot.quantity_remaining
    instruments = sorted(set(yahoo.keys()) | set(calc.keys()))
    rows: List[Dict[str, Any]] = []
    for inst in instruments:
        yq = yahoo.get(inst)
        cq = calc.get(inst, 0.0)
        sources = position_provenance.get(inst, [])
        source_count = len(sources)
        primary_source = sources[0] if sources else {}

        if yq is None:
            source_status = "unknown"
            source_reason = "No broker/Yahoo position row is available for this instrument."
        else:
            source_status = "ready"
            source_reason_parts: List[str] = []
            missing_snapshot_dates = [src for src in sources if src.get("snapshot_date") is None]
            if missing_snapshot_dates:
                source_status = "partial"
                source_reason_parts.append(
                    "Snapshot date is unavailable in one or more source rows."
                )
            if source_count > 1:
                source_status = "partial"
                source_reason_parts.append(
                    f"Reported quantity is aggregated from {source_count} source rows."
                )
            source_reason = " ".join(source_reason_parts) if source_reason_parts else None

        if yq is None:
            diff = None
            status = "UNKNOWN"
        else:
            diff = cq - yq
            status = "OK" if abs(diff) <= ok_tolerance else (
                "WARN" if abs(diff) <= warn_tolerance else "ERROR"
            )
        rows.append({
            "Instrument_ID": inst,
            "Reported qty": yq,
            "Yahoo qty": yq,
            "Calculated qty": cq,
            "Difference": diff,
            "Status": status,
            "Reported position source file": primary_source.get("source_file"),
            "Reported position source row": primary_source.get("source_row"),
            "Reported position broker": primary_source.get("broker"),
            "Reported position account": primary_source.get("account"),
            "Reported position snapshot date": primary_source.get("snapshot_date"),
            "Reported position source type": (
                primary_source.get("source_type") if sources else "csv_position_row"
            ),
            "Reported position source status": source_status,
            "Reported position source reason": source_reason,
            "Reported position source count": source_count,
            "Reported position sources": sources,
        })
    return rows

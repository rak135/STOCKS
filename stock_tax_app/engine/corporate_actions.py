from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

CA_TYPES = ("SPLIT", "REVERSE_SPLIT", "TICKER_CHANGE")


def _is_blank_corporate_action_row(row: Dict[str, Any]) -> bool:
    keys = (
        "Date",
        "effective_date",
        "Instrument_ID",
        "instrument_id",
        "Action type",
        "action_type",
        "Action ID",
        "action_id",
        "Notes",
        "note",
        "Ratio old",
        "ratio_denominator",
        "Ratio new",
        "ratio_numerator",
    )
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return False
    return True


def _corporate_action_issue(
    *,
    category: str,
    detail: str,
    severity: str,
    row_index: int,
) -> Dict[str, Any]:
    return {
        "check": category,
        "detail": detail,
        "severity": severity,
        "source_file": "Corporate_Actions",
        "source_row": row_index,
    }


def _parse_target_from_note(note: str) -> str:
    marker = "target="
    lower = note.lower()
    idx = lower.find(marker)
    if idx == -1:
        return ""
    tail = note[idx + len(marker):].strip()
    if not tail:
        return ""
    return tail.split()[0].strip()


def build_corporate_actions(
    user_state: Dict[str, Any],
    *,
    known_instrument_ids: Optional[set[str]] = None,
    parse_trade_date: Callable[[str], Optional[date]],
    coerce_float: Callable[[Any], Optional[float]],
    to_bool: Callable[[Any, bool], bool],
    to_float: Callable[[Any, float], float],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    out: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for idx, row in enumerate(user_state.get("Corporate_Actions", []), start=4):
        if not isinstance(row, dict) or _is_blank_corporate_action_row(row):
            continue

        action_id = str(row.get("Action ID") or row.get("action_id") or "").strip()
        action_type = str(row.get("Action type") or row.get("action_type") or "").strip().upper()

        raw_date = row.get("Date")
        if raw_date is None:
            raw_date = row.get("effective_date")
        parsed_date: Optional[date] = None
        if isinstance(raw_date, datetime):
            parsed_date = raw_date.date()
        elif isinstance(raw_date, date):
            parsed_date = raw_date
        elif isinstance(raw_date, str):
            parsed_date = parse_trade_date(raw_date)

        inst = str(
            row.get("Instrument_ID")
            or row.get("instrument_id")
            or row.get("source_symbol")
            or ""
        ).strip()
        target_inst = str(
            row.get("Target Instrument_ID")
            or row.get("target_instrument_id")
            or row.get("target_symbol")
            or row.get("Target symbol")
            or ""
        ).strip()

        note = str(row.get("Notes") or row.get("note") or "").strip()
        source = str(row.get("Source") or row.get("source") or "").strip()
        if not target_inst and action_type == "TICKER_CHANGE":
            target_inst = _parse_target_from_note(note)

        ratio_old = coerce_float(row.get("Ratio old"))
        if ratio_old is None:
            ratio_old = coerce_float(row.get("ratio_denominator"))
        ratio_new = coerce_float(row.get("Ratio new"))
        if ratio_new is None:
            ratio_new = coerce_float(row.get("ratio_numerator"))
        if ratio_old is None:
            ratio_old = 1.0
        if ratio_new is None:
            ratio_new = 1.0

        enabled = to_bool(row.get("Applied?") if "Applied?" in row else row.get("enabled"), True)
        cash_in_lieu = to_float(row.get("Cash in lieu"), 0.0)

        if action_id:
            if action_id in seen_ids:
                issues.append(
                    _corporate_action_issue(
                        category="corporate_action_duplicate_action_id",
                        detail=f"Duplicate action_id '{action_id}' in Corporate_Actions.",
                        severity="ERROR",
                        row_index=idx,
                    )
                )
                continue
            seen_ids.add(action_id)

        if action_type not in CA_TYPES:
            issues.append(
                _corporate_action_issue(
                    category="corporate_action_unknown_action_type",
                    detail=f"Unknown action_type '{action_type or '<blank>'}'.",
                    severity="ERROR",
                    row_index=idx,
                )
            )
            continue

        if parsed_date is None:
            issues.append(
                _corporate_action_issue(
                    category="corporate_action_invalid_date",
                    detail="Corporate action has an invalid or missing effective date.",
                    severity="ERROR",
                    row_index=idx,
                )
            )
            continue

        if not inst:
            issues.append(
                _corporate_action_issue(
                    category="corporate_action_missing_instrument",
                    detail="Corporate action is missing Instrument_ID/source symbol.",
                    severity="ERROR",
                    row_index=idx,
                )
            )
            continue

        if action_type in ("SPLIT", "REVERSE_SPLIT"):
            if ratio_old <= 0 or ratio_new <= 0:
                issues.append(
                    _corporate_action_issue(
                        category="corporate_action_invalid_ratio",
                        detail=(
                            "Split ratio must be positive and non-zero "
                            f"(got old={ratio_old}, new={ratio_new})."
                        ),
                        severity="ERROR",
                        row_index=idx,
                    )
                )
                continue
        if action_type == "TICKER_CHANGE" and not target_inst:
            issues.append(
                _corporate_action_issue(
                    category="corporate_action_missing_target",
                    detail="Ticker change is missing target instrument/symbol.",
                    severity="ERROR",
                    row_index=idx,
                )
            )
            continue

        if enabled and known_instrument_ids and inst not in known_instrument_ids:
            issues.append(
                _corporate_action_issue(
                    category="corporate_action_ambiguous_mapping",
                    detail=(
                        f"Corporate action instrument '{inst}' does not match known instrument IDs "
                        "from transaction data."
                    ),
                    severity="WARN",
                    row_index=idx,
                )
            )

        out.append(
            {
                "Action_ID": action_id,
                "Date": parsed_date,
                "Instrument_ID": inst,
                "Action type": action_type,
                "Ratio old": ratio_old,
                "Ratio new": ratio_new,
                "Cash in lieu": cash_in_lieu,
                "Notes": note,
                "Applied": enabled,
                "Target Instrument_ID": target_inst,
                "Source": source,
            }
        )

    out.sort(key=lambda r: (r["Date"], r["Instrument_ID"], r.get("Action_ID") or ""))
    return out, issues


def apply_corporate_action_to_lots(lots: List[Any], action: Dict[str, Any]) -> None:
    """Apply a supported corporate action to open lots in place."""
    inst = action["Instrument_ID"]
    action_date = action["Date"]
    action_type = str(action.get("Action type") or "").strip().upper()

    if action_type == "TICKER_CHANGE":
        target_inst = str(action.get("Target Instrument_ID") or "").strip()
        if not target_inst:
            return
        for lot in lots:
            if lot.instrument_id != inst:
                continue
            if lot.buy_date > action_date:
                continue
            if lot.quantity_remaining <= 0:
                continue
            lot.instrument_id = target_inst
            lot.adjustments.append(f"TICKER_CHANGE {inst}->{target_inst} on {action_date}")
        return

    ratio_old = action["Ratio old"]
    ratio_new = action["Ratio new"]
    if ratio_old <= 0 or ratio_new <= 0:
        return

    factor = ratio_new / ratio_old
    if factor == 1.0:
        return
    for lot in lots:
        if lot.instrument_id != inst:
            continue
        if lot.buy_date > action_date:
            continue
        if lot.quantity_remaining <= 0:
            continue
        lot.quantity_remaining *= factor
        lot.quantity_original *= factor
        lot.price_per_share_usd /= factor
        lot.adjustments.append(f"{action_type} {ratio_old}:{ratio_new} on {action_date}")
"""Check/problem shaping logic.

Behavior-preserving extraction from build_stock_tax_workbook.py.
Centralises the conversion of raw calculation problems, simulation
warnings, and engine-derived observations into the flat check-row list
that core.py and the workbook writer consume.

All monolith-defined types (FXResolver, MatchLine, Lot) are accepted
as Any to avoid import cycles.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Tuple


def build_check_rows(
    *,
    sim_warnings: List[Dict[str, Any]],
    problems: List[Dict[str, Any]],
    fx_yearly: Dict[int, float],
    fx_daily: Dict[date, float],
    settings: Dict[int, Dict[str, Any]],
    locked_years: Dict[int, bool],
    frozen_inventory: Dict[int, List[Dict[str, Any]]],
    split_warnings: List[Dict[str, Any]],
    method_selection: Dict[Tuple[int, str], str],
    yearly_summary: List[Dict[str, Any]],
    match_lines: List[Any],
    lots_final: List[Any],
    year_end_inventory: Dict[int, List[Any]],
    frozen_snapshots: Dict[int, Dict[str, Any]],
    fx: Any,
    supported_methods: Tuple[str, ...],
) -> List[Dict[str, Any]]:
    """Build the flat list of check rows from all engine signals.

    Parameters
    ----------
    supported_methods:
        Tuple of valid method strings (injected by monolith wrapper to
        avoid importing policy directly here).
    fx:
        FXResolver instance; accessed only via .missing_daily and
        .missing_yearly attributes.
    match_lines:
        List of MatchLine objects; accessed only via .sell_date and
        .buy_date attributes.
    lots_final:
        List of Lot objects; accessed only via .quantity_remaining,
        .lot_id, .source_file, .source_row attributes.
    """
    rows: List[Dict[str, Any]] = []
    for p in problems:
        rows.append({
            "Severity": p.get("severity", "WARN"),
            "Category": p.get("check", "import"),
            "Detail": p.get("detail", ""),
            "Source file": p.get("source_file", ""),
            "Source row": p.get("source_row", ""),
        })
    for w in sim_warnings:
        rows.append({
            "Severity": w.get("severity", "WARN"),
            "Category": w.get("check", "simulate"),
            "Detail": w.get("detail", ""),
            "Source file": w.get("source_file", ""),
            "Source row": w.get("source_row", ""),
        })

    used_fx_years = {m.sell_date.year for m in match_lines} | {
        m.buy_date.year for m in match_lines
    }
    for y in used_fx_years:
        if y not in fx_yearly:
            rows.append({
                "Severity": "ERROR",
                "Category": "missing_fx_yearly",
                "Detail": f"FX_Yearly missing for {y}",
                "Source file": "",
                "Source row": "",
            })

    for y, s in settings.items():
        if s["fx_method"] == "FX_DAILY_CNB":
            need_dates = {m.sell_date for m in match_lines if m.sell_date.year == y} | {
                m.buy_date for m in match_lines if m.buy_date.year == y
            }
            missing = [d for d in need_dates if d not in fx_daily]
            if missing:
                rows.append({
                    "Severity": "ERROR",
                    "Category": "missing_fx_daily",
                    "Detail": f"{len(missing)} trade dates in {y} lacked FX_DAILY_CNB rate.",
                    "Source file": "",
                    "Source row": "",
                })

    if fx.missing_daily:
        rows.append({
            "Severity": "ERROR",
            "Category": "missing_fx_daily",
            "Detail": (
                "Trusted calculation encountered unresolved FX_DAILY_CNB dates: "
                f"{len(sorted(set(fx.missing_daily)))}"
            ),
            "Source file": "",
            "Source row": "",
        })

    if fx.missing_yearly:
        rows.append({
            "Severity": "ERROR",
            "Category": "missing_fx_yearly",
            "Detail": (
                "Trusted calculation encountered unresolved yearly FX for "
                f"{len(sorted(set(fx.missing_yearly)))} tax year(s)."
            ),
            "Source file": "",
            "Source row": "",
        })

    manifest_years = set(frozen_snapshots.keys()) | {
        y for y in year_end_inventory.keys() if locked_years.get(y)
    }
    for y, locked in locked_years.items():
        if locked and y not in manifest_years:
            rows.append({
                "Severity": "ERROR",
                "Category": "locked_year_no_snapshot",
                "Detail": (
                    f"Year {y} marked Locked but no frozen snapshot manifest exists yet."
                ),
                "Source file": "",
                "Source row": "",
            })

    for key, method in method_selection.items():
        if method not in supported_methods:
            rows.append({
                "Severity": "ERROR",
                "Category": "invalid_method",
                "Detail": f"Invalid method '{method}' for {key}",
                "Source file": "",
                "Source row": "",
            })

    for s in split_warnings:
        rows.append({
            "Severity": "INFO",
            "Category": "split_audit_hint",
            "Detail": (
                f"{s['Instrument_ID']} {s['From date']} -> {s['To date']} "
                f"ratio {s['Ratio (next/prev)']}"
            ),
            "Source file": "",
            "Source row": "",
        })

    for lot in lots_final:
        if lot.quantity_remaining < -1e-6:
            rows.append({
                "Severity": "ERROR",
                "Category": "negative_remaining",
                "Detail": f"Lot {lot.lot_id} remaining {lot.quantity_remaining}",
                "Source file": lot.source_file,
                "Source row": lot.source_row,
            })

    if not rows:
        rows.append({
            "Severity": "INFO",
            "Category": "all_clear",
            "Detail": "No issues detected by static checks.",
            "Source file": "",
            "Source row": "",
        })
    return rows

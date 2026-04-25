"""Tax summary helpers.

Behavior-preserving extraction from build_stock_tax_workbook.py.
Contains build_yearly_summary, run_method_comparison, split_audit.

Monolith-defined types (Transaction, MatchLine) are accepted as Any
to avoid circular imports.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from stock_tax_app.engine import policy
from stock_tax_app.engine.fx import FXResolver
from stock_tax_app.engine.matching import simulate

# Mirror of the monolith constants — both must stay in sync.
DEFAULT_TAX_RATE: float = 0.15
DEFAULT_APPLY_100K: bool = False
DEFAULT_100K_THRESHOLD: float = 100_000.0  # CZK
DEFAULT_FX_METHOD: str = "FX_UNIFIED_GFR"


def build_yearly_summary(
    match_lines: List[Any],
    settings: Dict[int, Dict[str, Any]],
    *,
    default_tax_rate: float = DEFAULT_TAX_RATE,
    default_apply_100k: bool = DEFAULT_APPLY_100K,
    default_100k_threshold: float = DEFAULT_100K_THRESHOLD,
    default_fx_method: str = DEFAULT_FX_METHOD,
) -> List[Dict[str, Any]]:
    by_year: Dict[int, Dict[str, Any]] = defaultdict(lambda: {
        "gross_proceeds": 0.0, "gross_proceeds_pre_sell_commission": 0.0,
        "total_cost_basis": 0.0, "non_exempt_cost_basis": 0.0,
        "total_pnl": 0.0, "exempt_proceeds": 0.0,
        "exempt_gain": 0.0, "taxable_gains": 0.0, "taxable_losses": 0.0,
        "match_count": 0,
    })
    for m in match_lines:
        y = m.tax_year
        slot = by_year[y]
        slot["gross_proceeds"] += m.proceeds_czk
        slot["gross_proceeds_pre_sell_commission"] += (
            m.proceeds_czk + (m.allocated_sell_commission_usd * m.fx_rate_sell)
        )
        slot["total_cost_basis"] += m.cost_basis_czk
        slot["total_pnl"] += m.proceeds_czk - m.cost_basis_czk
        slot["match_count"] += 1
        if m.time_test_exempt:
            slot["exempt_proceeds"] += m.proceeds_czk
            slot["exempt_gain"] += m.proceeds_czk - m.cost_basis_czk
        else:
            slot["non_exempt_cost_basis"] += m.cost_basis_czk
            pnl = m.taxable_gain_czk
            if pnl >= 0:
                slot["taxable_gains"] += pnl
            else:
                slot["taxable_losses"] += -pnl

    out: List[Dict[str, Any]] = []
    for y in sorted(set(list(by_year.keys()) + list(settings.keys()))):
        s = settings.get(y, {
            "tax_rate": default_tax_rate,
            "apply_100k": default_apply_100k,
            "fx_method": default_fx_method,
            "locked": False,
        })
        slot = by_year.get(y)
        if slot is None:
            out.append({
                "Tax year": y,
                "Gross proceeds CZK (all sells)": 0.0,
                "Time-test exempt proceeds CZK": 0.0,
                "Non-exempt cost basis CZK": 0.0,
                "Non-exempt proceeds CZK": 0.0,
                "Taxable gains CZK": 0.0,
                "Taxable losses CZK": 0.0,
                "Pre-exemption tax base CZK": 0.0,
                "100k threshold met?": False,
                "Apply 100k exemption?": s["apply_100k"],
                "Final tax base CZK": 0.0,
                "Tax rate": s["tax_rate"],
                "Tax due CZK": 0.0,
                "FX method": s["fx_method"],
                "Locked?": s.get("locked", False),
                "Match line count": 0,
                "Note": "no sales",
            })
            continue
        pre_base = max(0.0, slot["taxable_gains"] - slot["taxable_losses"])
        under_100k = (
            slot["gross_proceeds_pre_sell_commission"] <= default_100k_threshold
        )
        final_base = pre_base
        note = ""
        if s["apply_100k"] and under_100k:
            final_base = 0.0
            note = (
                "100k exemption applied (gross proceeds before sell "
                "commission <= 100 000 CZK)"
            )
        tax = final_base * s["tax_rate"]
        out.append({
            "Tax year": y,
            "Gross proceeds CZK (all sells)": round(slot["gross_proceeds"], 2),
            "Time-test exempt proceeds CZK": round(slot["exempt_proceeds"], 2),
            "Non-exempt cost basis CZK": round(slot["non_exempt_cost_basis"], 2),
            "Non-exempt proceeds CZK": round(
                slot["gross_proceeds"] - slot["exempt_proceeds"], 2),
            "Taxable gains CZK": round(slot["taxable_gains"], 2),
            "Taxable losses CZK": round(slot["taxable_losses"], 2),
            "Pre-exemption tax base CZK": round(pre_base, 2),
            "100k threshold met?": under_100k,
            "Apply 100k exemption?": s["apply_100k"],
            "Final tax base CZK": round(final_base, 2),
            "Tax rate": s["tax_rate"],
            "Tax due CZK": round(tax, 2),
            "FX method": s["fx_method"],
            "Locked?": s.get("locked", False),
            "Match line count": slot["match_count"],
            "Note": note,
        })
    return out


def run_method_comparison(
    txs: List[Any],
    settings: Dict[int, Dict[str, Any]],
    method_selection: Dict[Tuple[int, str], str],
    locked_years: Dict[int, bool],
    corporate_actions: List[Dict[str, Any]],
    frozen_inventory: Dict[int, List[Dict[str, Any]]],
    frozen_matching: Dict[int, List[Dict[str, Any]]],
    frozen_snapshots: Dict[int, Dict[str, Any]],
    fx: FXResolver,
    *,
    lot_factory: Any,
    match_line_factory: Any,
    default_method: str,
    to_bool: Any,
    parse_trade_date: Any,
    supported_methods: Optional[Tuple[str, ...]] = None,
) -> List[Dict[str, Any]]:
    """For each tax year, re-run matching with each global method override.

    Returns one row per year per method plus one "Selected" row.
    """
    if supported_methods is None:
        supported_methods = policy.SUPPORTED_METHODS

    results: Dict[Tuple[int, str], Dict[str, float]] = {}
    for method in list(supported_methods) + ["SELECTED"]:
        override = None if method == "SELECTED" else method
        _, lines, _, _ = simulate(
            txs, settings, method_selection, locked_years,
            corporate_actions, frozen_inventory, frozen_matching,
            frozen_snapshots, fx, override,
            lot_factory=lot_factory,
            match_line_factory=match_line_factory,
            default_method=default_method,
            to_bool=to_bool,
            parse_trade_date=parse_trade_date,
        )
        summary = build_yearly_summary(lines, settings)
        for row in summary:
            key = (row["Tax year"], method)
            results[key] = {
                "tax_base": row["Final tax base CZK"],
                "tax": row["Tax due CZK"],
                "gains": row["Taxable gains CZK"],
                "losses": row["Taxable losses CZK"],
                "gross_proceeds": row["Gross proceeds CZK (all sells)"],
            }
    years = sorted({k[0] for k in results.keys()})
    out: List[Dict[str, Any]] = []
    for y in years:
        row: Dict[str, Any] = {"Tax year": y}
        min_tax = None
        for m in supported_methods:
            r = results.get((y, m), {"tax_base": 0.0, "tax": 0.0})
            row[f"{m} tax base CZK"] = r["tax_base"]
            row[f"{m} tax CZK"] = r["tax"]
            if min_tax is None or r["tax"] < min_tax[1]:
                min_tax = (m, r["tax"])
        sel = results.get((y, "SELECTED"), {"tax_base": 0.0, "tax": 0.0})
        row["Selected method tax base CZK"] = sel["tax_base"]
        row["Selected method tax CZK"] = sel["tax"]
        row["Best method"] = min_tax[0] if min_tax else ""
        row["Best method tax CZK"] = min_tax[1] if min_tax else 0.0
        row["Delta selected vs best CZK"] = round(
            sel["tax"] - (min_tax[1] if min_tax else 0.0), 2)
        out.append(row)
    return out


def split_audit(txs: List[Any]) -> List[Dict[str, Any]]:
    """Very light heuristic: per instrument, look for large step-change in
    average price across neighbouring BUY/SELL events.

    This does not prove anything; it just raises attention so the operator
    can manually enter a split if Yahoo data is or isn't already adjusted.
    """
    out: List[Dict[str, Any]] = []
    by_inst: Dict[str, List[Any]] = defaultdict(list)
    for tx in txs:
        by_inst[tx.instrument_id].append(tx)
    for inst, events in by_inst.items():
        events.sort(key=lambda t: (t.trade_date, t.source_file, t.source_row))
        for i in range(1, len(events)):
            a, b = events[i - 1], events[i]
            if a.price_usd <= 0 or b.price_usd <= 0:
                continue
            ratio = b.price_usd / a.price_usd
            if ratio >= 2.8 or ratio <= 0.35:
                out.append({
                    "Instrument_ID": inst,
                    "From date": a.trade_date,
                    "To date": b.trade_date,
                    "Prev price USD": a.price_usd,
                    "Next price USD": b.price_usd,
                    "Ratio (next/prev)": round(ratio, 4),
                    "Hint": (
                        "Possible unrecorded split or data already "
                        "adjusted. Verify manually in Corporate_Actions."
                    ),
                })
    return out

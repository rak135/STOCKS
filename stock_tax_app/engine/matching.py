"""Lot matching engine.

Behavior-preserving extraction from build_stock_tax_workbook.py.
Contains FIFO/LIFO/MIN_GAIN/MAX_GAIN selection helpers, the global
optimizer, the main simulate() loop, and frozen-lot helpers.

Imports:
- FXResolver from stock_tax_app.engine.fx (extracted in Phase 4)
- apply_corporate_action_to_lots from stock_tax_app.engine.corporate_actions
- policy from stock_tax_app.engine

Monolith-defined types (Lot, Transaction, MatchLine) are:
- Accepted as Any in type hints to avoid circular imports
- Constructed via injected factory callables (lot_factory, match_line_factory)
  in functions that create new instances
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from stock_tax_app.engine import policy
from stock_tax_app.engine.corporate_actions import (
    apply_corporate_action_to_lots as _apply_ca,
)
from stock_tax_app.engine.fx import FXResolver


# -----------------------------------------------------------------------
# Date helpers
# -----------------------------------------------------------------------

def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # leap-year Feb 29
        return d.replace(year=d.year + years, day=28)


def _coerce_date(v: Any, parse_trade_date: Callable) -> date:
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        d = parse_trade_date(v)
        if d is not None:
            return d
    return date.min


# -----------------------------------------------------------------------
# Lot helpers
# -----------------------------------------------------------------------

def _clone_lots(lots: List[Any]) -> List[Any]:
    return [dataclasses.replace(l, adjustments=list(l.adjustments))
            for l in lots]


def _lots_from_frozen(
    inventory_rows: List[Dict[str, Any]],
    *,
    lot_factory: Callable[..., Any],
    parse_trade_date: Callable[[str], Optional[date]],
) -> List[Any]:
    out: List[Any] = []
    for r in inventory_rows:
        try:
            qty_original = float(r.get("Quantity original"))
            qty_remaining = float(r.get("Quantity remaining"))
            price = float(r.get("Price per share USD"))
            comm = float(r.get("Buy commission USD") or 0.0)
        except (TypeError, ValueError):
            continue
        bd = r.get("Buy date")
        if isinstance(bd, datetime):
            bd = bd.date()
        elif isinstance(bd, str):
            bd = parse_trade_date(bd)
        if not isinstance(bd, date):
            continue
        out.append(lot_factory(
            lot_id=str(r.get("Lot_ID") or "FROZEN"),
            tx_id=str(r.get("Tx_ID") or "FROZEN"),
            instrument_id=str(r.get("Instrument_ID") or ""),
            source_broker=str(r.get("Source broker") or ""),
            source_account=str(r.get("Source account") or ""),
            source_file=str(r.get("Source file") or ""),
            source_row=int(r.get("Source row") or 0),
            buy_date=bd,
            quantity_original=qty_original,
            quantity_remaining=qty_remaining,
            price_per_share_usd=price,
            buy_commission_total_usd=comm,
        ))
    return out


def _snapshot_status(snapshot_row: Optional[Dict[str, Any]]) -> str:
    if not snapshot_row:
        return ""
    return str(snapshot_row.get("Snapshot status") or "").strip().upper()


def _snapshot_is_stale(snapshot_row: Optional[Dict[str, Any]]) -> bool:
    return _snapshot_status(snapshot_row) in {"STALE", "NEEDS_REBUILD"}


def _snapshot_rebuild_detail(changed_year: int, later_snapshot_years: List[int]) -> str:
    years = ", ".join(str(y) for y in later_snapshot_years)
    return (
        f"Year {changed_year} was changed or locked without a matching snapshot while later "
        f"frozen snapshot year(s) {years} exist. Those later snapshots may be stale. "
        f"Rebuild/recalculate frozen snapshots from {changed_year} onward is required."
    )


# -----------------------------------------------------------------------
# Scoring helpers
# -----------------------------------------------------------------------

def _expected_contribution_per_share_czk(
    lot: Any,
    sell: Any,
    sell_commission_per_share_usd: float,
    fx: FXResolver,
) -> Tuple[float, bool]:
    """Return (per-share taxable CZK contribution, exempt?)."""
    exempt = sell.trade_date > _add_years(lot.buy_date, 3)
    if exempt:
        return 0.0, True
    fx_buy, _ = fx.rate_for(lot.buy_date)
    fx_sell, _ = fx.rate_for(sell.trade_date)
    net_sell = (sell.price_usd - sell_commission_per_share_usd) * fx_sell
    net_buy = (lot.price_per_share_usd
               + lot.buy_commission_per_share_usd) * fx_buy
    return (net_sell - net_buy), False


def rank_lots_for_sell(
    lots: List[Any],
    sell: Any,
    method: str,
    fx: FXResolver,
) -> List[Any]:
    available = [l for l in lots if l.instrument_id == sell.instrument_id
                 and l.quantity_remaining > 1e-9
                 and l.buy_date <= sell.trade_date]
    if method == "FIFO":
        available.sort(key=lambda l: (l.buy_date, l.source_file, l.source_row))
        return available
    if method == "LIFO":
        available.sort(key=lambda l: (l.buy_date, l.source_file, l.source_row),
                       reverse=True)
        return available

    # MIN_GAIN / MAX_GAIN
    sell_comm_per_share = (sell.commission_usd / sell.quantity
                           if sell.quantity > 0 else 0.0)
    scored: List[Tuple[float, bool, Any]] = []
    for lot in available:
        contrib, exempt = _expected_contribution_per_share_czk(
            lot, sell, sell_comm_per_share, fx)
        scored.append((contrib, exempt, lot))

    if method == "MIN_GAIN":
        scored.sort(key=lambda t: (t[0], t[2].buy_date,
                                   t[2].source_file, t[2].source_row))
    elif method == "MAX_GAIN":
        scored.sort(key=lambda t: (-t[0], t[2].buy_date,
                                   t[2].source_file, t[2].source_row))
    return [t[2] for t in scored]


# -----------------------------------------------------------------------
# Match line builder
# -----------------------------------------------------------------------

def _make_match_line(
    sell: Any,
    lot: Any,
    take: float,
    fx: FXResolver,
    match_counter: dict,
    method: str,
    *,
    match_line_factory: Callable[..., Any],
) -> Any:
    """Build a single match line from (sell, lot, take)."""
    sell_comm_ps = sell.commission_usd / sell.quantity if sell.quantity > 0 else 0.0
    fx_buy, _ = fx.rate_for(lot.buy_date)
    fx_sell, _ = fx.rate_for(sell.trade_date)
    alloc_buy_comm_usd = (
        lot.buy_commission_total_usd * (take / lot.quantity_original)
        if lot.quantity_original > 0 else 0.0
    )
    alloc_sell_comm_usd = sell_comm_ps * take
    cost_basis_usd = (lot.price_per_share_usd * take) + alloc_buy_comm_usd
    proceeds_usd = (sell.price_usd * take) - alloc_sell_comm_usd
    cost_basis_czk = cost_basis_usd * fx_buy
    proceeds_czk = proceeds_usd * fx_sell
    exempt = sell.trade_date > _add_years(lot.buy_date, 3)
    taxable_gain = 0.0 if exempt else (proceeds_czk - cost_basis_czk)
    match_counter["n"] += 1
    return match_line_factory(
        match_id=f"M{match_counter['n']:06d}",
        sell_tx_id=sell.tx_id,
        sell_date=sell.trade_date,
        sell_source_broker=sell.source_broker,
        sell_source_file=sell.source_file,
        sell_source_row=sell.source_row,
        instrument_id=sell.instrument_id,
        buy_lot_id=lot.lot_id,
        buy_tx_id=lot.tx_id,
        buy_date=lot.buy_date,
        buy_source_broker=lot.source_broker,
        buy_source_file=lot.source_file,
        buy_source_row=lot.source_row,
        quantity=take,
        buy_price_per_share_usd=lot.price_per_share_usd,
        sell_price_per_share_usd=sell.price_usd,
        allocated_buy_commission_usd=alloc_buy_comm_usd,
        allocated_sell_commission_usd=alloc_sell_comm_usd,
        fx_rate_buy=fx_buy,
        fx_rate_sell=fx_sell,
        cost_basis_czk=cost_basis_czk,
        proceeds_czk=proceeds_czk,
        holding_days=(sell.trade_date - lot.buy_date).days,
        time_test_exempt=exempt,
        taxable=not exempt,
        taxable_gain_czk=taxable_gain,
        method=method,
        tax_year=sell.trade_date.year,
    )


# -----------------------------------------------------------------------
# Per-sell FIFO/LIFO matcher
# -----------------------------------------------------------------------

def match_sell(
    sell: Any,
    lots: List[Any],
    method: str,
    fx: FXResolver,
    match_counter: Dict[str, int],
    *,
    match_line_factory: Callable[..., Any],
) -> Tuple[List[Any], float]:
    """Consume lots to cover the sell (FIFO / LIFO / per-sell greedy).

    Returns (match lines, unmatched quantity).
    Note: MIN_GAIN and MAX_GAIN are handled by _match_global_optimized()
    in simulate(); this function only handles FIFO/LIFO (and serves as
    fallback for edge-case calls with other methods).
    """
    remaining = sell.quantity
    ranked = rank_lots_for_sell(lots, sell, method, fx)
    out: List[Any] = []
    for lot in ranked:
        if remaining <= 1e-9:
            break
        take = min(remaining, lot.quantity_remaining)
        if take <= 1e-9:
            continue
        out.append(_make_match_line(sell, lot, take, fx, match_counter, method,
                                    match_line_factory=match_line_factory))
        lot.quantity_remaining -= take
        remaining -= take
    return out, remaining


# -----------------------------------------------------------------------
# Annual global optimizer for MIN_GAIN / MAX_GAIN
# -----------------------------------------------------------------------

def _match_global_optimized(
    sells: List[Any],
    lots: List[Any],
    method: str,
    fx: FXResolver,
    match_counter: dict,
    *,
    match_line_factory: Callable[..., Any],
) -> Tuple[List[Any], Dict[str, float]]:
    """True annual global optimizer for MIN_GAIN / MAX_GAIN.

    Considers ALL sells for a (year, instrument) batch simultaneously and
    assigns lots globally — unlike per-sell greedy matching.

    Algorithm (global greedy assignment):
      1. Build every eligible (sell, lot) pair respecting buy_date <= sell_date.
      2. Score each pair by taxable-gain CZK contribution per share:
         exempt pairs score 0 (irrelevant to taxable gain).
      3. Sort globally: ascending for MIN_GAIN, descending for MAX_GAIN.
      4. Greedily consume from the most-favourable pair first, tracking
         remaining quantities for each sell and each lot independently.
      5. Leftover sells are completed FIFO as a fallback (data-quality
         safeguard; should not happen with clean input).

    This is LP-optimal for identical sell prices and near-optimal for
    multi-sell scenarios. Strictly better than per-sell greedy in all
    cases where multiple sells compete for the same lot pool.

    Returns (match_lines, {sell_tx_id: unmatched_qty}).
    """
    if not sells or not lots:
        return [], {s.tx_id: s.quantity for s in sells}

    sell_remaining: Dict[str, float] = {s.tx_id: s.quantity for s in sells}
    lot_remaining: Dict[str, float] = {l.lot_id: l.quantity_remaining for l in lots}
    lot_by_id: Dict[str, Any] = {l.lot_id: l for l in lots}
    sell_by_id: Dict[str, Any] = {s.tx_id: s for s in sells}

    # Build eligible (gain_per_unit, sell_date_iso, buy_date_iso, sell_id, lot_id)
    pairs: List[tuple] = []
    for sell in sells:
        sell_comm_ps = sell.commission_usd / sell.quantity if sell.quantity > 0 else 0.0
        fx_sell, _ = fx.rate_for(sell.trade_date)
        for lot in lots:
            if lot.buy_date > sell.trade_date:
                continue
            exempt = sell.trade_date > _add_years(lot.buy_date, 3)
            if exempt:
                gain_pu = 0.0
            else:
                fx_buy, _ = fx.rate_for(lot.buy_date)
                proceeds_pu = (sell.price_usd - sell_comm_ps) * fx_sell
                cost_pu = (lot.price_per_share_usd
                           + lot.buy_commission_per_share_usd) * fx_buy
                gain_pu = proceeds_pu - cost_pu
            pairs.append((
                gain_pu,
                sell.trade_date.isoformat(),
                lot.buy_date.isoformat(),
                sell.tx_id,
                lot.lot_id,
            ))

    reverse = (method == "MAX_GAIN")
    pairs.sort(reverse=reverse)

    out_lines: List[Any] = []
    for gain_pu, _sd, _ld, sell_tx_id, lot_id in pairs:
        sr = sell_remaining.get(sell_tx_id, 0.0)
        lr = lot_remaining.get(lot_id, 0.0)
        if sr < 1e-9 or lr < 1e-9:
            continue
        take = min(sr, lr)
        sell = sell_by_id[sell_tx_id]
        lot = lot_by_id[lot_id]
        out_lines.append(_make_match_line(sell, lot, take, fx,
                                          match_counter, method,
                                          match_line_factory=match_line_factory))
        sell_remaining[sell_tx_id] = sr - take
        lot_remaining[lot_id] = lr - take

    # Apply lot quantity changes back to actual lot objects
    for lot in lots:
        lot.quantity_remaining = lot_remaining[lot.lot_id]

    # FIFO fallback for any unresolved sells (data quality safeguard)
    for sell_tx_id, leftover in list(sell_remaining.items()):
        if leftover < 1e-9:
            continue
        sell = sell_by_id[sell_tx_id]
        for lot in sorted(lots, key=lambda l: (l.buy_date, l.source_file,
                                               l.source_row)):
            if lot.buy_date > sell.trade_date or lot.quantity_remaining < 1e-9:
                continue
            take = min(leftover, lot.quantity_remaining)
            if take < 1e-9:
                continue
            out_lines.append(_make_match_line(sell, lot, take, fx,
                                              match_counter,
                                              method + "_fallback_fifo",
                                              match_line_factory=match_line_factory))
            lot.quantity_remaining -= take
            leftover -= take
            sell_remaining[sell_tx_id] = leftover
            if leftover < 1e-9:
                break

    return out_lines, sell_remaining


# -----------------------------------------------------------------------
# Main simulation loop
# -----------------------------------------------------------------------

def simulate(
    txs: List[Any],
    settings: Dict[int, Dict[str, Any]],
    method_selection: Dict[Tuple[int, str], str],
    locked_years: Dict[int, bool],
    corporate_actions: List[Dict[str, Any]],
    frozen_inventory: Dict[int, List[Dict[str, Any]]],
    frozen_matching: Dict[int, List[Dict[str, Any]]],
    frozen_snapshots: Dict[int, Dict[str, Any]],
    fx: FXResolver,
    override_method: Optional[str] = None,
    *,
    lot_factory: Callable[..., Any],
    match_line_factory: Callable[..., Any],
    default_method: str,
    to_bool: Callable[[Any, bool], bool],
    parse_trade_date: Callable[[str], Optional[date]],
) -> Tuple[List[Any], List[Any], List[Dict[str, Any]], Dict[int, List[Any]]]:
    """Run full lot-matching over transactions.

    Returns (final lots, match lines, warnings, per-year end inventories).
    """
    warnings: List[Dict[str, Any]] = []

    # Determine latest locked year with a usable frozen snapshot.
    snapshot_years = set(frozen_snapshots.keys()) | {
        y for y, rows in frozen_inventory.items() if rows
    }
    stale_snapshot_years = {
        y for y, row in frozen_snapshots.items() if _snapshot_is_stale(row)
    }
    for y in sorted(stale_snapshot_years):
        if not locked_years.get(y):
            continue
        row = frozen_snapshots.get(y) or {}
        detail = str(row.get("Status detail") or "").strip()
        if not detail:
            detail = (
                f"Frozen snapshot year {y} is marked stale and must be rebuilt before it can "
                "be reused as seed state."
            )
        warning = {
            "check": "locked_year_snapshot_rebuild_required",
            "severity": "ERROR",
            "detail": detail,
            "stale_snapshot_years": [y],
        }
        stale_after_year = row.get("Stale after year")
        try:
            if stale_after_year not in (None, ""):
                warning["changed_year"] = int(stale_after_year)
        except (TypeError, ValueError):
            pass
        warnings.append(warning)

    for y in sorted(locked_years.keys()):
        if not locked_years.get(y):
            continue
        if y in snapshot_years and y not in stale_snapshot_years:
            continue
        later_snapshot_years = [
            later_year
            for later_year in sorted(snapshot_years)
            if later_year > y and locked_years.get(later_year)
        ]
        if later_snapshot_years:
            stale_snapshot_years.update(later_snapshot_years)
            warnings.append({
                "check": "locked_year_snapshot_rebuild_required",
                "severity": "ERROR",
                "detail": _snapshot_rebuild_detail(y, later_snapshot_years),
                "changed_year": y,
                "stale_snapshot_years": later_snapshot_years,
            })

    usable_snapshot_years = {
        y for y in snapshot_years if y not in stale_snapshot_years
    }
    seed_year: Optional[int] = None
    for y in sorted(locked_years.keys(), reverse=True):
        if locked_years.get(y) and y in usable_snapshot_years:
            seed_year = y
            break
        if (
            locked_years.get(y)
            and y not in snapshot_years
            and not any(
                later_year > y and locked_years.get(later_year)
                for later_year in snapshot_years
            )
        ):
            warnings.append({
                "check": "locked_year_no_snapshot", "severity": "INFO",
                "detail": (
                    f"Year {y} is locked but has no frozen snapshot yet; "
                    "the current run will regenerate it."
                ),
            })
    lots: List[Any] = []
    if seed_year is not None:
        lots = _lots_from_frozen(
            frozen_inventory[seed_year],
            lot_factory=lot_factory,
            parse_trade_date=parse_trade_date,
        )

    # Transactions to process: only those strictly after seed_year.
    eff_txs = [t for t in txs
               if seed_year is None or t.trade_date.year > seed_year]
    # Sort by date, then source_file, row for stable ordering.
    eff_txs.sort(key=lambda t: (t.trade_date, t.source_file, t.source_row))

    match_counter = {"n": 0}
    match_lines: List[Any] = []

    # Preserve historical audit for unlocked years before the seed snapshot.
    if seed_year is not None:
        historical_txs = [
            t for t in txs
            if t.trade_date.year < seed_year and not locked_years.get(t.trade_date.year, False)
        ]
        historical_settings = {
            y: s for y, s in settings.items()
            if y < seed_year and not locked_years.get(y, False)
        }
        historical_actions = [ca for ca in corporate_actions if ca["Date"].year < seed_year]
        if historical_txs:
            _, hist_lines, hist_warnings, _ = simulate(
                txs=historical_txs,
                settings=historical_settings,
                method_selection=method_selection,
                locked_years={y: False for y in historical_settings},
                corporate_actions=historical_actions,
                frozen_inventory={},
                frozen_matching={},
                frozen_snapshots={},
                fx=fx,
                override_method=override_method,
                lot_factory=lot_factory,
                match_line_factory=match_line_factory,
                default_method=default_method,
                to_bool=to_bool,
                parse_trade_date=parse_trade_date,
            )
            match_lines.extend(hist_lines)
            warnings.extend(hist_warnings)

    # Replay frozen matching rows if locked year has them (so audit covers them).
    def _coerce(v: Any) -> date:
        return _coerce_date(v, parse_trade_date)

    for y, rows in frozen_matching.items():
        if not locked_years.get(y):
            continue
        if y in stale_snapshot_years:
            continue
        for r in rows:
            try:
                m = match_line_factory(
                    match_id=str(r.get("Match_ID") or ""),
                    sell_tx_id=str(r.get("Sell_ID") or ""),
                    sell_date=_coerce(r.get("Sell date")),
                    sell_source_broker=str(r.get("Sell source broker") or ""),
                    sell_source_file=str(r.get("Sell source file") or ""),
                    sell_source_row=int(r.get("Sell source row") or 0),
                    instrument_id=str(r.get("Instrument_ID") or ""),
                    buy_lot_id=str(r.get("Buy Lot_ID") or ""),
                    buy_tx_id=str(r.get("Buy Tx_ID") or ""),
                    buy_date=_coerce(r.get("Buy date")),
                    buy_source_broker=str(r.get("Buy source broker") or ""),
                    buy_source_file=str(r.get("Buy source file") or ""),
                    buy_source_row=int(r.get("Buy source row") or 0),
                    quantity=float(r.get("Quantity") or 0.0),
                    buy_price_per_share_usd=float(r.get("Buy price USD") or 0.0),
                    sell_price_per_share_usd=float(r.get("Sell price USD") or 0.0),
                    allocated_buy_commission_usd=float(
                        r.get("Allocated buy commission USD") or 0.0),
                    allocated_sell_commission_usd=float(
                        r.get("Allocated sell commission USD") or 0.0),
                    fx_rate_buy=float(r.get("FX rate buy") or 0.0),
                    fx_rate_sell=float(r.get("FX rate sell") or 0.0),
                    cost_basis_czk=float(r.get("Cost basis CZK") or 0.0),
                    proceeds_czk=float(r.get("Proceeds CZK") or 0.0),
                    holding_days=int(r.get("Holding days") or 0),
                    time_test_exempt=to_bool(r.get("Time-test exempt?"), False),
                    taxable=to_bool(r.get("Taxable?"), True),
                    taxable_gain_czk=float(r.get("Taxable gain CZK") or 0.0),
                    method=str(r.get("Method") or ""),
                    tax_year=int(r.get("Tax year") or y),
                )
                match_lines.append(m)
            except (TypeError, ValueError):
                continue

    # Apply any corporate actions that predate seed_year+1 against frozen lots
    # as a safety net (user may have entered late split data).
    for ca in corporate_actions:
        if seed_year is None or ca["Date"].year > seed_year:
            continue
        _apply_ca(lots, ca)

    year_end_inventory: Dict[int, List[Any]] = {}

    tx_iter = iter(eff_txs)
    pending: Optional[Any] = next(tx_iter, None)

    ca_iter = iter(corporate_actions)
    next_ca: Optional[Dict[str, Any]] = next(ca_iter, None)
    # Skip CAs already applied (dated <= seed_year year-end).
    while next_ca is not None and seed_year is not None \
            and next_ca["Date"].year <= seed_year:
        next_ca = next(ca_iter, None)

    # Merge stream by date: CAs and transactions in chronological order.
    def next_action() -> Tuple[Optional[str], Any]:
        nonlocal pending, next_ca
        if pending is None and next_ca is None:
            return None, None
        if pending is None:
            ca = next_ca
            next_ca = next(ca_iter, None)
            return "CA", ca
        if next_ca is None:
            tx = pending
            pending = next(tx_iter, None)
            return "TX", tx
        # Both exist — pick earlier date; CAs apply first on same date.
        if next_ca["Date"] <= pending.trade_date:
            ca = next_ca
            next_ca = next(ca_iter, None)
            return "CA", ca
        tx = pending
        pending = next(tx_iter, None)
        return "TX", tx

    current_year: Optional[int] = None
    # Global optimizer buffer: {instrument_id: [sell transaction]}
    deferred_global_sells: Dict[str, List[Any]] = defaultdict(list)

    def flush_deferred_sells(flush_year: Optional[int]) -> None:
        """Process buffered MIN_GAIN/MAX_GAIN sells for completed year."""
        if flush_year is None:
            return
        for inst, sell_list in list(deferred_global_sells.items()):
            year_sells = [s for s in sell_list if s.trade_date.year == flush_year]
            if not year_sells:
                continue
            method = override_method if override_method is not None else (
                method_selection.get((flush_year, inst), policy.default_method_for(flush_year))
            )
            avail_lots = [l for l in lots
                          if l.instrument_id == inst and l.quantity_remaining > 1e-9]
            lines, unmatched_map = _match_global_optimized(
                year_sells, avail_lots, method, fx, match_counter,
                match_line_factory=match_line_factory)
            match_lines.extend(lines)
            for tx in year_sells:
                leftover = unmatched_map.get(tx.tx_id, 0.0)
                if leftover > 1e-6:
                    severity = "WARN" if leftover < 1e-3 else "ERROR"
                    warnings.append({
                        "check": "insufficient_lots", "severity": severity,
                        "source_file": tx.source_file,
                        "source_row": tx.source_row,
                        "detail": (f"SELL {tx.symbol} {tx.trade_date} qty "
                                   f"{tx.quantity}: unmatched {leftover:.6f}"),
                    })
            # Remove processed sells from buffer
            remaining_in_buf = [s for s in sell_list
                                 if s.trade_date.year != flush_year]
            if remaining_in_buf:
                deferred_global_sells[inst] = remaining_in_buf
            else:
                del deferred_global_sells[inst]

    while True:
        kind, item = next_action()
        if kind is None:
            break
        item_date = item["Date"] if kind == "CA" else item.trade_date
        item_year = item_date.year

        # Snapshot previous year before starting new year actions.
        if current_year is not None and item_year != current_year:
            flush_deferred_sells(current_year)
            year_end_inventory[current_year] = _clone_lots(lots)
        current_year = item_year

        if kind == "CA":
            if item.get("Applied", True):
                _apply_ca(lots, item)
            continue
        # kind == "TX"
        tx: Any = item
        if tx.side == "BUY":
            lot = lot_factory(
                lot_id=f"L_{tx.tx_id}",
                tx_id=tx.tx_id,
                instrument_id=tx.instrument_id,
                source_broker=tx.source_broker,
                source_account=tx.source_account,
                source_file=tx.source_file,
                source_row=tx.source_row,
                buy_date=tx.trade_date,
                quantity_original=tx.quantity,
                quantity_remaining=tx.quantity,
                price_per_share_usd=tx.price_usd,
                buy_commission_total_usd=tx.commission_usd,
            )
            lots.append(lot)
        else:  # SELL
            if override_method is not None:
                method = override_method
            else:
                method = method_selection.get(
                    (tx.trade_date.year, tx.instrument_id), default_method)
            if method in ("MIN_GAIN", "MAX_GAIN"):
                # Buffer for global annual optimizer
                deferred_global_sells[tx.instrument_id].append(tx)
            else:
                lines, unmatched = match_sell(tx, lots, method, fx, match_counter,
                                              match_line_factory=match_line_factory)
                match_lines.extend(lines)
                if unmatched > 1e-6:
                    severity = "WARN" if unmatched < 1e-3 else "ERROR"
                    warnings.append({
                        "check": "insufficient_lots", "severity": severity,
                        "source_file": tx.source_file,
                        "source_row": tx.source_row,
                        "detail": (f"SELL {tx.symbol} {tx.trade_date} qty "
                                   f"{tx.quantity}: unmatched {unmatched:.6f}"),
                    })

    if current_year is not None:
        flush_deferred_sells(current_year)
        year_end_inventory[current_year] = _clone_lots(lots)

    return lots, match_lines, warnings, year_end_inventory

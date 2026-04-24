from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
import re

import build_stock_tax_workbook as workbook

from . import policy, ui_state
from .models import (
    AppSettings,
    AppStatus,
    AuditSummary,
    Check,
    EngineResult,
    FxYear,
    ImportFile,
    ImportSummary,
    MatchedLot,
    MethodComparison,
    NextAction,
    OpenLot,
    OpenPosition,
    Sell,
    SourceRef,
    TaxYear,
)


def _resolve_path(project_dir: Path, value: Path | str | None, default_name: str) -> Path:
    if value is None:
        return (project_dir / default_name).resolve()
    p = Path(value)
    if not p.is_absolute():
        p = project_dir / p
    return p.resolve()


def _discover_csv_inputs(csv_dir: Path) -> list[Path]:
    return sorted(p.resolve() for p in csv_dir.glob("*.csv") if p.is_file())


def _safe_sell_id(raw_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", raw_id)


def _check_level(severity: str) -> str:
    sev = str(severity or "").strip().upper()
    if sev == "ERROR":
        return "error"
    if sev == "WARN":
        return "warn"
    return "info"


def _check_href(category: str) -> str:
    if "fx" in category:
        return "/fx"
    if "method" in category or "filed" in category:
        return "/years"
    if "remaining" in category or "position" in category:
        return "/open-positions"
    if "import" in category:
        return "/import"
    return "/audit"


def _build_checks(calc: workbook.CalculationResult) -> list[Check]:
    rows = workbook.build_check_rows(
        sim_warnings=calc.sim_warnings,
        problems=calc.problems,
        fx_yearly=calc.fx_yearly,
        fx_daily=calc.fx_daily,
        settings=calc.settings,
        locked_years=calc.locked_years,
        frozen_inventory=calc.frozen_inventory,
        split_warnings=calc.split_warnings,
        method_selection=calc.method_selection,
        yearly_summary=calc.yearly_summary,
        match_lines=calc.match_lines,
        lots_final=calc.lots_final,
        year_end_inventory=calc.year_end_inventory,
        frozen_snapshots=calc.frozen_snapshots,
        fx=calc.fx,
    )
    checks: list[Check] = []
    for i, row in enumerate(rows, start=1):
        category = str(row.get("Category") or "check")
        checks.append(
            Check(
                id=f"check-{i}",
                level=_check_level(str(row.get("Severity") or "")),
                message=str(row.get("Detail") or ""),
                href=_check_href(category),
            )
        )
    return checks


def _build_import_summary(calc: workbook.CalculationResult, csv_dir: Path) -> ImportSummary:
    rows_by_file: dict[str, list[workbook.RawRow]] = defaultdict(list)
    for row in calc.raw_rows:
        rows_by_file[row.source_file].append(row)
    warnings_by_file: dict[str, list[str]] = defaultdict(list)
    for row in calc.problems:
        source_file = str(row.get("source_file") or "")
        if source_file:
            warnings_by_file[source_file].append(str(row.get("detail") or ""))

    files: list[ImportFile] = []
    total_warnings = 0
    for entry in calc.import_log:
        name = str(entry.get("Source file") or "")
        file_rows = rows_by_file.get(name, [])
        position_rows = 0
        for raw in file_rows:
            tt = (raw.data.get("Transaction Type") or "").strip()
            td = (raw.data.get("Trade Date") or "").strip()
            if tt or td:
                continue
            qty, ok = workbook.safe_float(raw.data.get("Quantity") or "", default=None)
            if ok and qty is not None:
                position_rows += 1
        warnings = warnings_by_file.get(name, [])
        total_warnings += len(warnings)
        status = "error" if any("error" in w.lower() for w in warnings) else (
            "warnings" if warnings else "ok"
        )
        files.append(
            ImportFile(
                name=name,
                broker=str(entry.get("Broker") or ""),
                account=str(entry.get("Account") or ""),
                total_rows=int(entry.get("Raw rows") or 0),
                trade_rows=int(entry.get("Transactions") or 0),
                ignored_rows=int(entry.get("Ignored") or 0),
                position_rows=position_rows,
                min_trade_date=entry.get("Min Trade Date"),
                max_trade_date=entry.get("Max Trade Date"),
                unique_symbols=[
                    s.strip()
                    for s in str(entry.get("Unique symbols") or "").split(",")
                    if s.strip()
                ],
                warnings=warnings,
                status=status,
            )
        )

    return ImportSummary(
        folder=str(csv_dir),
        files=files,
        total_trade_rows=sum(f.trade_rows for f in files),
        total_ignored_rows=sum(f.ignored_rows for f in files),
        total_warnings=total_warnings,
    )


def _method_values_for_year(
    method_selection: dict[tuple[int, str], str],
    year: int,
    instrument_ids: Iterable[str],
) -> set[str]:
    values: set[str] = set()
    for inst in instrument_ids:
        method = method_selection.get((year, inst))
        if method:
            values.add(method)
    return values


def _effective_year_method(calc: workbook.CalculationResult, year: int) -> str:
    if policy.is_filed(year):
        return policy.filed_method(year) or "LIFO"
    methods = _method_values_for_year(calc.method_selection, year, calc.instrument_ids)
    if not methods:
        return policy.default_method_for(year)
    if len(methods) == 1:
        return next(iter(methods))
    return "MIXED"


def _build_tax_years(
    calc: workbook.CalculationResult,
    state: ui_state.UIState,
) -> list[TaxYear]:
    summary_by_year = {int(row["Tax year"]): row for row in calc.yearly_summary}
    comparison_by_year = {int(row["Tax year"]): row for row in calc.method_comparison}
    years: list[TaxYear] = []
    for year in sorted(calc.years):
        summary = summary_by_year.get(year, {})
        settings = calc.settings.get(year, {})
        filed = policy.is_filed(year)
        locked = policy.is_locked(year) or bool(calc.locked_years.get(year)) or bool(
            summary.get("Locked?")
        )
        method = _effective_year_method(calc, year)
        filed_method = policy.filed_method(year)
        show_comparison = policy.show_method_comparison(year) and year in comparison_by_year

        reconciliation_note = None
        reconciliation_status = "not_filed"
        filed_tax_input = None
        if filed:
            filed_row = calc.filed_reconciliation.get(year, {})
            filed_tax_input = filed_row.get("filed_tax_due")
            if filed_tax_input is None:
                filed_tax_input = summary.get("Tax due CZK")
            workbook_tax_due = float(summary.get("Tax due CZK") or 0.0)
            diff = workbook_tax_due - float(filed_tax_input or 0.0)
            year_note = state.reconciliation_for(year)
            reconciliation_note = year_note.note or None
            if reconciliation_note:
                reconciliation_status = "accepted_with_note"
            elif abs(diff) <= 0.5 and method == (filed_method or method):
                reconciliation_status = "reconciled"
            else:
                reconciliation_status = "needs_attention"

        method_comparison = None
        cmp_row = comparison_by_year.get(year)
        if show_comparison and cmp_row is not None:
            method_comparison = MethodComparison(
                FIFO=float(cmp_row.get("FIFO tax CZK") or 0.0),
                LIFO=float(cmp_row.get("LIFO tax CZK") or 0.0),
                MIN_GAIN=float(cmp_row.get("MIN_GAIN tax CZK") or 0.0),
                MAX_GAIN=float(cmp_row.get("MAX_GAIN tax CZK") or 0.0),
            )

        years.append(
            TaxYear(
                year=year,
                method=method,
                filed_method=filed_method,
                fx_method=str(settings.get("fx_method") or workbook.DEFAULT_FX_METHOD),
                tax_rate=float(settings.get("tax_rate") or workbook.DEFAULT_TAX_RATE),
                exemption_100k=bool(settings.get("apply_100k")),
                gross_proceeds_czk=float(summary.get("Gross proceeds CZK (all sells)") or 0.0),
                exempt_proceeds_czk=float(summary.get("Time-test exempt proceeds CZK") or 0.0),
                taxable_gains_czk=float(summary.get("Taxable gains CZK") or 0.0),
                taxable_losses_czk=float(summary.get("Taxable losses CZK") or 0.0),
                taxable_base_czk=float(summary.get("Final tax base CZK") or 0.0),
                tax_due_czk=float(summary.get("Tax due CZK") or 0.0),
                match_line_count=int(summary.get("Match line count") or 0),
                filed=filed,
                locked=locked,
                show_method_comparison=show_comparison,
                filed_tax_input_czk=(
                    float(filed_tax_input) if filed_tax_input is not None else None
                ),
                reconciliation_status=reconciliation_status,
                reconciliation_note=reconciliation_note,
                method_comparison=method_comparison,
            )
        )
    return years


def _build_sales(
    calc: workbook.CalculationResult,
    state: ui_state.UIState,
) -> list[Sell]:
    lines_by_sell: dict[str, list[workbook.MatchLine]] = defaultdict(list)
    for line in calc.match_lines:
        lines_by_sell[line.sell_tx_id].append(line)

    sells: list[Sell] = []
    sell_txs = [tx for tx in calc.txs if tx.side == "SELL"]
    sell_txs.sort(key=lambda tx: (tx.trade_date, tx.source_file, tx.source_row, tx.tx_id))
    for tx in sell_txs:
        sell_id = _safe_sell_id(tx.tx_id)
        lines = lines_by_sell.get(tx.tx_id, [])
        lines.sort(key=lambda line: (line.buy_date, line.buy_source_file, line.buy_source_row))
        matched_quantity = sum(line.quantity for line in lines)
        unmatched_quantity = max(0.0, tx.quantity - matched_quantity)
        exemptions = {bool(line.time_test_exempt) for line in lines}
        if not lines:
            classification = "taxable"
        elif exemptions == {True}:
            classification = "exempt"
        elif exemptions == {False}:
            classification = "taxable"
        else:
            classification = "mixed"
        review = state.review_for(sell_id)
        matched_lots = [
            MatchedLot(
                lot_id=line.buy_lot_id,
                buy_date=line.buy_date,
                broker=line.buy_source_broker,
                source=SourceRef(file=line.buy_source_file, row=line.buy_source_row),
                quantity=float(line.quantity),
                buy_price_usd=float(line.buy_price_per_share_usd),
                sell_price_usd=float(line.sell_price_per_share_usd),
                fx_buy=float(line.fx_rate_buy),
                fx_sell=float(line.fx_rate_sell),
                cost_basis_czk=float(line.cost_basis_czk),
                proceeds_czk=float(line.proceeds_czk),
                holding_days=int(line.holding_days),
                time_test_exempt=bool(line.time_test_exempt),
                gain_loss_czk=float(line.proceeds_czk - line.cost_basis_czk),
            )
            for line in lines
        ]
        sells.append(
            Sell(
                id=sell_id,
                year=tx.trade_date.year,
                date=tx.trade_date,
                ticker=tx.symbol,
                instrument_id=tx.instrument_id,
                broker=tx.source_broker,
                quantity=float(tx.quantity),
                price_usd=float(tx.price_usd),
                proceeds_czk=float(sum(line.proceeds_czk for line in lines)),
                method=calc.method_selection.get(
                    (tx.trade_date.year, tx.instrument_id), policy.default_method_for(tx.trade_date.year)
                ),
                matched_quantity=float(matched_quantity),
                unmatched_quantity=float(unmatched_quantity),
                classification=classification,
                review_status=review.review_status,
                source=SourceRef(file=tx.source_file, row=tx.source_row),
                note=review.note,
                total_gain_loss_czk=float(
                    sum(line.proceeds_czk - line.cost_basis_czk for line in lines)
                ),
                total_cost_basis_czk=float(sum(line.cost_basis_czk for line in lines)),
                matched_lots=matched_lots,
            )
        )
    return sells


def _build_open_positions(calc: workbook.CalculationResult) -> list[OpenPosition]:
    rows = workbook.build_open_position_rows(
        calc.raw_rows,
        calc.instrument_map,
        calc.lots_final,
    )
    rows_by_inst = {str(row["Instrument_ID"]): row for row in rows}
    ticker_by_inst: dict[str, str] = {}
    for tx in calc.txs:
        ticker_by_inst.setdefault(tx.instrument_id, tx.symbol)

    lots_by_inst: dict[str, list[OpenLot]] = defaultdict(list)
    for lot in calc.lots_final:
        if lot.quantity_remaining <= 1e-9:
            continue
        remaining_cost_usd = (
            lot.quantity_remaining * lot.price_per_share_usd
            + lot.buy_commission_total_usd * (lot.quantity_remaining / lot.quantity_original)
            if lot.quantity_original > 0
            else 0.0
        )
        fx_buy, _ = calc.fx.rate_for(lot.buy_date)
        lots_by_inst[lot.instrument_id].append(
            OpenLot(
                lot_id=lot.lot_id,
                buy_date=lot.buy_date,
                broker=lot.source_broker,
                quantity=float(lot.quantity_remaining),
                cost_basis_czk=float(remaining_cost_usd * fx_buy),
                unrealised_pl_czk=None,
            )
        )

    positions: list[OpenPosition] = []
    for inst in sorted(set(rows_by_inst.keys()) | set(lots_by_inst.keys())):
        row = rows_by_inst.get(inst, {})
        positions.append(
            OpenPosition(
                ticker=ticker_by_inst.get(inst, inst),
                instrument_id=inst,
                calculated_qty=float(row.get("Calculated qty") or 0.0),
                yahoo_qty=(
                    float(row["Yahoo qty"]) if row.get("Yahoo qty") is not None else None
                ),
                difference=(
                    float(row["Difference"]) if row.get("Difference") is not None else None
                ),
                status=str(row.get("Status") or "UNKNOWN").lower(),
                lots=sorted(lots_by_inst.get(inst, []), key=lambda lot: (lot.buy_date, lot.lot_id)),
            )
        )
    return positions


def _build_fx_years(calc: workbook.CalculationResult) -> list[FxYear]:
    tx_dates_by_year: dict[int, set] = defaultdict(set)
    for tx in calc.txs:
        tx_dates_by_year[tx.trade_date.year].add(tx.trade_date)

    years: list[FxYear] = []
    for year in sorted(calc.years):
        method = str(calc.settings.get(year, {}).get("fx_method") or workbook.DEFAULT_FX_METHOD)
        missing_dates = sorted(d for d in tx_dates_by_year.get(year, set()) if d not in calc.fx_daily)
        source_label = calc.fx_yearly_sources.get(year, "default")
        years.append(
            FxYear(
                year=year,
                method=method,
                unified_rate=calc.fx_yearly.get(year),
                daily_cached=sum(1 for d in calc.fx_daily if d.year == year),
                daily_expected=len(tx_dates_by_year.get(year, set())) if method == "FX_DAILY_CNB" else 0,
                missing_dates=missing_dates if method == "FX_DAILY_CNB" else [],
                source_label=source_label,
                source_url=None,
                verified_at=None,
                manual_override="manual" in source_label.lower(),
                locked=policy.is_locked(year) or bool(calc.locked_years.get(year)),
            )
        )
    return years


def _build_settings(project_dir: Path, csv_dir: Path, output_path: Path) -> AppSettings:
    return AppSettings(
        project_folder=str(project_dir),
        csv_folder=str(csv_dir),
        output_path=str(output_path),
        cache_folder=str(output_path.parent),
        default_tax_rate=workbook.DEFAULT_TAX_RATE,
        default_fx_method=workbook.DEFAULT_FX_METHOD,
        default_100k=workbook.DEFAULT_APPLY_100K,
        unmatched_qty_tolerance=1e-3,
        position_reconciliation_tolerance=1e-4,
        backup_on_recalc=False,
        require_confirm_unlock=True,
        keep_n_snapshots=1,
        excel_validation="strict",
    )


def _build_audit_summary(calc: workbook.CalculationResult, tax_years: list[TaxYear]) -> AuditSummary:
    return AuditSummary(
        year_rows=tax_years,
        trace_counts={
            "csv_files": len(calc.inputs),
            "raw_rows": len(calc.raw_rows),
            "transactions": len(calc.txs),
            "ignored_rows": len(calc.ignored),
            "match_lines": len(calc.match_lines),
            "open_lots": sum(1 for lot in calc.lots_final if lot.quantity_remaining > 1e-9),
        },
        locked_snapshots=sorted(calc.frozen_snapshots.keys()),
    )


def _build_status(
    project_dir: Path,
    csv_dir: Path,
    output_path: Path,
    unresolved_checks: list[Check],
) -> AppStatus:
    if any(check.level == "error" for check in unresolved_checks):
        global_status = "blocked"
    elif any(check.level == "warn" for check in unresolved_checks):
        global_status = "needs_review"
    else:
        global_status = "ready"
    next_action = None
    if unresolved_checks:
        first = unresolved_checks[0]
        next_action = NextAction(label="Review checks", href=first.href or "/audit")
    return AppStatus(
        project_path=str(project_dir),
        csv_folder=str(csv_dir),
        output_path=str(output_path),
        last_calculated_at=datetime.now(timezone.utc),
        global_status=global_status,
        next_action=next_action,
        unresolved_checks=unresolved_checks,
    )


def run(
    project_dir: Path | str,
    csv_dir: Path | str | None = None,
    output_path: Path | str | None = None,
    write_workbook: bool = True,
) -> EngineResult:
    project_path = Path(project_dir).resolve()
    csv_path = _resolve_path(project_path, csv_dir, ".csv")
    output = _resolve_path(project_path, output_path, workbook.CANONICAL_OUTPUT_NAME)

    inputs = _discover_csv_inputs(csv_path)
    calc = workbook.calculate_workbook_data(
        inputs=inputs,
        out_path=output,
        fetch_missing_fx=True,
    )
    if write_workbook:
        workbook.write_calculation_result(calc, backup_existing=False)

    state = ui_state.load(output)
    checks = _build_checks(calc)
    unresolved_checks = [check for check in checks if check.level != "info"]
    sales = _build_sales(calc, state)
    tax_years = _build_tax_years(calc, state)
    open_positions = _build_open_positions(calc)
    fx_years = _build_fx_years(calc)
    settings = _build_settings(project_path, csv_path, output)
    audit_summary = _build_audit_summary(calc, tax_years)
    app_status = _build_status(project_path, csv_path, output, unresolved_checks)

    return EngineResult(
        app_status=app_status,
        import_summary=_build_import_summary(calc, csv_path),
        tax_years=tax_years,
        unresolved_checks=unresolved_checks,
        sales=sales,
        open_positions=open_positions,
        fx_years=fx_years,
        audit_summary=audit_summary,
        settings=settings,
    )

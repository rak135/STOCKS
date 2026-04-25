from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import build_stock_tax_workbook as workbook

from stock_tax_app.state import project_store

from . import policy, ui_state
from .models import (
    AppSettings,
    AppStatus,
    AuditSummary,
    Check,
    CollectionTruth,
    EngineResult,
    FxYear,
    FxYearList,
    ImportFile,
    ImportSummary,
    MatchedLot,
    MethodComparison,
    NextAction,
    OpenLot,
    OpenPosition,
    OpenPositionList,
    Sell,
    SellList,
    SettingFieldTruth,
    SourceRef,
    TaxYear,
    TaxYearList,
    TruthMeta,
    TruthReason,
)

FRONTEND_READY_HREFS = frozenset({"/", "/import", "/tax-years"})
WORKBOOK_BACKED_DOMAINS = (
    "locked_years",
    "frozen_inventory",
    "frozen_lot_matching",
    "frozen_snapshots",
    "filed_year_reconciliation",
)
_PLACEHOLDER_HREF_FALLBACKS = {
    "/audit": "/",
    "/fx": "/",
    "/open-positions": "/",
    "/sales-review": "/",
    "/settings": "/",
    "/years": "/tax-years",
}
POSITION_RECONCILIATION_TOLERANCE_DEFAULT = 1e-4
POSITION_RECONCILIATION_WARN_TOLERANCE_DEFAULT = 1e-2

ENGINE_DEFAULT_EXPORT_NAME = "stock_tax_export.xlsx"


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
    return ui_state.canonical_sell_id(raw_id)


def _check_level(severity: str) -> str:
    sev = str(severity or "").strip().upper()
    if sev == "ERROR":
        return "error"
    if sev == "WARN":
        return "warn"
    return "info"


def _frontend_ready_href(href: str) -> str:
    if href in FRONTEND_READY_HREFS:
        return href
    return _PLACEHOLDER_HREF_FALLBACKS.get(href, "/")


def _check_href(category: str) -> str:
    if "fx" in category:
        return _frontend_ready_href("/fx")
    if "method" in category or "filed" in category:
        return _frontend_ready_href("/years")
    if "remaining" in category or "position" in category:
        return _frontend_ready_href("/open-positions")
    if "import" in category:
        return _frontend_ready_href("/import")
    return _frontend_ready_href("/audit")


def _legacy_rows(legacy_user_state: dict[str, Any], sheet: str) -> list[dict[str, Any]]:
    rows = legacy_user_state.get(sheet) or []
    return [row for row in rows if isinstance(row, dict)]


def _legacy_has_year_row(legacy_user_state: dict[str, Any], sheet: str, year: int) -> bool:
    for row in _legacy_rows(legacy_user_state, sheet):
        try:
            if int(row.get("Tax year")) == year:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _legacy_has_method_row(
    legacy_user_state: dict[str, Any],
    year: int,
    instrument_id: str | None = None,
) -> bool:
    for row in _legacy_rows(legacy_user_state, "Method_Selection"):
        try:
            row_year = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        if row_year != year:
            continue
        if instrument_id is None or str(row.get("Instrument_ID") or "").strip() == instrument_id:
            return True
    return False


def _legacy_has_instrument_map_row(legacy_user_state: dict[str, Any], symbol: str) -> bool:
    return any(
        str(row.get("Yahoo Symbol") or "").strip() == symbol
        for row in _legacy_rows(legacy_user_state, "Instrument_Map")
    )


def _legacy_has_corporate_action_rows(legacy_user_state: dict[str, Any]) -> bool:
    for row in _legacy_rows(legacy_user_state, "Corporate_Actions"):
        if any(
            row.get(key) not in (None, "")
            for key in ("Date", "Instrument_ID", "Action type", "Notes", "Ratio old", "Ratio new")
        ):
            return True
    return False


def _legacy_daily_dates_for_year(legacy_user_state: dict[str, Any], year: int) -> set[str]:
    dates: set[str] = set()
    for row in _legacy_rows(legacy_user_state, "FX_Daily"):
        value = row.get("Date")
        resolved: date | None = None
        if isinstance(value, datetime):
            resolved = value.date()
        elif isinstance(value, date):
            resolved = value
        elif isinstance(value, str):
            try:
                resolved = date.fromisoformat(value.strip())
            except ValueError:
                resolved = None
        if resolved is not None and resolved.year == year:
            dates.add(resolved.isoformat())
    return dates


def _unique_sources(*sources: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for source in sources:
        if not source or source in seen:
            continue
        seen.add(source)
        ordered.append(source)
    return ordered


def _reason(code: str, message: str) -> TruthReason:
    return TruthReason(code=code, message=message)


def _reasons_from_checks(checks: list[Check]) -> list[TruthReason]:
    return [_reason(f"check_{check.id}", check.message) for check in checks]


def _remaining_workbook_backed_domains() -> list[str]:
    return list(WORKBOOK_BACKED_DOMAINS)


def _global_truth_status(unresolved_checks: list[Check]) -> str:
    if any(check.level == "error" for check in unresolved_checks):
        return "blocked"
    if _remaining_workbook_backed_domains():
        return "partial"
    if any(check.level == "warn" for check in unresolved_checks):
        return "needs_review"
    return "ready"


def _collection_truth(
    *,
    status: str,
    reasons: list[TruthReason],
    sources: list[str],
    items: list[Any],
    summary: str,
    empty_meaning: str | None = None,
) -> CollectionTruth:
    if empty_meaning is None:
        empty_meaning = "not_empty" if items else "no_data"
    return CollectionTruth(
        status=status,
        reasons=reasons,
        sources=sources,
        summary=summary,
        item_count=len(items),
        empty_meaning=empty_meaning,
    )


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


def _year_settings_source(project_state: Any, legacy_user_state: dict[str, Any], year: int) -> str:
    if year in project_state.year_settings:
        return "project_state"
    if _legacy_has_year_row(legacy_user_state, "Settings", year):
        return "workbook_fallback"
    return "generated_default"


def _method_source(
    project_state: Any,
    legacy_user_state: dict[str, Any],
    year: int,
) -> str:
    if policy.is_filed(year):
        return "static_config"
    if project_state.year_settings.get(year, {}).get("method") is not None:
        return "project_state"
    if project_state.method_selection.get(year):
        return "project_state"
    if _legacy_has_method_row(legacy_user_state, year):
        return "workbook_fallback"
    return "generated_default"


def _reconciliation_source(calc: workbook.CalculationResult, year: int) -> str:
    if not policy.is_filed(year):
        return "unavailable"
    if year in calc.filed_reconciliation:
        return "workbook_fallback"
    return "generated_default"


def _instrument_map_source(project_state: Any, legacy_user_state: dict[str, Any], symbol: str) -> str:
    if symbol in project_state.instrument_map:
        return "project_state"
    if _legacy_has_instrument_map_row(legacy_user_state, symbol):
        return "workbook_fallback"
    return "generated_default"


def _corporate_actions_source(project_state: Any, legacy_user_state: dict[str, Any]) -> str:
    if getattr(project_state, "corporate_actions", None):
        return "project_state"
    if _legacy_has_corporate_action_rows(legacy_user_state):
        return "workbook_fallback"
    return "workbook_fallback"


def _daily_rate_source(
    *,
    project_state: Any,
    legacy_user_state: dict[str, Any],
    calc: workbook.CalculationResult,
    year: int,
    required_dates: set[date],
) -> str:
    if not required_dates:
        return "unavailable"

    project_state_dates = {
        iso_date for iso_date in project_state.fx_daily.keys() if iso_date.startswith(f"{year:04d}-")
    }
    required_iso_dates = {value.isoformat() for value in required_dates}
    if required_iso_dates and required_iso_dates.issubset(project_state_dates):
        return "project_state"

    legacy_dates = _legacy_daily_dates_for_year(legacy_user_state, year)
    if required_iso_dates & legacy_dates:
        return "workbook_fallback"

    if any(value.year == year for value in calc.fx_daily):
        return "cnb_cache"

    return "unavailable"


def _build_import_summary(
    calc: workbook.CalculationResult,
    csv_dir: Path,
    unresolved_checks: list[Check],
) -> ImportSummary:
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

    if calc.calculation_blocked:
        truth_status = "partial"
        reasons = [_reason("calculation_blocked", "Import data loaded, but downstream calculation is blocked.")]
    elif total_warnings:
        truth_status = "needs_review"
        reasons = [_reason("import_warnings", "Some input files contain warnings and should be reviewed.")]
    else:
        truth_status = "ready"
        reasons = []
    if unresolved_checks and calc.calculation_blocked:
        reasons.extend(_reasons_from_checks([check for check in unresolved_checks if check.level == "error"]))

    return ImportSummary(
        folder=str(csv_dir),
        files=files,
        total_trade_rows=sum(f.trade_rows for f in files),
        total_ignored_rows=sum(f.ignored_rows for f in files),
        total_warnings=total_warnings,
        truth=TruthMeta(
            status=truth_status,
            reasons=reasons,
            sources=["calculated"],
            summary="Real CSV import summary from backend-owned normalization.",
        ),
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


def _year_default_method(settings_by_year: dict[int, dict[str, Any]], year: int) -> str:
    settings = settings_by_year.get(year, {})
    return policy.resolved_method_for(year, settings.get("method"))


def _effective_year_method(calc: workbook.CalculationResult, year: int) -> str:
    if policy.is_filed(year):
        return policy.filed_method(year) or "LIFO"
    explicit_default = calc.settings.get(year, {}).get("method")
    if explicit_default:
        return str(explicit_default)
    methods = _method_values_for_year(calc.method_selection, year, calc.instrument_ids)
    if not methods:
        return _year_default_method(calc.settings, year)
    if len(methods) == 1:
        return next(iter(methods))
    return "MIXED"


def _build_tax_years(
    calc: workbook.CalculationResult,
    state: ui_state.UIState,
    project_state: Any,
    legacy_user_state: dict[str, Any],
    unresolved_checks: list[Check],
) -> TaxYearList:
    if calc.calculation_blocked:
        error_checks = [check for check in unresolved_checks if check.level == "error"]
        return TaxYearList(
            items=[],
            truth=_collection_truth(
                status="blocked",
                reasons=[
                    _reason(
                        "calculation_blocked",
                        "Tax years are unavailable because calculation is blocked.",
                    ),
                    *_reasons_from_checks(error_checks),
                ],
                sources=["unavailable", "calculated"],
                items=[],
                summary="Empty tax-year list is blocked, not a genuine no-data result.",
                empty_meaning="blocked",
            ),
        )

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

        settings_source = _year_settings_source(project_state, legacy_user_state, year)
        method_source = _method_source(project_state, legacy_user_state, year)
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
                truth_status="ready",
                settings_source=settings_source,
                method_source=method_source,
                reconciliation_source=_reconciliation_source(calc, year),
            )
        )

    return TaxYearList(
        items=years,
        truth=_collection_truth(
            status="ready",
            reasons=[],
            sources=_unique_sources(
                "calculated",
                *(year.settings_source for year in years),
                *(year.method_source for year in years),
                *(year.reconciliation_source for year in years),
            ),
            items=years,
            summary="Tax-year response includes explicit provenance for policy and reconciliation fields.",
        ),
    )


def _build_sales(
    calc: workbook.CalculationResult,
    state: ui_state.UIState,
    project_state: Any,
    legacy_user_state: dict[str, Any],
    unresolved_checks: list[Check],
) -> SellList:
    if calc.calculation_blocked:
        error_checks = [check for check in unresolved_checks if check.level == "error"]
        return SellList(
            items=[],
            truth=_collection_truth(
                status="blocked",
                reasons=[
                    _reason(
                        "calculation_blocked",
                        "Sales evidence is unavailable because calculation is blocked.",
                    ),
                    *_reasons_from_checks(error_checks),
                ],
                sources=["unavailable", "calculated"],
                items=[],
                summary="Empty sales list is blocked, not a genuine no-sales result.",
                empty_meaning="blocked",
            ),
        )

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
        instrument_source = _instrument_map_source(project_state, legacy_user_state, tx.symbol)
        sell_truth = "needs_review" if unmatched_quantity > 1e-9 else "ready"
        sell_reasons = []
        if unmatched_quantity > 1e-9:
            sell_reasons.append(
                _reason(
                    "unmatched_quantity",
                    f"Sell {sell_id} still has unmatched quantity {unmatched_quantity:.6f}.",
                )
            )
        sells.append(
            Sell(
                id=sell_id,
                sell_id=sell_id,
                year=tx.trade_date.year,
                date=tx.trade_date,
                ticker=tx.symbol,
                instrument_id=tx.instrument_id,
                broker=tx.source_broker,
                quantity=float(tx.quantity),
                price_usd=float(tx.price_usd),
                proceeds_czk=float(sum(line.proceeds_czk for line in lines)),
                method=calc.method_selection.get(
                    (tx.trade_date.year, tx.instrument_id),
                    _year_default_method(calc.settings, tx.trade_date.year),
                ),
                matched_quantity=float(matched_quantity),
                unmatched_quantity=float(unmatched_quantity),
                classification=classification,
                review_status=review.review_status,
                truth_status=sell_truth,
                instrument_map_source=instrument_source,
                review_state_source="ui_state",
                source=SourceRef(file=tx.source_file, row=tx.source_row),
                note=review.note,
                total_gain_loss_czk=float(
                    sum(line.proceeds_czk - line.cost_basis_czk for line in lines)
                ),
                total_cost_basis_czk=float(sum(line.cost_basis_czk for line in lines)),
                matched_lots=matched_lots,
                truth=TruthMeta(
                    status=sell_truth,
                    reasons=sell_reasons,
                    sources=_unique_sources("calculated", instrument_source, "ui_state"),
                    summary="Sale detail is calculated evidence layered with UI review state.",
                ),
            )
        )

    response_status = "needs_review" if any(sell.truth_status != "ready" for sell in sells) else "ready"
    return SellList(
        items=sells,
        truth=_collection_truth(
            status=response_status,
            reasons=[],
            sources=_unique_sources(
                "calculated",
                *(sell.instrument_map_source for sell in sells),
                *(sell.review_state_source for sell in sells),
            ),
            items=sells,
            summary="Sales response is real calculation output with explicit instrument-map and UI-state provenance.",
        ),
    )


def _build_open_positions(
    calc: workbook.CalculationResult,
    project_state: Any,
    legacy_user_state: dict[str, Any],
    unresolved_checks: list[Check],
) -> OpenPositionList:
    if calc.calculation_blocked:
        error_checks = [check for check in unresolved_checks if check.level == "error"]
        return OpenPositionList(
            items=[],
            truth=_collection_truth(
                status="blocked",
                reasons=[
                    _reason(
                        "calculation_blocked",
                        "Open positions are unavailable because calculation is blocked.",
                    ),
                    *_reasons_from_checks(error_checks),
                ],
                sources=["unavailable", "calculated"],
                items=[],
                summary="Empty open-position list is blocked, not a genuine empty inventory result.",
                empty_meaning="blocked",
            ),
        )

    ok_tolerance = POSITION_RECONCILIATION_TOLERANCE_DEFAULT
    warn_tolerance = max(POSITION_RECONCILIATION_WARN_TOLERANCE_DEFAULT, ok_tolerance)

    rows = workbook.build_open_position_rows(
        calc.raw_rows,
        calc.instrument_map,
        calc.lots_final,
        ok_tolerance=ok_tolerance,
        warn_tolerance=warn_tolerance,
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
        ticker = ticker_by_inst.get(inst, inst)
        instrument_source = _instrument_map_source(project_state, legacy_user_state, ticker)
        status = str(row.get("Status") or "UNKNOWN").lower()
        reported_qty = (
            float(row["Reported qty"])
            if row.get("Reported qty") is not None
            else float(row["Yahoo qty"])
            if row.get("Yahoo qty") is not None
            else None
        )
        difference = float(row["Difference"]) if row.get("Difference") is not None else None
        source_status = str(row.get("Reported position source status") or "unknown").lower()
        source_reason = row.get("Reported position source reason")
        source_count = int(row.get("Reported position source count") or 0)
        source_type = str(row.get("Reported position source type") or "csv_position_row")
        source_rows = row.get("Reported position sources") or []
        snapshot_date = row.get("Reported position snapshot date")
        reason_code = None
        reason = None
        truth_status = "ready"
        if status == "unknown":
            truth_status = "unknown"
            if instrument_source == "generated_default":
                reason_code = "unknown_missing_mapping"
                reason = (
                    "Open position is unresolved because the instrument map is still a generated default "
                    "and Yahoo position data is missing."
                )
            else:
                reason_code = "unknown_missing_yahoo_position"
                reason = "Yahoo position rows are missing for this instrument."
        elif status == "ok":
            reason_code = "reconciled_within_tolerance"
            reason = (
                "Calculated and reported quantities reconcile within the configured tolerance "
                f"({ok_tolerance:.6g})."
            )
            if source_status in {"partial", "unknown"}:
                truth_status = "needs_review"
                reason_code = "reported_position_source_needs_review"
                reason = (
                    "Quantity matches, but reported-position provenance is not fully ready. "
                    + (str(source_reason) if source_reason else "")
                ).strip()
        elif status == "warn":
            truth_status = "needs_review"
            reason_code = "difference_above_tolerance"
            reason = (
                "Quantity difference is above tolerance but below material threshold: "
                f"|difference|={abs(difference or 0.0):.6g}, "
                f"tolerance={ok_tolerance:.6g}, material_threshold={warn_tolerance:.6g}."
            )
        elif status == "error":
            truth_status = "blocked"
            reason_code = "material_difference"
            reason = (
                "Material quantity mismatch between calculated and reported inventory: "
                f"|difference|={abs(difference or 0.0):.6g}, "
                f"material_threshold={warn_tolerance:.6g}."
            )
        else:
            truth_status = "unknown"
            reason_code = "unknown_status"
            reason = f"Unrecognized open-position status '{status}'."

        if source_status in {"partial", "unknown"} and status != "unknown":
            if not reason_code or reason_code == "reconciled_within_tolerance":
                reason_code = "reported_position_source_needs_review"
            if source_reason:
                reason = f"{reason} {source_reason}".strip() if reason else str(source_reason)

        positions.append(
            OpenPosition(
                ticker=ticker,
                instrument_id=inst,
                calculated_qty=float(row.get("Calculated qty") or 0.0),
                reported_qty=reported_qty,
                yahoo_qty=reported_qty,
                difference=difference,
                tolerance=ok_tolerance,
                status=status,
                lots=sorted(lots_by_inst.get(inst, []), key=lambda lot: (lot.buy_date, lot.lot_id)),
                truth_status=truth_status,
                status_reason_code=reason_code,
                status_reason=reason,
                instrument_map_source=instrument_source,
                inventory_source="calculated",
                reported_position_source_file=row.get("Reported position source file"),
                reported_position_source_row=row.get("Reported position source row"),
                reported_position_broker=row.get("Reported position broker"),
                reported_position_account=row.get("Reported position account"),
                reported_position_snapshot_date=snapshot_date,
                reported_position_source_type=source_type,
                reported_position_source_status=(
                    source_status if source_status in {"ready", "partial", "unknown"} else "unknown"
                ),
                reported_position_source_reason=(str(source_reason) if source_reason else None),
                reported_position_source_count=source_count,
                reported_position_sources=source_rows,
            )
        )

    response_status = (
        "blocked"
        if any(position.truth_status == "blocked" for position in positions)
        else "partial"
        if any(position.truth_status == "unknown" for position in positions)
        else "needs_review"
        if any(position.truth_status == "needs_review" for position in positions)
        else "ready"
    )
    reasons = []
    if any(position.truth_status == "blocked" for position in positions):
        reasons.append(
            _reason(
                "material_open_position_differences",
                "One or more open positions have material calculated-vs-reported quantity differences.",
            )
        )
    if any(position.truth_status == "unknown" for position in positions):
        reasons.append(
            _reason(
                "unknown_positions_present",
                "Some open positions remain unknown and must not be shown as fully resolved.",
            )
        )
    if any(position.truth_status == "needs_review" for position in positions):
        reasons.append(
            _reason(
                "position_differences_above_tolerance",
                "Some open-position differences exceed tolerance and require operator review.",
            )
        )
    if any(position.reported_position_source_status in {"partial", "unknown"} for position in positions):
        reasons.append(
            _reason(
                "reported_position_provenance_needs_review",
                "Reported-position provenance is partial/unknown for one or more instruments.",
            )
        )
    return OpenPositionList(
        items=positions,
        truth=_collection_truth(
            status=response_status,
            reasons=reasons,
            sources=_unique_sources(
                "calculated",
                *(position.instrument_map_source for position in positions),
            ),
            items=positions,
            summary=(
                "Open positions reconcile calculated residual lots against reported broker/Yahoo positions "
                "using explicit tolerance-based status and reason codes."
            ),
        ),
    )


def _open_position_discrepancy_checks(open_positions: OpenPositionList) -> list[Check]:
    checks: list[Check] = []
    for index, position in enumerate(open_positions.items, start=1):
        if position.status == "ok" and position.reported_position_source_status == "ready":
            continue
        level = "error" if position.status == "error" else "warn"
        reason = position.status_reason or "Open-position reconciliation issue."
        if position.status == "ok" and position.reported_position_source_status in {"partial", "unknown"}:
            reason = "Reported-position provenance: " + (
                position.reported_position_source_reason
                or "Reported-position provenance is not fully ready for reconciliation evidence."
            )
        checks.append(
            Check(
                id=f"open-position-{index}",
                level=level,
                message=f"Open position {position.ticker} ({position.instrument_id}): {reason}",
                href=_check_href("remaining_position_mismatch"),
            )
        )
    return checks


def _build_fx_years(
    calc: workbook.CalculationResult,
    project_state: Any,
    legacy_user_state: dict[str, Any],
    unresolved_checks: list[Check],
) -> FxYearList:
    tx_dates_by_year: dict[int, set[date]] = defaultdict(set)
    for tx in calc.txs:
        tx_dates_by_year[tx.trade_date.year].add(tx.trade_date)

    years: list[FxYear] = []
    for year in sorted(calc.years):
        method = str(calc.settings.get(year, {}).get("fx_method") or workbook.DEFAULT_FX_METHOD)
        required_dates = tx_dates_by_year.get(year, set())
        missing_dates = sorted(
            value for value in required_dates
            if calc.fx.inspect_date(value)[0] is None
        )
        source_label = calc.fx_yearly_sources.get(year, "default")
        if method == "FX_DAILY_CNB":
            rate_source = _daily_rate_source(
                project_state=project_state,
                legacy_user_state=legacy_user_state,
                calc=calc,
                year=year,
                required_dates=required_dates,
            )
        elif year in project_state.fx_yearly:
            rate_source = "project_state"
        elif _legacy_has_year_row(legacy_user_state, "FX_Yearly", year):
            rate_source = "workbook_fallback"
        elif calc.fx_yearly.get(year) is not None:
            rate_source = "static_config"
        else:
            rate_source = "unavailable"

        truth_status = "ready"
        status_reason = None
        if missing_dates:
            truth_status = "blocked" if calc.calculation_blocked else "needs_review"
            status_reason = (
                f"{len(missing_dates)} required FX date(s) are still missing for {year}."
            )

        years.append(
            FxYear(
                year=year,
                method=method,
                unified_rate=calc.fx_yearly.get(year),
                daily_cached=sum(1 for value in calc.fx_daily if value.year == year),
                daily_expected=len(required_dates) if method == "FX_DAILY_CNB" else 0,
                missing_dates=missing_dates if method == "FX_DAILY_CNB" else [],
                source_label=source_label,
                source_url=None,
                verified_at=None,
                manual_override=bool(
                    calc.fx_yearly_manual.get(year, "manual" in source_label.lower())
                ),
                locked=policy.is_locked(year) or bool(calc.locked_years.get(year)),
                truth_status=truth_status,
                rate_source=rate_source,
                status_reason=status_reason,
            )
        )

    status = (
        "blocked"
        if any(year.truth_status == "blocked" for year in years)
        else "needs_review"
        if any(year.truth_status == "needs_review" for year in years)
        else "ready"
    )
    reasons = []
    if calc.calculation_blocked:
        reasons.append(_reason("calculation_blocked", "FX truth is explicit: required rates are still missing."))
        reasons.extend(_reasons_from_checks([check for check in unresolved_checks if check.level == "error"]))
    return FxYearList(
        items=years,
        truth=_collection_truth(
            status=status,
            reasons=reasons,
            sources=_unique_sources("calculated", *(year.rate_source for year in years)),
            items=years,
            summary="FX response discloses whether effective rates came from ProjectState, workbook fallback, cache, or static defaults.",
        ),
    )


def _build_settings(
    project_dir: Path,
    csv_dir: Path,
    output_path: Path,
    project_state: Any,
    legacy_user_state: dict[str, Any],
) -> AppSettings:
    field_names = [
        "project_folder",
        "csv_folder",
        "output_path",
        "cache_folder",
        "default_tax_rate",
        "default_fx_method",
        "default_100k",
        "unmatched_qty_tolerance",
        "position_reconciliation_tolerance",
        "backup_on_recalc",
        "require_confirm_unlock",
        "keep_n_snapshots",
        "excel_validation",
    ]
    field_meta = {
        name: SettingFieldTruth(
            editability="display_only",
            source="static_config",
            status="not_implemented",
            reason="GET /api/settings is truthful display-only metadata. PATCH /api/settings is not implemented yet.",
        )
        for name in field_names
    }
    return AppSettings(
        project_folder=str(project_dir),
        csv_folder=str(csv_dir),
        output_path=str(output_path),
        cache_folder=str(output_path.parent),
        default_tax_rate=workbook.DEFAULT_TAX_RATE,
        default_fx_method=workbook.DEFAULT_FX_METHOD,
        default_100k=workbook.DEFAULT_APPLY_100K,
        unmatched_qty_tolerance=1e-3,
        position_reconciliation_tolerance=POSITION_RECONCILIATION_TOLERANCE_DEFAULT,
        backup_on_recalc=False,
        require_confirm_unlock=True,
        keep_n_snapshots=1,
        excel_validation="strict",
        truth_status="partial",
        status_reasons=[
            _reason(
                "settings_display_only",
                "Settings are exposed for truthful display only. Editing is not implemented in this slice.",
            )
        ],
        field_meta=field_meta,
        domain_sources={
            "year_settings": "project_state",
            "method_selection": "project_state",
            "fx_yearly": "project_state",
            "fx_daily": "project_state",
            "instrument_map": "project_state",
            "review_state": "ui_state",
            "corporate_actions": _corporate_actions_source(project_state, legacy_user_state),
            "locked_years": "workbook_fallback",
            "frozen_inventory": "workbook_fallback",
            "frozen_snapshots": "workbook_fallback",
            "filed_year_reconciliation": "workbook_fallback",
        },
    )


def _build_audit_summary(
    calc: workbook.CalculationResult,
    tax_years: TaxYearList,
    open_positions: OpenPositionList,
) -> AuditSummary:
    workbook_backed_domains = _remaining_workbook_backed_domains()
    reasons = [
        _reason(
            "audit_summary_only",
            "Audit is summary-only in this slice and must not be treated as final export readiness.",
        )
    ]
    if calc.calculation_blocked:
        reasons.insert(
            0,
            _reason(
                "calculation_blocked",
                "Audit readiness is blocked because required calculation checks are unresolved.",
            ),
        )
    if workbook_backed_domains:
        reasons.append(
            _reason(
                "workbook_backed_domains",
                "Audit still depends on workbook-backed domains: " + ", ".join(workbook_backed_domains) + ".",
            )
        )
    if open_positions.truth.status != "ready":
        reasons.append(
            _reason(
                f"open_positions_{open_positions.truth.status}",
                "Open-position reconciliation is not fully ready; audit readiness is reduced until discrepancies are resolved.",
            )
        )
        for row in open_positions.items:
            if row.status == "ok" and row.reported_position_source_status == "ready":
                continue
            row_kind = (
                "provenance"
                if row.status == "ok" and row.reported_position_source_status in {"partial", "unknown"}
                else row.status
            )
            reasons.append(
                _reason(
                    f"open_position_{row_kind}_{row.instrument_id}",
                    f"{row.ticker} ({row.instrument_id}): {row.status_reason or 'open-position issue.'}",
                )
            )

    corporate_issues = [
        row
        for row in calc.problems
        if str(row.get("check") or "").startswith("corporate_action_")
    ]
    corporate_error_count = sum(
        1 for row in corporate_issues if str(row.get("severity") or "").upper() == "ERROR"
    )
    corporate_warn_count = sum(
        1 for row in corporate_issues if str(row.get("severity") or "").upper() == "WARN"
    )
    if calc.corporate_actions:
        reasons.append(
            _reason(
                "corporate_actions_present",
                f"Effective corporate actions in scope: {len(calc.corporate_actions)}.",
            )
        )
    if corporate_issues:
        reasons.append(
            _reason(
                "corporate_action_checks",
                (
                    "Corporate action checks reported "
                    f"{corporate_error_count} error(s) and {corporate_warn_count} warning(s)."
                ),
            )
        )

    truth_status = "partial"
    if calc.calculation_blocked or open_positions.truth.status == "blocked":
        truth_status = "blocked"
    return AuditSummary(
        year_rows=tax_years.items,
        trace_counts={
            "csv_files": len(calc.inputs),
            "raw_rows": len(calc.raw_rows),
            "transactions": len(calc.txs),
            "ignored_rows": len(calc.ignored),
            "match_lines": len(calc.match_lines),
            "open_lots": sum(1 for lot in calc.lots_final if lot.quantity_remaining > 1e-9),
        },
        locked_snapshots=sorted(calc.frozen_snapshots.keys()),
        truth_status=truth_status,
        summary_only=True,
        status_reasons=reasons,
        workbook_backed_domains=workbook_backed_domains,
    )


def _build_status(
    project_dir: Path,
    csv_dir: Path,
    output_path: Path,
    unresolved_checks: list[Check],
    open_positions: OpenPositionList,
) -> AppStatus:
    open_position_checks = _open_position_discrepancy_checks(open_positions)
    effective_checks = [*unresolved_checks, *open_position_checks]

    if any(check.level == "error" for check in effective_checks):
        global_status = "blocked"
    elif any(check.level == "warn" for check in effective_checks):
        global_status = "needs_review"
    else:
        global_status = "ready"
    next_action = None
    if effective_checks:
        first = effective_checks[0]
        next_action = NextAction(
            label="Review checks",
            href=_frontend_ready_href(first.href or "/"),
        )

    workbook_backed_domains = _remaining_workbook_backed_domains()
    status_reasons = _reasons_from_checks(effective_checks)
    if open_position_checks:
        status_reasons.append(
            _reason(
                "open_position_discrepancies",
                "Open-position reconciliation surfaced unresolved discrepancies in calculated vs reported inventory.",
            )
        )
    if workbook_backed_domains:
        status_reasons.append(
            _reason(
                "workbook_backed_domains",
                "Remaining workbook-backed domains: " + ", ".join(workbook_backed_domains) + ".",
            )
        )
    return AppStatus(
        project_path=str(project_dir),
        csv_folder=str(csv_dir),
        output_path=str(output_path),
        last_calculated_at=datetime.now(timezone.utc),
        global_status=global_status,
        truth_status=_global_truth_status(effective_checks),
        next_action=next_action,
        unresolved_checks=effective_checks,
        status_reasons=status_reasons,
        workbook_backed_domains=workbook_backed_domains,
    )


def run(
    project_dir: Path | str,
    csv_dir: Path | str | None = None,
    output_path: Path | str | None = None,
    write_workbook: bool = True,
) -> EngineResult:
    project_path = Path(project_dir).resolve()
    csv_path = _resolve_path(project_path, csv_dir, ".csv")
    output = _resolve_path(project_path, output_path, ENGINE_DEFAULT_EXPORT_NAME)

    inputs = _discover_csv_inputs(csv_path)
    calc = workbook.calculate_workbook_data(
        inputs=inputs,
        out_path=output,
        fetch_missing_fx=True,
    )
    if write_workbook and not calc.calculation_blocked:
        workbook.write_calculation_result(calc, backup_existing=False)

    state = ui_state.load(output)
    project_state = project_store.load_project_state(project_path)
    legacy_user_state = workbook.load_existing_user_state(output)
    checks = _build_checks(calc)
    unresolved_checks = [check for check in checks if check.level != "info"]

    tax_years = _build_tax_years(calc, state, project_state, legacy_user_state, unresolved_checks)
    sales = _build_sales(calc, state, project_state, legacy_user_state, unresolved_checks)
    open_positions = _build_open_positions(calc, project_state, legacy_user_state, unresolved_checks)
    fx_years = _build_fx_years(calc, project_state, legacy_user_state, unresolved_checks)
    settings = _build_settings(project_path, csv_path, output, project_state, legacy_user_state)
    audit_summary = _build_audit_summary(calc, tax_years, open_positions)
    app_status = _build_status(project_path, csv_path, output, unresolved_checks, open_positions)

    return EngineResult(
        app_status=app_status,
        import_summary=_build_import_summary(calc, csv_path, unresolved_checks),
        tax_years=tax_years,
        unresolved_checks=unresolved_checks,
        sales=sales,
        open_positions=open_positions,
        fx_years=fx_years,
        audit_summary=audit_summary,
        settings=settings,
    )

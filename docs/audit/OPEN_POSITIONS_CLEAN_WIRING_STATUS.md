# OPEN POSITIONS CLEAN WIRING STATUS

Date: 2026-04-25
Scope: Wiring-only slice to make open-position logic single-owned by `stock_tax_app.engine.open_positions`.

## Old Split Ownership

Open-position calculation and reported-position provenance logic were split and duplicated across multiple modules:

- `stock_tax_app/engine/open_positions.py`
  - Contained extracted open-position logic, but was not the sole runtime owner.
- `stock_tax_app/engine/workbook_export.py`
  - Duplicated open-position helper logic (`build_open_position_rows`, `extract_position_rows`, `extract_position_rows_with_provenance`).
- `build_stock_tax_workbook.py`
  - `build_open_position_rows` compatibility wrapper delegated to `workbook_export.py` instead of directly to `open_positions.py`.
  - Compatibility wrappers for `extract_position_rows` and `extract_position_rows_with_provenance` were missing.

## New Owner

Single owner of open-position and reported-position provenance logic is now:

- `stock_tax_app/engine/open_positions.py`

Owned functions:

- `extract_position_rows`
- `extract_position_rows_with_provenance`
- `build_open_position_rows`
- Reported-position provenance derivation
- Status / tolerance / source-status behavior

## Functions Wired

### build_stock_tax_workbook.py

Kept compatibility surface and wired thin wrappers directly to `open_positions.py`:

- Restored `extract_position_rows_with_provenance(raw_rows, instrument_map)` wrapper.
- Restored `extract_position_rows(raw_rows, instrument_map)` wrapper.
- Rewired `build_open_position_rows(raw_rows, instrument_map, lots, *, ok_tolerance, warn_tolerance)` wrapper.

All wrappers delegate to `stock_tax_app.engine.open_positions` and inject:

- `safe_float`
- `parse_trade_date`

Public wrapper names and signatures remain compatible.

### stock_tax_app/engine/workbook_export.py

Removed duplicated logic implementations and now uses imported canonical owner function:

- Imports `build_open_position_rows` from `stock_tax_app.engine.open_positions`.
- `_write_open_position_check(...)` still calls `build_open_position_rows(...)` and writes the same sheet columns/layout.

Removed duplicated local definitions:

- `build_open_position_rows`
- `extract_position_rows`
- `extract_position_rows_with_provenance`

## Duplicated Logic Removed From workbook_export.py

Yes. Duplicate open-position/provenance calculation code was deleted from `workbook_export.py`.
Workbook export module now performs sheet writing and consumes canonical open-position rows.

## Behavior Preservation Notes

Validated preserved behavior for:

- API shape and semantics for `/api/open-positions`
- `reported_position_source_*` fields
- Unknown reported positions remain unknown (not OK)
- Provenance partial/weak signals still downgrade readiness
- Tolerance/status semantics (OK/WARN/ERROR/UNKNOWN)
- Open_Position_Check workbook sheet columns and layout
- Existing workbook verification contract

No tax formulas, frontend, project-state schema, soft-lock policy, or unrelated extraction boundaries were changed.

## Tests Run

Focused tests:

- `py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_exact_match_is_ok_and_ready` -> PASS
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_warn_difference_creates_needs_review_and_status_check` -> PASS
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_material_difference_blocks_collection_and_surfaces_audit_reason` -> PASS
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_missing_reported_position_is_unknown_not_ok` -> PASS
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_provenance_missing_snapshot_date_is_honest` -> PASS
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_multiple_reported_rows_expose_ambiguity_and_source_count` -> PASS
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_status_and_audit_include_provenance_checks_for_quantity_match` -> PASS

Full validation sequence:

- `py -3 -m pytest -q test_stock_tax_app_api.py` -> PASS (61 passed)
- `py -3 -m pytest -q test_project_state_store.py` -> PASS (22 passed)
- `py -3 -m pytest -q` -> PASS (85 passed)
- `py -3 test_locked_year_roundtrip.py` -> PASS
- `py -3 verify_workbook.py stock_tax_system.xlsx` -> PASS

## Pass/Fail Result

PASS: Clean wiring slice completed with behavior preserved and validation green.

## Remaining Extraction Risks

- Monolith compatibility wrappers in `build_stock_tax_workbook.py` still exist by design. They are now thin and direct, but still represent transitional coupling.
- `workbook_export.py` still imports and calls many non-open-position helpers; broader extraction boundaries remain intentionally unchanged in this slice.
- `checks.py` and `fx.py` extraction remains partial and out of scope for this change.

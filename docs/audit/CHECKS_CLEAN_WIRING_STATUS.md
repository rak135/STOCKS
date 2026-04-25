# Checks Clean Wiring Status

## Old split ownership

- `build_stock_tax_workbook.py::build_check_rows(...)` contained the full check-row construction logic.
- `stock_tax_app/engine/checks.py::build_check_rows(...)` also contained the same logic and was already used by `stock_tax_app/engine/workbook_export.py`.
- Result: workbook export used engine ownership, while API/core compatibility paths still depended on the monolith copy.

## New owner

- `stock_tax_app/engine/checks.py::build_check_rows(...)` is now the single owner of check-row construction.
- `build_stock_tax_workbook.py::build_check_rows(...)` is now a thin compatibility wrapper.

## Functions and wrappers changed

- Changed `build_stock_tax_workbook.py::build_check_rows(...)`.
- Kept the existing public signature in `build_stock_tax_workbook.py`.
- Wrapper now delegates to `stock_tax_app.engine.checks.build_check_rows(...)` and injects `SUPPORTED_METHODS`.
- `stock_tax_app/engine/workbook_export.py` continues using `stock_tax_app.engine.checks.build_check_rows(...)` directly.

## Duplicated logic removed

- raw `problems` to check-row shaping
- raw `sim_warnings` to check-row shaping
- missing yearly FX checks
- missing daily FX checks
- trusted FX missing-data checks
- locked-year snapshot presence checks
- invalid method checks
- split audit hint checks
- negative remaining lot checks
- `all_clear` fallback row

## Behavior preservation notes

- `stock_tax_app/engine/checks.py` matched the prior monolith implementation for the owned logic before this change.
- Check ordering remains unchanged because the wrapper forwards arguments directly to the same extracted implementation.
- Severity, category, detail text, workbook `Checks` sheet layout, and compatibility wrapper signature were preserved.
- No changes were made to `core.py` href mapping, FX behavior, matching behavior, workbook layout, `ProjectState` schema, API contracts, or frontend files.

## Call sites

- `stock_tax_app/engine/workbook_export.py::_write_checks(...)` calls `stock_tax_app.engine.checks.build_check_rows(...)` directly.
- `stock_tax_app/engine/core.py::_build_checks(...)` calls `build_stock_tax_workbook.build_check_rows(...)`, which now delegates to the engine owner.
- `test_stock_tax_app_api.py::_build_check_rows_for_project(...)` calls `build_stock_tax_workbook.build_check_rows(...)`, which now delegates to the engine owner.

## Tests run

- `py -3 -m pytest -q test_stock_tax_app_api.py::test_invalid_corporate_actions_surface_in_status_and_audit`
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_warn_difference_creates_needs_review_and_status_check`
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_material_difference_blocks_collection_and_surfaces_audit_reason`
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_status_and_audit_include_provenance_checks_for_quantity_match`
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_locked_year_snapshot_rebuild_required_when_earlier_year_locked_under_later_snapshot`
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_stale_frozen_snapshot_manifest_persists_rebuild_required_check`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
- `py -3 -m pytest -q test_project_state_store.py`
- `py -3 -m pytest -q`
- `py -3 test_locked_year_roundtrip.py`
- `py -3 verify_workbook.py stock_tax_system.xlsx`

## Results

- Focused API tests: pass
- Locked/snapshot targeted tests: pass
- `test_stock_tax_app_api.py`: `61 passed`
- `test_project_state_store.py`: `22 passed`
- Full pytest suite: `85 passed`
- `test_locked_year_roundtrip.py`: pass
- `verify_workbook.py stock_tax_system.xlsx`: validation passed

## Remaining extraction risks

- `build_stock_tax_workbook.py` still exposes the compatibility wrapper, so stale callers can still appear unless future slices migrate them intentionally.
- The extracted owner still accepts several legacy parameters that are currently unused; signature cleanup should be deferred until all callers are explicitly audited.
- Any future changes to check construction must update `stock_tax_app/engine/checks.py` only; reintroducing local shaping in the monolith would recreate split ownership.

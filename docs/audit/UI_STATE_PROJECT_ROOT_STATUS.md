# UI State Project Root Status

## Scope

This slice decouples backend/frontend UI state persistence from workbook output path selection.

## Old Coupling to output_path

Before this change, UI state persistence used workbook-relative path inference:

- `.ui_state.json` location was derived from `output_path.parent`.
- Changing `output_path` could move effective UI state location.
- If output moved into a subdirectory (for example `exports/stock_tax_export.xlsx`), UI state sidecar moved there too.

## New Project-Root Ownership

UI state now has explicit project-root ownership:

- `ui_state_path(project_dir)` resolves to `project_dir / ".ui_state.json"`.
- Backend/API review state load/save use project directory, not workbook parent.
- Engine runtime load path is project-root and independent from export path.
- Workbook path is now only a compatibility input for legacy sidecar adoption.

## Migration and Fallback Rule

Migration behavior is now:

- If project-root `.ui_state.json` exists, it is canonical and wins.
- If project-root `.ui_state.json` is missing and legacy sidecar exists next to workbook path, legacy sidecar is adopted into project root.
- If both exist, legacy sidecar is ignored for canonical load.
- Project-root state is never silently overwritten by legacy sidecar.

Workbook `Review_State` remains a legacy fallback/export compatibility domain only.

## Tests Added/Updated

Updated or added coverage in `test_stock_tax_app_api.py`:

- `test_patch_sale_review_updates_ui_state_only`
  - Asserts review PATCH persists UI state and still does not write workbook.
- `test_ui_state_stored_at_project_root_when_output_path_is_nested`
  - Asserts `.ui_state.json` stays in project root even with nested export path.
- `test_ui_state_persists_when_output_path_changes`
  - Asserts changing `output_path` does not move or lose review state.
- `test_legacy_sidecar_ui_state_adopted_only_when_root_missing`
  - Asserts legacy sidecar is adopted only when root state is absent.
- `test_root_ui_state_wins_over_legacy_sidecar`
  - Asserts root state wins when both root and legacy sidecar exist.
- Existing review persistence tests remain green, including recalc and runtime reload survival.

## Commands Run

- `py -3 -m pytest -q test_stock_tax_app_api.py`
  - Result: 67 passed
- `py -3 -m pytest -q test_project_state_store.py`
  - Result: 22 passed
- `py -3 -m pytest -q test_root_excel_absent.py`
  - Result: 4 passed
- `py -3 -m pytest -q`
  - Result: 95 passed
- `py -3 test_locked_year_roundtrip.py`
  - Result: PASS (3-pass flow completed)

## Remaining Excel/output_path Coupling

This slice intentionally leaves workbook fallback/export domains unchanged:

- Workbook `Review_State` fallback read path remains tied to workbook path when workbook exists.
- Instrument map fallback, FX fallback, method selection fallback, locked/frozen/filed workbook-backed domains remain workbook-path based.
- Workbook export remains optional and explicit (`write_workbook=True` paths).

These are separate migration slices and were not changed here.

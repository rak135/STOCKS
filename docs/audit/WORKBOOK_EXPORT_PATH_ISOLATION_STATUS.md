# Workbook Export Path Isolation Status

## Scope

This slice moves the default workbook export path into an explicit export-only subdirectory while keeping runtime/app state ownership unchanged.

## Old Default Path

- Backend default output path: `project / "stock_tax_export.xlsx"`
- Engine default fallback output path: `project / ENGINE_DEFAULT_EXPORT_NAME`

This made generated workbook export files appear at project root by default.

## New Export-Only Default Path

- Backend default output path: `project / "exports" / "stock_tax_export.xlsx"`
- Engine default fallback output path: `project / "exports" / ENGINE_DEFAULT_EXPORT_NAME`
- `ENGINE_DEFAULT_EXPORT_NAME` remains `"stock_tax_export.xlsx"`

This makes workbook writes clearly export artifacts.

## Proof: Normal Runtime Does Not Create Exports

Validated by tests:

- `test_root_excel_absent.py`
  - `GET /api/status`, `GET /api/years`, `GET /api/sales` do not create:
    - `stock_tax_system.xlsx`
    - `exports/stock_tax_export.xlsx`
    - `exports/` directory
  - `POST /api/recalculate` still does not create workbook or `exports/`.
- `test_stock_tax_app_api.py::test_api_runs_without_root_workbook_and_only_exports_explicitly`
  - Asserts runtime default `output_path == project / "exports" / "stock_tax_export.xlsx"`
  - Asserts no export file or export directory exists after normal API and recalculate calls.

## Proof: Explicit Export Writes Under exports/

- `runtime.calculate(write_workbook=True)` creates `exports/` and writes `exports/stock_tax_export.xlsx`.
- Verified in `test_stock_tax_app_api.py::test_api_runs_without_root_workbook_and_only_exports_explicitly`.

## UI State Ownership

- `.ui_state.json` remains project-root owned.
- UI state is still independent of `output_path`.
- Existing nested-output-path tests remain green and continue asserting root ownership.

## Docs/Samples Updated

- `docs/api_samples/status.json`
  - `output_path` now uses `...\\exports\\stock_tax_export.xlsx`.
- `docs/audit/ROOT_EXCEL_REMOVAL_STATUS.md`
  - Updated default path references to `project / "exports" / "stock_tax_export.xlsx"`.

## Tests Run

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

## Remaining Workbook Fallback/Export Dependencies

Intentionally unchanged in this slice:

- Workbook export code paths remain available (`write_workbook=True`, CLI export flow).
- Workbook fallback domains remain in place (review fallback, instrument map fallback, FX fallback, method selection fallback, locked/frozen/filed workbook-backed domains).
- No migration of workbook fallback domains was performed.

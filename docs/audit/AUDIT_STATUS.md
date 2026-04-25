# Audit Status

- Timestamp: `2026-04-24T22:43:15.9093879+02:00`
- Repository root: `C:\DATA\PROJECTS\STOCKS`
- Auditor stance: code/import/runtime truth over README/spec claims

## Commands Run

- `Get-ChildItem -Force`
- `rg --files`
- `git status --short`
- `Get-Content run_dev.ps1`
- `Get-Content stock_tax_app/backend/main.py`
- `Get-Content stock_tax_app/backend/runtime.py`
- `Get-Content stock_tax_app/backend/routes/*.py`
- `Get-Content stock_tax_app/engine/*.py`
- `Get-Content ui/frontend/package.json`
- `Get-Content ui/frontend/src/**/*.ts*`
- `Get-Content README.md`
- `Get-Content README_OPERATOR.md`
- `Get-Content IMPLEMENTATION_NOTES.md`
- `Get-Content docs/API_CONTRACT.md`
- `Get-Content ui/DESIGN.md`
- `Get-Content test_stock_tax_app_api.py`
- `Get-Content test_min_gain_optimality.py`
- `Get-Content test_locked_year_roundtrip.py`
- `Get-Content verify_workbook.py`
- `rg -n ...` scans for entrypoints, imports, routes, Excel usage, placeholder text, generated artifacts, and doc references
- `py -3 -m pytest -q`
- `py -3 -` probes using `FastAPI TestClient` for route inventory, live response shape, runtime counts, and OpenAPI comparison
- `npm run build` in `ui/frontend`
- `Get-Date -Format o`

## Succeeded

- Python test suite: `7 passed in 6.70s`
- Backend route/OpenAPI smoke:
  - Real API routes found: `/api/status`, `/api/import`, `/api/years`, `/api/sales`, `/api/sales/{sell_id}`, `/api/sales/{sell_id}/review`, `/api/open-positions`, `/api/fx`, `/api/audit`, `/api/settings`, `/api/recalculate`
  - `docs/openapi.json` exactly matches `create_app().openapi()`
- Live backend data probe against repo root:
  - `global_status = needs_review`
  - `unresolved_checks = 1`
  - `csv_files = 5`
  - `raw_rows = 214`
  - `transactions = 190`
  - `ignored_rows = 24`
  - `match_lines = 57`
  - `open_lots = 122`
- Frontend production build: passed via `npm run build`

## Failed Or Partially Failed

- `python -` was not available on PATH in this environment; `py -3 -` worked instead.
- Two early `rg` commands using Windows-invalid wildcard arguments (`test_*.py`, `*.py`, `*.md`) returned OS error `123`. I reran those scans with valid paths.
- `PATCH /api/years/2025` returned `501 {"detail":"Year editing is not implemented yet."}`. This is an application gap, not an environment failure.

## Artifacts Created During Validation

- Temporary frontend build output under `ui/frontend/dist/`
- Temporary `.ui_state.json` created by a sale-review PATCH probe

Both were deleted after verification. No tracked files were modified before the audit docs were written.

## Could Not Be Fully Verified

- Manual Excel desktop behavior with the workbook open in Microsoft Excel
- Any Tauri/Desktop shell behavior described in `ui/DESIGN.md` because no Tauri project exists in this repo
- Whether `docs/api_samples/*.json` are consumed by anything outside this repository
- Whether `temp/stock_tax_system.xlsx` is intentionally kept by the user as a scratch artifact; code inside the repo does not reference it

## Important Runtime Truth Captured

- The backend is operational, but the engine still depends on workbook-era state loading from `stock_tax_system.xlsx`.
- The frontend shell builds, but only three screens use live API data.
- Excel is not parsed by the frontend, but Excel is still part of backend calculation/persistence truth.

# File Inventory

Classification values used below:

- `LIVE_PRODUCT`
- `LIVE_TEST_ONLY`
- `LIVE_DEV_TOOL`
- `LEGACY_EXCEL_CORE`
- `LEGACY_EXPORT_ONLY`
- `DEAD_CANDIDATE`
- `DUPLICATE_LOGIC`
- `GENERATED_ARTIFACT`
- `UNKNOWN`

## Core Python

| Path | Classification | Evidence |
|---|---|---|
| `build_stock_tax_workbook.py` | `LEGACY_EXCEL_CORE` | Real calculation owner and workbook persistence owner. Reads workbook user state (`15-18`, `520-534`), calculates all tax data (`1924-2068`), writes workbook (`2071-3535`), and is still imported by `stock_tax_app.engine.core` (`stock_tax_app/engine/core.py:9,489-496`). |
| `stock_tax_app/engine/core.py` | `LIVE_PRODUCT` | Live API adapter. Every backend read/write route eventually uses `run()` (`479-519`). It is product-critical, but it is only a transformation layer over `build_stock_tax_workbook`. |
| `stock_tax_app/engine/models.py` | `LIVE_PRODUCT` | FastAPI response schemas used by every route. Real contract source for backend serialization. |
| `stock_tax_app/engine/policy.py` | `DUPLICATE_LOGIC` | Used live by `/api/years` and engine model shaping, but duplicates filed/locked/default-year policy already present in `build_stock_tax_workbook.py` (`FILED_YEARS`, `YEAR_DEFAULT_METHODS`). |
| `stock_tax_app/engine/ui_state.py` | `LIVE_PRODUCT` | Live UI-only persistence for sale review and reconciliation notes. Used by backend runtime and engine shaping (`backend/runtime.py:44-47`, `engine/core.py:498-503`). |
| `stock_tax_app/backend/main.py` | `LIVE_PRODUCT` | Real FastAPI startup path and route registration (`13-56`). |
| `stock_tax_app/backend/runtime.py` | `LIVE_PRODUCT` | Real backend runtime cache/mutation layer. Holds last engine result and sale-review patch flow (`9-47`). |
| `stock_tax_app/backend/routes/status.py` | `LIVE_PRODUCT` | Real route returning live engine data. Frontend uses it. |
| `stock_tax_app/backend/routes/import_summary.py` | `LIVE_PRODUCT` | Real route returning live engine data. Frontend uses it. |
| `stock_tax_app/backend/routes/years.py` | `LIVE_PRODUCT` | Real route for reads; partial route for edits. `GET` is live, `PATCH` only guards locked years then raises `501`. |
| `stock_tax_app/backend/routes/sales.py` | `LIVE_PRODUCT` | Real sales list/detail/review endpoints. Backend works; frontend does not use them yet. |
| `stock_tax_app/backend/routes/positions.py` | `LIVE_PRODUCT` | Real endpoint backed by engine data. Frontend does not use it yet. |
| `stock_tax_app/backend/routes/fx.py` | `LIVE_PRODUCT` | Real endpoint backed by engine data. Frontend does not use it yet. |
| `stock_tax_app/backend/routes/audit.py` | `LIVE_PRODUCT` | Real endpoint backed by engine data. Frontend does not use it yet. |
| `stock_tax_app/backend/routes/settings.py` | `LIVE_PRODUCT` | Real endpoint, but it only exposes static-ish paths/constants from `_build_settings()` rather than a real editable settings store. |

## Frontend

| Path | Classification | Evidence |
|---|---|---|
| `ui/frontend/package.json` | `LIVE_PRODUCT` | Real frontend entrypoint scripts (`dev`, `build`, `lint`, `preview`). |
| `ui/frontend/vite.config.ts` | `LIVE_PRODUCT` | Real `/api` proxy to FastAPI (`6-13`). |
| `ui/frontend/src/main.tsx` | `LIVE_PRODUCT` | Browser bootstrap for React Query + router. |
| `ui/frontend/src/App.tsx` | `LIVE_PRODUCT` | Real app shell and route map. Also proves five major routes are placeholders (`177-223`). |
| `ui/frontend/src/lib/api.ts` | `LIVE_PRODUCT` | Real frontend API layer, but only for `/api/status`, `/api/import`, `/api/years`. |
| `ui/frontend/src/types/api.ts` | `DUPLICATE_LOGIC` | Hand-maintained TS contract duplicate of `stock_tax_app/engine/models.py`. Active, but drift-prone. |
| `ui/frontend/src/screens/overview-screen.tsx` | `LIVE_PRODUCT` | Real connected page using three live hooks. |
| `ui/frontend/src/screens/import-screen.tsx` | `LIVE_PRODUCT` | Real connected page using `/api/import`. |
| `ui/frontend/src/screens/tax-years-screen.tsx` | `LIVE_PRODUCT` | Real connected page using `/api/years`. |
| `ui/frontend/src/screens/coming-next-screen.tsx` | `LIVE_PRODUCT` | Real route component, but intentionally placeholder-only content. |
| `ui/frontend/README.md` | `UNKNOWN` | Accurate about current scope, but documentation only. |
| `ui/prototype.html` | `DEAD_CANDIDATE` | Not imported by Vite or runtime code. Only referenced by `ui/DESIGN.md`. Uses mock data and stale assumptions. |
| `ui/DESIGN.md` | `UNKNOWN` | Product/design document, not runtime code. Large parts are stale or speculative relative to the repo. |

## Tests And Dev Utilities

| Path | Classification | Evidence |
|---|---|---|
| `test_stock_tax_app_api.py` | `LIVE_TEST_ONLY` | Real pytest coverage. Passed during audit. |
| `test_min_gain_optimality.py` | `LIVE_TEST_ONLY` | Real pytest coverage for matching/tax behavior. Passed during audit. |
| `test_locked_year_roundtrip.py` | `LIVE_DEV_TOOL` | Workbook regression script with `main()`, not collected by pytest. Misleading filename, but still useful for manual workbook checks. |
| `verify_workbook.py` | `LEGACY_EXCEL_CORE` | Workbook validator is imported by `write_calculation_result()` and therefore part of the live recalc/write path. |
| `inspect_csvs.py` | `LIVE_DEV_TOOL` | One-off CSV inspection utility. No live imports. |
| `run_dev.ps1` | `LIVE_DEV_TOOL` | Real developer launcher for backend + frontend. |

## Docs And Generated Snapshots

| Path | Classification | Evidence |
|---|---|---|
| `docs/openapi.json` | `GENERATED_ARTIFACT` | Generated schema snapshot. Verified equal to `create_app().openapi()`. Useful, but not source code. |
| `docs/api_samples/*.json` | `GENERATED_ARTIFACT` | Unreferenced JSON snapshots. Not imported anywhere in repo. `docs/api_samples/status.json` includes a local machine path. |
| `docs/API_CONTRACT.md` | `UNKNOWN` | Partly accurate for the current live routes, but overstates backend authority because workbook state is still a backend dependency. |
| `README.md` | `UNKNOWN` | Thin top-level guide. Not harmful, but incomplete about workbook dependence and frontend incompleteness. |
| `README_OPERATOR.md` | `UNKNOWN` | Workbook-era operator guide. Accurate for the old workflow, wrong for the target product direction. |
| `IMPLEMENTATION_NOTES.md` | `UNKNOWN` | Strong workbook-era internals doc. Useful evidence, but architecturally obsolete for the target direction. |

## Data And Artifacts

| Path | Classification | Evidence |
|---|---|---|
| `.csv/*.csv` | `LIVE_PRODUCT` | Real runtime input source. Backend auto-discovers `.csv/*.csv` (`engine/core.py:41-42,485-490`). Tests also copy these files. |
| `stock_tax_system.xlsx` | `LEGACY_EXCEL_CORE` | Default backend output path (`backend/main.py:21`), CLI canonical output (`build_stock_tax_workbook.py:96,3541-3568`), and a test fixture copied by `test_stock_tax_app_api.py:17-22`. |
| `temp/stock_tax_system.xlsx` | `GENERATED_ARTIFACT` | Unreferenced temp workbook under an ignored folder. No code references found. |
| `backend_server.out.log` | `GENERATED_ARTIFACT` | Runtime log capture, not imported anywhere. |
| `backend_server.err.log` | `GENERATED_ARTIFACT` | Runtime log capture, not imported anywhere. |
| `build/` | `GENERATED_ARTIFACT` | Ignored directory and empty during audit. |

## Most Important Dependency Edges

- `stock_tax_app/backend/main.py`
  -> `stock_tax_app/backend/runtime.py`
  -> `stock_tax_app/engine.run`
- `stock_tax_app/engine/core.py`
  -> `build_stock_tax_workbook.py`
  -> `stock_tax_app/engine/policy.py`
  -> `stock_tax_app/engine/ui_state.py`
- `build_stock_tax_workbook.py`
  -> `verify_workbook.py`
  -> `openpyxl`
- `ui/frontend/src/main.tsx`
  -> `ui/frontend/src/App.tsx`
  -> `ui/frontend/src/lib/api.ts`
- `ui/frontend/src/lib/api.ts`
  -> `/api/status`
  -> `/api/import`
  -> `/api/years`

## Inventory Conclusions

- The repo has a real backend and a real frontend shell.
- The workbook script is still the architectural center.
- The frontend is not dead; it is incomplete.
- The biggest duplicate-logic hotspots are year policy and API type definitions.
- The biggest dead-candidate hotspot is the old prototype and unreferenced sample snapshots, not the backend package.

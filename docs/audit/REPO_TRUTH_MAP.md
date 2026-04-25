# Repo Truth Map

## Actual Architecture

Current runtime truth is:

1. `ui/frontend` is a Vite/React shell.
2. The shell talks only to FastAPI over `/api/*`.
3. FastAPI is a very thin adapter over `stock_tax_app.engine.core.run`.
4. `stock_tax_app.engine.core.run` is not an independent engine. It imports `build_stock_tax_workbook` directly (`stock_tax_app/engine/core.py:9,479-519`).
5. `build_stock_tax_workbook.py` is still the real calculation center and also the persistence layer for operator-maintained state via workbook sheet readback (`build_stock_tax_workbook.py:15-18,520-534,1924-2068`).
6. The backend can avoid writing the workbook on read-only requests, but it still reads workbook-derived state and still builds API models from workbook-centric result objects.

The repo already contains a frontend-first aspiration, but not a frontend-first architecture.

## Runtime Flow

### Read path

`GET /api/status` or `GET /api/import` or `GET /api/years`

-> `stock_tax_app.backend.routes.*`

-> `request.app.state.runtime.current()` (`stock_tax_app/backend/runtime.py:29-35`)

-> first request triggers `calculate(write_workbook=False)` (`stock_tax_app/backend/runtime.py:16-27`)

-> `stock_tax_app.engine.core.run(...)` (`stock_tax_app/engine/core.py:479-519`)

-> `build_stock_tax_workbook.calculate_workbook_data(...)` (`stock_tax_app/engine/core.py:489-494`)

-> workbook script loads CSVs and reads user-maintained workbook sheets back from `stock_tax_system.xlsx` (`build_stock_tax_workbook.py:1930-1995`)

-> engine core transforms the workbook result into API models (`stock_tax_app/engine/core.py:70-507`)

### Write path

`POST /api/recalculate`

-> `BackendRuntime.calculate(write_workbook=True)` (`stock_tax_app/backend/main.py:37-39`, `stock_tax_app/backend/runtime.py:16-27`)

-> `engine.core.run(..., write_workbook=True)` (`stock_tax_app/engine/core.py:483-496`)

-> `build_stock_tax_workbook.write_calculation_result(...)` (`stock_tax_app/engine/core.py:495-496`)

-> `write_workbook(...)`

-> `verify_workbook.main(...)`

-> replace `stock_tax_system.xlsx` (`build_stock_tax_workbook.py:2071-2124`)

This means recalc is still workbook-writing and workbook-validating by design, not just optional export.

## Entrypoint Map

| Path | Command | What it does | Classification |
|---|---|---|---|
| `build_stock_tax_workbook.py` | `py -3 build_stock_tax_workbook.py --input ... --output stock_tax_system.xlsx` | Main CLI. Reads CSVs, reads existing workbook state, calculates tax data, writes validated workbook. | `LEGACY_EXCEL_CORE` |
| `stock_tax_app/backend/main.py` | `py -3 -m stock_tax_app.backend.main` | Starts FastAPI on `127.0.0.1:8787`, registers all API routes, exposes `POST /api/recalculate`. | `LIVE_PRODUCT` |
| `run_dev.ps1` | `.\run_dev.ps1` | Opens two PowerShell windows: backend and frontend dev server. It also runs `npm install` every time. | `LIVE_DEV_TOOL` |
| `ui/frontend/package.json` | `npm run dev` | Starts Vite dev server with `/api` proxy to FastAPI (`ui/frontend/vite.config.ts:6-13`). | `LIVE_PRODUCT` |
| `ui/frontend/package.json` | `npm run build` | Type-check + production bundle build. Passed during audit. | `LIVE_DEV_TOOL` |
| `ui/frontend/src/main.tsx` | Browser entrypoint | Boots React Query and the router. | `LIVE_PRODUCT` |
| `ui/frontend/src/App.tsx` | Browser router entrypoint | Declares all primary routes and the shell layout. | `LIVE_PRODUCT` |
| `test_stock_tax_app_api.py` | `py -3 -m pytest -q` | Real pytest coverage for engine/API smoke and sale-review patch. | `LIVE_TEST_ONLY` |
| `test_min_gain_optimality.py` | `py -3 -m pytest -q` | Real pytest unit-ish coverage for MIN_GAIN logic. | `LIVE_TEST_ONLY` |
| `test_locked_year_roundtrip.py` | `py -3 test_locked_year_roundtrip.py` | Manual three-pass workbook regression script. Not collected by pytest because it has no `test_*` functions. | `LIVE_DEV_TOOL` |
| `verify_workbook.py` | `py -3 verify_workbook.py stock_tax_system.xlsx` | Workbook structural validator. Also imported by the main workbook write path. | `LEGACY_EXCEL_CORE` |
| `inspect_csvs.py` | `py -3 inspect_csvs.py .csv/*.csv` | One-off CSV sanity script. No runtime imports. | `LIVE_DEV_TOOL` |
| `ui/prototype.html` | Open in browser | Mock prototype with fake data and future screens. Not wired into Vite app. | `DEAD_CANDIDATE` |

## Frontend Entrypoints And Truth

- Router defined in `ui/frontend/src/App.tsx:177-223`
- Real connected screens:
  - `/` -> `OverviewScreen`
  - `/import` -> `ImportScreen`
  - `/tax-years` -> `TaxYearsScreen`
- Placeholder routes:
  - `/sales-review`
  - `/open-positions`
  - `/fx`
  - `/audit`
  - `/settings`

Actual data hooks exist only for:

- `useStatusQuery()` -> `/api/status` (`ui/frontend/src/lib/api.ts:14-19`)
- `useImportQuery()` -> `/api/import` (`ui/frontend/src/lib/api.ts:21-26`)
- `useYearsQuery()` -> `/api/years` (`ui/frontend/src/lib/api.ts:28-33`)

No frontend code calls `/api/sales`, `/api/open-positions`, `/api/fx`, `/api/audit`, `/api/settings`, or `/api/recalculate`.

## Backend Route Registration Truth

Route registration lives only in `stock_tax_app/backend/main.py:26-41`.

Registered routes:

- `GET /api/status`
- `GET /api/import`
- `GET /api/years`
- `PATCH /api/years/{year}`
- `GET /api/sales`
- `GET /api/sales/{sell_id}`
- `PATCH /api/sales/{sell_id}/review`
- `GET /api/open-positions`
- `GET /api/fx`
- `GET /api/audit`
- `GET /api/settings`
- `POST /api/recalculate`

`docs/openapi.json` is in sync with this route set. `ui/DESIGN.md` is not.

## Tests Truth

Actually executed by `pytest`:

- `test_stock_tax_app_api.py` -> 5 tests
- `test_min_gain_optimality.py` -> 2 tests

Not executed by `pytest` despite the misleading filename:

- `test_locked_year_roundtrip.py`

That file is a manual script, not a real test suite member.

## Current Live Data Snapshot

From a `TestClient(create_app(project_dir=root))` probe against the repo root:

- `global_status = needs_review`
- `unresolved_checks = 1`
- The only current unresolved check is a tiny unmatched TSLA sell residual routed to `/audit`
- `trace_counts = {csv_files: 5, raw_rows: 214, transactions: 190, ignored_rows: 24, match_lines: 57, open_lots: 122}`
- `GET /api/open-positions` returned 20 rows and all of them had `status = unknown`
- `GET /api/years` returned 6 tax years
- 2024 is correctly enforced as filed/locked/LIFO
- 2025 currently resolves to `FIFO`, not `LIFO`

## Code Truth Vs Stale Claims

### Code truth

- The backend exists and works.
- The frontend exists and builds.
- Only three frontend pages use live data.
- Workbook sheet data still feeds the calculation path.
- `POST /api/recalculate` is synchronous and workbook-writing.

### Stale or false claims

- `stock_tax_app/engine/__init__.py:4-5` says Excel is “never a data source for the API”. False. `engine.core.run()` calls `calculate_workbook_data()`, which reads workbook user state (`build_stock_tax_workbook.py:1930`, `520-534`).
- `ui/DESIGN.md:471-505` describes many endpoints that do not exist:
  - `GET /api/recalculate/:run_id`
  - `GET /api/years/:year`
  - `PATCH /api/years/:year/settings`
  - `POST /api/sales/:id/export`
  - `POST /api/fx/fetch`
  - `PATCH /api/fx/:year`
  - `POST /api/audit/export`
  - `PATCH /api/settings`
- `ui/DESIGN.md:751-752` says the prototype demonstrates all eight screens with mock data. True for the prototype only, false for the actual Vite app.
- `ui/DESIGN.md:769` says the workbook is still the deliverable. That is the opposite of the current product direction.
- `README_OPERATOR.md` is an Excel-first operator manual from top to bottom (`README_OPERATOR.md:1-193`). It describes the legacy workflow accurately, but it describes the wrong product target.

## Bottom Line

The repo is not “backend truth + frontend operator UI + optional Excel export”.

The repo is:

- workbook-centric calculation and persistence
- a thin FastAPI wrapper over that workbook-centric core
- a partially connected frontend shell
- stale design docs that describe a much more complete product than the code actually implements

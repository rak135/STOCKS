# API Frontend Gap Report

## Route Truth Table

| Route | Impl file | Runtime status | Depends on | Frontend usage | Docs truth |
|---|---|---|---|---|---|
| `GET /api/status` | `stock_tax_app/backend/routes/status.py` | Real engine data | `runtime.current().app_status` -> `engine.core._build_status()` | Used by `AppFrame` and `OverviewScreen` | `docs/API_CONTRACT.md` accurate |
| `GET /api/import` | `stock_tax_app/backend/routes/import_summary.py` | Real engine data | `engine.core._build_import_summary()` | Used by `ImportScreen` and `OverviewScreen` | `docs/API_CONTRACT.md` accurate |
| `GET /api/years` | `stock_tax_app/backend/routes/years.py` | Real engine data | `engine.core._build_tax_years()` | Used by `TaxYearsScreen` and `OverviewScreen` | `docs/API_CONTRACT.md` accurate |
| `PATCH /api/years/{year}` | `stock_tax_app/backend/routes/years.py` | Partial / fake | Policy guard works; actual edit path returns `501` for unlocked years | Not used by frontend | `docs/API_CONTRACT.md` understates the gap; `ui/DESIGN.md` is stale fantasy |
| `GET /api/sales` | `stock_tax_app/backend/routes/sales.py` | Real engine data | `engine.core._build_sales()` | Not used by frontend | Backend real, frontend missing |
| `GET /api/sales/{sell_id}` | `stock_tax_app/backend/routes/sales.py` | Real engine data | `engine.core._build_sales()` | Not used by frontend | Backend real, frontend missing |
| `PATCH /api/sales/{sell_id}/review` | `stock_tax_app/backend/routes/sales.py` | Real mutation | `backend.runtime.update_sell_review()` -> `.ui_state.json` | Not used by frontend | Route exists and works, but workbook review state is a different store |
| `GET /api/open-positions` | `stock_tax_app/backend/routes/positions.py` | Real data, weak usefulness on current dataset | `engine.core._build_open_positions()` | Not used by frontend | Backend real, frontend missing |
| `GET /api/fx` | `stock_tax_app/backend/routes/fx.py` | Real data | `engine.core._build_fx_years()` | Not used by frontend | Backend real, frontend missing |
| `GET /api/audit` | `stock_tax_app/backend/routes/audit.py` | Real summary data | `engine.core._build_audit_summary()` | Not used by frontend | Backend real, frontend missing |
| `GET /api/settings` | `stock_tax_app/backend/routes/settings.py` | Real endpoint, mostly static/config-display data | `engine.core._build_settings()` | Not used by frontend | `docs/API_CONTRACT.md` says display only; that is accurate |
| `POST /api/recalculate` | `stock_tax_app/backend/main.py` inline route | Real, synchronous, workbook-writing | `runtime.calculate(write_workbook=True)` | Not used by frontend | `docs/API_CONTRACT.md` accurate; `ui/DESIGN.md` wrong about async run IDs |

## What Is Real Vs Placeholder

### Backend real

- `/api/status`
- `/api/import`
- `/api/years`
- `/api/sales`
- `/api/sales/{sell_id}`
- `/api/sales/{sell_id}/review`
- `/api/open-positions`
- `/api/fx`
- `/api/audit`
- `/api/settings`
- `/api/recalculate`

### Backend partial or fake

- `PATCH /api/years/{year}`
  - Real lock guard for filed years
  - No actual update implementation for non-filed years
  - Returns `501`

### Frontend real

- Overview
- Import
- Tax Years

### Frontend placeholder

- Sales Review
- Open Positions
- FX Rates
- Audit Pack
- Settings

Evidence: `ui/frontend/src/App.tsx:185-218` routes all five missing workflows to `ComingNextScreen`.

## Biggest Backend/Frontend Mismatches

### 1. The backend can route the user into a dead-end page

`engine.core._check_href()` maps unresolved checks to `/fx`, `/open-positions`, `/audit`, `/years`, or `/import` (`stock_tax_app/engine/core.py:58-67`).

Current frontend reality:

- `/import` and `/tax-years` are real
- `/fx`, `/open-positions`, and `/audit` are placeholders

Concrete proof from live data:

- Current `GET /api/status` returns `next_action.href = "/audit"`
- Current frontend `/audit` page is a placeholder

That is a bad user experience and a trust problem, not a minor TODO.

### 2. Backend sales functionality exists; frontend sales workflow does not

The backend already exposes:

- sales list
- sale detail
- sale review mutation

But `ui/frontend/src/App.tsx:186-190` still routes Sales Review to placeholder copy.

### 3. Backend FX and positions data exist; frontend still hides them behind “coming next”

Backend:

- `GET /api/fx`
- `GET /api/open-positions`

Frontend:

- placeholders only

Worse, current live `GET /api/open-positions` data returns 20 rows and all are `unknown`, so this part of the workflow is both missing in the UI and weak in present output quality.

### 4. Docs promise endpoints that do not exist

`ui/DESIGN.md:471-505,807-820` promises:

- async recalc jobs
- year-detail/settings patch endpoints
- sales export
- FX fetch and patch
- audit export
- settings patch

None of those are implemented.

## Per-Page Frontend Classification

| Page | File | Classification | Evidence |
|---|---|---|---|
| Overview | `ui/frontend/src/screens/overview-screen.tsx` | `REAL_CONNECTED` | Uses `/api/status`, `/api/import`, `/api/years` |
| Import | `ui/frontend/src/screens/import-screen.tsx` | `REAL_CONNECTED` | Uses `/api/import` |
| Tax Years | `ui/frontend/src/screens/tax-years-screen.tsx` | `REAL_CONNECTED` | Uses `/api/years` |
| Sales Review | routed via `ComingNextScreen` | `PLACEHOLDER` | No sales hook exists in frontend |
| Open Positions | routed via `ComingNextScreen` | `PLACEHOLDER` | No positions hook exists in frontend |
| FX Rates | routed via `ComingNextScreen` | `PLACEHOLDER` | No FX hook exists in frontend |
| Audit Pack | routed via `ComingNextScreen` | `PLACEHOLDER` | No audit hook or export action exists |
| Settings | routed via `ComingNextScreen` | `PLACEHOLDER` | No settings hook or editor exists |

## Frontend-First Target Workflow Gap Map

### 1. Import data

Current:

- Backend: yes
- Frontend: yes, read-only

Gap:

- No frontend recalc trigger
- No raw row drill-down
- No mutation path for import fixes

### 2. Review transactions

Current:

- Backend: indirect only through import summary and workbook artifacts
- Frontend: no transaction review page

Gap:

- Missing API to inspect normalized transaction rows directly
- Missing UI to inspect ignored rows and malformed rows in detail

### 3. Review sales and lot matches

Current:

- Backend: yes
- Frontend: no

Gap:

- Missing live Sales Review page
- Missing list filters/search
- Missing lot-detail evidence UI

### 4. Choose method per year where allowed

Current:

- Backend read: yes
- Backend write: no, except 2024 lock rejection
- Frontend: read-only cards only

Gap:

- Missing writable year settings endpoint
- Missing frontend mutation flow
- Missing explicit lock/unlock workflow

### 5. Inspect FX rates and missing rates

Current:

- Backend read: yes
- Backend write/fetch: no dedicated API
- Frontend: no

Gap:

- Missing FX screen
- Missing manual override API
- Missing fetch/verify actions

### 6. Inspect taxable vs exempt classification

Current:

- Backend: yes in sale detail and lot detail
- Frontend: no

Gap:

- Missing sale-detail screen
- Missing explanation UI for time-test and mixed sales

### 7. Review audit summary

Current:

- Backend: yes summary only
- Frontend: no

Gap:

- Missing audit screen
- Missing trace drill-down
- Missing snapshot visibility UI

### 8. Export final report if needed

Current:

- Backend: workbook write only via recalc, no export API
- Frontend: no

Gap:

- Missing explicit export endpoint(s)
- Missing export UX
- Missing separation between engine recalc and export rendering

## Missing Endpoints Needed To Replace Workbook Workflow

These are the smallest useful backend additions for the target direction:

1. `PATCH /api/years/{year}`
   - Real implementation for method, FX method, 100k toggle, tax rate, filed reconciliation note, lock state
2. `GET /api/transactions` and optionally `GET /api/transactions/{id}`
   - Needed for import review and audit drill-down
3. `GET /api/sales` filters + stable detail contract
   - Needed for real Sales Review UX
4. `GET /api/fx` plus real mutation/fetch endpoints
   - Needed to stop hiding FX behind workbook sheets
5. `GET /api/open-positions` drill-down improvements
   - Needed because current aggregate output is too weak alone
6. `POST /api/recalculate`
   - Keep, but decouple from workbook writing
7. `POST /api/export/workbook` or `POST /api/audit/export`
   - Export-only, not calculation truth

## Bottom Line

Backend coverage is ahead of frontend coverage.

The dangerous part is not “backend missing everything”.
The dangerous part is:

- some backend routes are real,
- some frontend pages are fake,
- and the app can route operators from a real backend warning into a fake frontend destination.

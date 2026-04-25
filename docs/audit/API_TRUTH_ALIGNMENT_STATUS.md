# API Truth Alignment Status

## Endpoint Truth Table

| Route | Impl file | Frontend usage | Data owner | Safe for frontend display | Needs explicit status / provenance | Could lie by omission before this slice | Current status after this slice |
|---|---|---|---|---|---|---|---|
| `GET /api/status` | `stock_tax_app/backend/routes/status.py` | Used by app frame and Overview | generated calculation + static config summary | Yes, with caveats disclosed | Yes | Yes: workbook-backed domains were invisible | Exposes `truth_status`, `status_reasons`, `workbook_backed_domains` |
| `GET /api/import` | `stock_tax_app/backend/routes/import_summary.py` | Used by Import and Overview | generated calculation | Yes | Yes | Yes: import could look fine while calculation was blocked elsewhere | Exposes `truth` |
| `GET /api/years` | `stock_tax_app/backend/routes/years.py` | Used by Overview and Tax Years | ProjectState for migrated settings/methods; workbook fallback for reconciliation/locked domains; generated calculation | Yes | Yes | Yes: blocked empty list was ambiguous | Returns `TaxYearList { items, truth }` plus per-year provenance |
| `PATCH /api/years/{year}` | `stock_tax_app/backend/routes/years.py` | Not used by frontend yet | not implemented, with policy guard | Yes, as an explicit failure | Yes | Less so, but docs could over-assume editability | Still `501` for real edits, still `409` for protected years |
| `GET /api/sales` | `stock_tax_app/backend/routes/sales.py` | Backend-ready, frontend placeholder | generated calculation + UIState + ProjectState/workbook instrument map | Yes | Yes | Yes: blocked empty list was ambiguous; instrument-map source was implicit | Returns `SellList { items, truth }` |
| `GET /api/sales/{sell_id}` | `stock_tax_app/backend/routes/sales.py` | Backend-ready, frontend placeholder | generated calculation + UIState + ProjectState/workbook instrument map | Yes | Yes | Yes: per-sale provenance was implicit | Returns per-sale `truth`, `instrument_map_source`, `review_state_source` |
| `PATCH /api/sales/{sell_id}/review` | `stock_tax_app/backend/routes/sales.py` | Backend-ready, frontend placeholder | UIState | Yes | Low | Low | No behavior change; now aligns with explicit UIState provenance in reads |
| `GET /api/open-positions` | `stock_tax_app/backend/routes/positions.py` | Backend-ready, frontend placeholder | generated calculation + ProjectState/workbook instrument map | Yes | Yes | Yes: unknown rows were status-only and blocked empty list was ambiguous | Returns `OpenPositionList { items, truth }` and row-level unknown reasons |
| `GET /api/fx` | `stock_tax_app/backend/routes/fx.py` | Backend-ready, frontend placeholder | ProjectState + workbook fallback + CNB cache + static config | Yes | Yes | Yes: effective source was implicit | Returns `FxYearList { items, truth }` and per-year `rate_source` |
| `GET /api/audit` | `stock_tax_app/backend/routes/audit.py` | Backend-ready, frontend placeholder | generated calculation + workbook-backed snapshot/reconciliation domains | Yes, if shown as summary only | Yes | Yes: could be read as final readiness | Explicitly `summary_only`, `truth_status`, `status_reasons`, `workbook_backed_domains` |
| `GET /api/settings` | `stock_tax_app/backend/routes/settings.py` | Backend-ready, frontend placeholder | static config + domain ownership summary | Yes | Yes | Yes: flat values could imply editability | Exposes per-field `field_meta` and `domain_sources` |
| `POST /api/recalculate` | `stock_tax_app/backend/main.py` | Not used by frontend yet | generated calculation | Yes | Inherited from nested models | Yes, via nested ambiguous collections | Returns `EngineResult` with the same truth containers and provenance fields |

## Changes Made

- Added explicit truth vocabulary to backend API models:
  - `TruthMeta`
  - `CollectionTruth`
  - `TruthReason`
- Wrapped collection endpoints in `{ items, truth }` envelopes:
  - `/api/years`
  - `/api/sales`
  - `/api/open-positions`
  - `/api/fx`
- Added per-domain provenance where current migrated ownership matters:
  - `TaxYear.settings_source`
  - `TaxYear.method_source`
  - `TaxYear.reconciliation_source`
  - `Sell.instrument_map_source`
  - `Sell.review_state_source`
  - `FxYear.rate_source`
  - `OpenPosition.instrument_map_source`
- Added blocked / partial / summary-only reasons to:
  - `/api/status`
  - `/api/import`
  - `/api/audit`
  - `/api/settings`
- Made blocked collection responses non-ambiguous by returning:
  - `truth.status = "blocked"`
  - `truth.empty_meaning = "blocked"`
  - explicit reason rows
- Added row-level unknown reasons to `/api/open-positions`.
- Updated the existing real frontend screens to consume the new `/api/years` envelope and show a truthful banner when no year items are available.

## Script Alignment Audit

| Script / entrypoint | Current truth posture | Notes | Change in this slice |
|---|---|---|---|
| `build_stock_tax_workbook.py` | Consumes canonical effective state for migrated domains, still uses workbook fallback for unmigrated domains | Year settings, method selection, FX yearly/daily, instrument map, and review state already flow from ProjectState/UIState-first effective state before workbook export | No code change required; existing behavior is already safe for migrated domains |
| `verify_workbook.py` | Validates workbook artifact only | Does not feed API truth back into runtime | No change |
| `run_dev.ps1` / backend smoke entry | Starts dev services only | Not a data owner | No change |

### Script-specific conclusion

No safe script fix was required in this slice. For already migrated
domains, workbook export already reflects canonical effective state
instead of stale workbook truth:

- `year_settings`
- `method_selection`
- `fx_yearly`
- `fx_daily`
- `instrument_map`
- review state

## Files Changed In This Slice

- `stock_tax_app/backend/routes/fx.py`
- `stock_tax_app/backend/routes/positions.py`
- `stock_tax_app/backend/routes/sales.py`
- `stock_tax_app/backend/routes/years.py`
- `stock_tax_app/engine/__init__.py`
- `stock_tax_app/engine/core.py`
- `stock_tax_app/engine/models.py`
- `test_project_state_store.py`
- `test_stock_tax_app_api.py`
- `ui/frontend/src/lib/api.ts`
- `ui/frontend/src/screens/overview-screen.tsx`
- `ui/frontend/src/screens/tax-years-screen.tsx`
- `ui/frontend/src/types/api.ts`
- `docs/audit/FRONTEND_TRUTH_CONTRACT.md`
- `docs/audit/API_TRUTH_ALIGNMENT_STATUS.md`

## Tests Added Or Strengthened

- Blocked collection truth test
- ProjectState provenance test through API
- Open-positions unknown-reason truth test
- Settings display-only / ownership truth test
- Audit summary truth test
- Existing route tests updated for collection envelopes and provenance fields

## Commands Run

```powershell
py -3 -m pytest -q test_project_state_store.py
py -3 -m pytest -q test_stock_tax_app_api.py
cd ui/frontend
npm run build
py -3 -m pytest -q
py -3 - <<'PY'
from stock_tax_app.backend.main import create_app
from fastapi.testclient import TestClient

app = create_app()
client = TestClient(app)

for path in [
    "/api/status",
    "/api/import",
    "/api/years",
    "/api/sales",
    "/api/open-positions",
    "/api/fx",
    "/api/audit",
    "/api/settings",
]:
    r = client.get(path)
    print(path, r.status_code)
PY
```

## Results

- `py -3 -m pytest -q test_project_state_store.py`
  - `15 passed`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
  - `32 passed`
- `npm run build`
  - success
- `py -3 -m pytest -q`
  - `49 passed`
- backend smoke
  - `/api/status 200`
  - `/api/import 200`
  - `/api/years 200`
  - `/api/sales 200`
  - `/api/open-positions 200`
  - `/api/fx 200`
  - `/api/audit 200`
  - `/api/settings 200`

## Remaining Gaps

- The frontend still has placeholder screens for Sales Review, Open Positions, FX, Audit, and Settings.
- `PATCH /api/years/{year}` still does not implement edits for unlocked years.
- `GET /api/settings` is truthful metadata only; there is still no settings mutation workflow.
- `GET /api/audit` is still summary-only and not an export workflow.
- Per-date FX provenance is still aggregated at year level.
- Open-position response does not yet expose per-row frozen-snapshot provenance.
- Workbook-backed domains remain:
  - `corporate_actions`
  - `locked_years`
  - `frozen_inventory`
  - `frozen_lot_matching`
  - `frozen_snapshots`
  - `filed_year_reconciliation`

## Recommended Next Slice

`P1.4` should be real frontend surfaces for existing truthful backend
data, starting with the highest-value room:

1. Replace the Sales Review placeholder with a real `/api/sales` list/detail UI.
2. Keep the new truth/provenance contract visible in that screen rather than hiding it.
3. After Sales Review, do the same for Open Positions and FX before any export-only refactor work.

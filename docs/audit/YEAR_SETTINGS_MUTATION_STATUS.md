# Year Settings Mutation Status (P2.0)

## Scope
This document covers P2.0 only: real mutation of per-year tax settings through `PATCH /api/years/{year}` backed by ProjectState.

Out of scope for this slice:
- audit export implementation
- settings mutation
- FX manual edit UX/API outside year-level `fx_method`
- corporate actions
- locked snapshot migration
- dividend support

## Endpoint behavior
- Endpoint: `PATCH /api/years/{year}`
- Backend route: `stock_tax_app/backend/routes/years.py`
- Behavior:
  - Verifies the year exists in backend runtime output.
  - Rejects mutation for locked/filed years using policy guard.
  - Validates payload fields.
  - Persists supported values to ProjectState:
    - `method` -> `ProjectState.method_selection[year][instrument_id]` for known instruments in that year.
    - `fx_method`, `tax_rate`, `apply_100k_exemption` -> `ProjectState.year_settings[year]` (`apply_100k` key).
  - Saves `.stock_tax_state.json`.
  - Recalculates runtime (`write_workbook=False`) and returns updated `TaxYear` row.

## Supported fields
- `method`: `FIFO | LIFO | MIN_GAIN | MAX_GAIN`
- `fx_method`: `FX_UNIFIED_GFR | FX_DAILY_CNB`
- `tax_rate`: decimal numeric value (for example `0.15`)
- `apply_100k_exemption`: boolean

## Validation rules
- Locked/filed year mutation:
  - rejected with `409`
  - detail text comes from year policy (includes locked-year context)
- Unknown method:
  - rejected with `422`
- Invalid `fx_method`:
  - rejected with `422`
- Invalid `tax_rate`:
  - rejected with `422` when non-numeric, boolean, NaN/inf, or `< 0`
  - no silent coercion of nonsense values
- Empty mutation payload:
  - rejected with `400`

## Locked-year protection
- 2024 remains filed/locked under policy and cannot be mutated.
- Backend enforcement is authoritative; UI disable state is advisory only.

## ProjectState persistence behavior
- ProjectState is persisted in `.stock_tax_state.json` and is the source of truth over workbook fallback.
- Existing workbook fallback remains for non-overridden years.
- GET years reflects ProjectState-backed values and provenance via:
  - `settings_source = project_state`
  - `method_source = project_state`

## Frontend behavior
- Tax Years screen now supports editing for unlocked years only.
- Locked/filed years remain visibly disabled.
- Save flow:
  - explicit per-year Apply button
  - loading state while saving
  - success indicator after save
  - backend error detail surfaced on failure
- No optimistic truth overwrite:
  - on success, frontend invalidates/refetches:
    - years
    - status
    - audit
    - sales
    - fx
    - open-positions
- Percent UI for tax rate is preserved; persisted value is decimal.
- Provenance chips/labels remain visible.

## Tests added
In `test_stock_tax_app_api.py`:
- `test_api_patch_year_updates_method_for_unlocked_year`
- `test_api_patch_year_updates_tax_rate_for_unlocked_year`
- `test_api_patch_year_updates_fx_method_for_unlocked_year`
- `test_api_rejects_2024_method_change` (existing locked-year protection check)
- `test_api_patch_year_rejects_invalid_method`
- `test_api_patch_year_rejects_invalid_tax_rate`
- `test_year_settings_patch_survives_recalc_and_runtime_reload`
- `test_get_years_reflects_project_state_values_and_provenance_after_patch`

## Commands run
- `py -3 -m pytest -q test_project_state_store.py`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
- `py -3 -m pytest -q`
- `cd ui/frontend && npm run build`
- `./run_app.ps1 -NoBrowser -AutoStopAfterSeconds 20`

## Remaining gaps
- Method mutation currently targets known instruments for the selected year. If a year has no known instruments, method change has no effect in calculation output.
- No additional reconciliation note / filed-tax mutation was added in this slice.
- No settings-domain mutation or other out-of-scope domains were changed.

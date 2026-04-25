# YEAR_METHOD_DEFAULT_STATUS

Date: 2026-04-25

Scope: P2.0a only. This document covers stable year-level method default persistence for `PATCH /api/years/{year}` and runtime method resolution. It does not cover audit export, settings mutation beyond the existing P2.0 fields, FX manual edit, corporate actions, locked snapshot migration, broader tax formula changes, workbook removal, or dividends.

## Old behavior

- `PATCH /api/years/{year}` persisted `method` by writing `ProjectState.method_selection[year][instrument_id]` rows for the currently known instrument universe.
- The runtime treated those rows as per-instrument selections.
- A year-level method choice had no independent storage location.
- If a year had no known instruments, a method patch had no stable runtime target.
- `GET /api/years` could report a method derived from instrument rows rather than a stable year default.

## New behavior

- `PATCH /api/years/{year}` persists `method` in `ProjectState.year_settings[year].method`.
- Per-instrument `ProjectState.method_selection` remains supported and still wins for individual instruments.
- Runtime method resolution now follows this order:
  1. per-instrument `ProjectState.method_selection[year][instrument_id]`
  2. year-level `ProjectState.year_settings[year].method`
  3. workbook `Method_Selection` fallback through the merged runtime state
  4. policy default method
- `GET /api/years` reports the explicit year default when present, with `method_source = project_state`.
- A year that exists only through settings state can now store and return a method default even when it has no known instruments.

## ProjectState schema decision

- Reused `ProjectState.year_settings[year]` and added the `method` key there.
- No new top-level map was introduced.
- `ProjectState.method_selection` remains the per-instrument override store.

## Compatibility handling

- The patch route includes an explicit cleanup for the old synthetic shape.
- When a year had no explicit year default yet, and its stored per-instrument rows were a uniform copy of the visible year method, those rows are removed when writing the new year default.
- This preserves real per-instrument overrides while letting legacy year-wide rows stop shadowing the new default.

## Files changed

- `stock_tax_app/backend/routes/years.py`
- `stock_tax_app/state/project_store.py`
- `build_stock_tax_workbook.py`
- `stock_tax_app/engine/core.py`
- `test_project_state_store.py`
- `test_stock_tax_app_api.py`
- `docs/audit/YEAR_METHOD_DEFAULT_STATUS.md`

## Tests added or updated

- Updated API test for year method patch persistence to assert `year_settings[year].method`.
- Added API regression for migrating legacy uniform per-instrument rows on patch.
- Added API regression for storing a method default on a year with no known instruments.
- Added runtime regression for year default on a year with no known instruments.
- Added runtime regression proving per-instrument override beats year default.
- Updated state roundtrip coverage to include `year_settings[year].method`.

## Commands run

- `py -3 -m pytest -q test_project_state_store.py`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
- `py -3 -m pytest -q`
- `./run_app.ps1 -NoBrowser -AutoStopAfterSeconds 20`

## Remaining gaps

- Workbook export still models explicit method rows via the `Method_Selection` sheet; there is no new dedicated workbook column for year method defaults.
- Legacy synthetic per-instrument rows are only normalized when a new year method patch is written; there is no broad one-time migration.
- Filed and locked historical snapshots remain unchanged.
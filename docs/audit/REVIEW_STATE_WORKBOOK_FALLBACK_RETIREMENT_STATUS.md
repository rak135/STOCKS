# REVIEW_STATE_WORKBOOK_FALLBACK_RETIREMENT_STATUS

Date: 2026-04-25
Scope: P3.0 - Retire Review_State workbook fallback from normal runtime

## Old behavior

- Normal runtime calculation loaded workbook user state from the export path.
- If workbook `Review_State` existed, runtime would merge missing sell reviews into project-root `.ui_state.json` automatically.
- Conflicts were ignored in favor of root UI state, but adoption still happened implicitly.
- Result: a generated/legacy workbook could influence live review state when `.ui_state.json` was missing.

## New ownership

- Canonical owner is project-root `.ui_state.json`.
- Normal runtime never auto-adopts workbook `Review_State`.
- If `.ui_state.json` is missing, runtime review state is empty (unreviewed).

## Normal runtime rule

- `GET /api/sales` and `GET /api/sales/{sell_id}` reflect only `.ui_state.json` review data layered on top of calculated sells.
- `PATCH /api/sales/{sell_id}/review` persists to project-root `.ui_state.json`.
- Recalculate/reload preserves review state from `.ui_state.json` only.
- Workbook `Review_State` is ignored in normal runtime unless explicitly migrated.

## Explicit migration path

- Added explicit helper in `build_stock_tax_workbook.py`:
  - `adopt_legacy_workbook_review_state(project_dir, workbook_path, overwrite=False)`
- Behavior:
  - Reads workbook `Review_State` via existing workbook read path.
  - Canonicalizes sell IDs before persistence.
  - Writes into project-root `.ui_state.json` using explicit merge helper.
  - With `overwrite=False`, fills only missing sell review entries.
  - With `overwrite=True`, replaces conflicting existing entries.
  - Returns summary counts: `legacy_rows`, `adopted`, `overwritten`, `skipped_conflicts`.

## Conflict rules

- Project-root `.ui_state.json` always wins in normal runtime.
- Legacy workbook `Review_State` never overrides root state automatically.
- Explicit adoption with `overwrite=False` only fills missing entries.
- Explicit adoption with `overwrite=True` can replace conflicting entries.

## Workbook export behavior

- Workbook export still writes `Review_State` for compatibility.
- Exported `Review_State` comes from canonical backend/UI state (`.ui_state.json`), not from workbook fallback reads.
- Workbook `Review_State` is now output compatibility, not runtime authority.

## Tests added/updated

Updated in `test_stock_tax_app_api.py`:

- `test_runtime_ignores_legacy_workbook_review_state_when_ui_state_missing`
  - Asserts runtime ignores workbook `Review_State` when root UI state is missing.
  - Asserts no silent `.ui_state.json` creation.
- `test_explicit_workbook_review_state_adoption_migrates_when_ui_state_missing`
  - Asserts explicit helper creates root `.ui_state.json` and migrates review data.
- `test_explicit_workbook_review_state_adoption_overwrite_behavior`
  - Asserts `overwrite=False` preserves canonical root values.
  - Asserts `overwrite=True` replaces conflicting root values.

Existing coverage retained:

- `test_ui_state_beats_conflicting_workbook_review_state`
- `test_workbook_export_reflects_backend_ui_state`
- `test_sale_review_patch_survives_recalc_and_runtime_reload`

## Commands run and results

- `py -3 -m pytest -q test_stock_tax_app_api.py` -> 69 passed
- `py -3 -m pytest -q test_project_state_store.py` -> 22 passed
- `py -3 -m pytest -q test_root_excel_absent.py` -> 4 passed
- `py -3 -m pytest -q` -> 97 passed
- `py -3 test_locked_year_roundtrip.py` -> PASS (3-phase script output; expected controlled stale-snapshot guidance in pass 2)

## Remaining workbook fallback domains (intentionally not changed in P3.0)

- Settings / Method_Selection fallback paths
- FX_Yearly and FX_Daily fallback paths
- Instrument_Map fallback paths
- Corporate_Actions fallback paths
- Locked_Years fallback path
- Frozen_Inventory / Frozen_Lot_Matching / Frozen_Snapshots fallback paths
- Filed_Year_Reconciliation fallback path

These remain out of scope for this slice and continue to follow existing explicit adoption and fallback rules.

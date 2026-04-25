# P1 Project State Store Status

## Why This Exists

The repository is still workbook-centered. Many operator-maintained inputs are still stored in workbook sheets and read back into calculation.

This slice introduces a backend-owned state-store boundary so migration away from workbook-sheet persistence can happen incrementally instead of through one large refactor.

The goal of this slice is architecture and migration safety, not a full ownership flip yet.

## State File

- Path: `.stock_tax_state.json`
- Location: project root
- Schema version: `1`

## ProjectState v1 Schema Sections

- `metadata`
- `year_settings`
- `method_selection`
- `fx_yearly`
- `fx_daily`
- `instrument_map`
- `corporate_actions`
- `locked_years`
- `frozen_inventory`
- `frozen_lot_matching`
- `frozen_snapshots`
- `filed_year_reconciliation`

The schema is intentionally explicit and boring. It is not a generic blob store.

## What Was Added

New backend-owned state-store modules:

- `stock_tax_app/state/models.py`
- `stock_tax_app/state/project_store.py`
- `stock_tax_app/state/__init__.py`

Implemented store behavior:

- load missing file -> default empty `ProjectState`
- deterministic JSON save with atomic replace
- explicit unsupported-version failure
- explicit adapter boundary for workbook migration

New boundary functions:

- `load_project_state(project_dir)`
- `save_project_state(project_dir, state)`
- `adopt_legacy_workbook_state(project_dir, legacy_state)`
- `merge_project_state_with_legacy_fallback(project_state, legacy_state)`

## Domains Migrated In This Slice

Actually wired into runtime:

- `year_settings`
- `method_selection`

These are the only domains currently read through the new backend-owned store.

## Conflict Rule

For migrated domains:

- `ProjectState` wins if present
- workbook state is used as fallback if `ProjectState` is missing
- policy/runtime defaults are used only if neither source has a value

For this slice, runtime uses read-through fallback.

- fallback is active in normal runtime through `merge_project_state_with_legacy_fallback()`
- adoption into `.stock_tax_state.json` is available explicitly through `adopt_legacy_workbook_state()`
- adoption is not forced automatically during normal runtime yet

## Runtime Wiring

`build_stock_tax_workbook.calculate_workbook_data()` now:

1. loads legacy workbook user state
2. loads backend `ProjectState`
3. merges `ProjectState` over workbook fallback for migrated domains
4. continues using the existing workbook engine with the merged state

This keeps runtime behavior stable while establishing a real backend-owned migration boundary.

## Workbook Export Compatibility

Workbook sheet layout was not changed.

For migrated domains:

- if `ProjectState` owns a setting or method, workbook export now reflects that value
- workbook `Settings` and `Method_Selection` are no longer an independent source of truth for those migrated fields during runtime

## What Still Remains Workbook-Backed

Still workbook-backed after this slice:

- `FX_Yearly`
- `FX_Daily`
- `Instrument_Map`
- `Corporate_Actions`
- `Locked_Years`
- `Frozen_Inventory`
- `Frozen_Lot_Matching`
- `Frozen_Snapshots`
- `Filed_Year_Reconciliation`

Review state remains backend-owned separately in `.ui_state.json` and was not moved into `ProjectState` in this slice.

## Files Changed

- `stock_tax_app/state/models.py`
- `stock_tax_app/state/project_store.py`
- `stock_tax_app/state/__init__.py`
- `build_stock_tax_workbook.py`
- `test_project_state_store.py`
- `docs/audit/P1_PROJECT_STATE_STORE_STATUS.md`

## Tests Added

- missing-file load returns default `ProjectState`
- save/load roundtrip preserves semantic equality
- unsupported schema version fails explicitly
- `ProjectState` beats workbook fallback for wired domains
- legacy workbook fallback still works and can be explicitly adopted into `.stock_tax_state.json`
- workbook export reflects `ProjectState` for migrated domains

Existing behavior also remains covered by the existing API suite:

- `2024` filed/locked/LIFO
- `2025` explicit FIFO default
- existing engine/API smoke paths still pass

## Commands Run

- `py -3 -m pytest -q test_project_state_store.py`
  - PASS
  - `6 passed in 8.89s`

- `py -3 -m pytest -q test_stock_tax_app_api.py`
  - PASS
  - `23 passed in 14.44s`

- `py -3 -m pytest -q`
  - PASS
  - `31 passed in 22.20s`

- Backend smoke:

```powershell
@'
from stock_tax_app.backend.main import create_app
from fastapi.testclient import TestClient

app = create_app()
client = TestClient(app)

print("status", client.get("/api/status").status_code)
print("years", client.get("/api/years").status_code)
print("settings", client.get("/api/settings").status_code)
'@ | py -3 -
```

  - PASS
  - observed output:
    - `status 200`
    - `years 200`
    - `settings 200`

## Pass/Fail Summary

- P1.0 store skeleton introduced: PASS
- Low-risk runtime wiring for proof domains: PASS
- Workbook export compatibility for migrated domains: PASS
- Full Python suite: PASS
- Backend smoke: PASS

## Remaining Migration Plan

Recommended next step:

- migrate one additional domain with the same rule set:
  - `ProjectState` wins
  - workbook fallback remains available
  - export reflects `ProjectState`

Best next candidate:

- `fx_yearly` and `fx_daily` together, because P0.3 already made FX correctness strict and this would move the highest-risk remaining operator state closer to backend ownership.

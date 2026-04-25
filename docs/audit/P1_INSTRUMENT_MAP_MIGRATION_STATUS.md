# P1.2 Instrument Map Migration Status

## Scope

This slice migrates only `instrument_map` ownership into backend `ProjectState`.

Not migrated in this slice:

- `corporate_actions`
- `locked_years`
- `frozen_inventory`
- `frozen_lot_matching`
- `frozen_snapshots`
- `filed_year_reconciliation`

## Old Instrument Map Ownership

Before P1.2, instrument identity was workbook-primary:

- workbook `Instrument_Map` sheet was read through `load_existing_user_state()`
- `build_instrument_map()` built the effective map from workbook rows
- missing rows fell back to generated identity `Instrument_ID == Yahoo Symbol`

That effective map was then applied through `apply_instrument_map()` and influenced:

- transaction `instrument_id`
- matching/method selection grouping
- sales API `instrument_id`
- workbook export `Instrument_Map`
- open-position extraction from raw Yahoo position rows

## New Instrument Map Ownership

After P1.2, canonical owner is backend `ProjectState` in `.stock_tax_state.json`:

- `instrument_map`

Normal runtime now:

1. loads workbook user state
2. loads backend `ProjectState`
3. merges `ProjectState` `instrument_map` over workbook fallback
4. builds/applies effective instrument identity from the merged state
5. falls back to generated identity only for symbols missing in both state and workbook

## ProjectState Instrument Map Schema Shape

Schema version remains `1`.

`instrument_map` shape:

```json
{
  "SHOP": {
    "yahoo_symbol": "SHOP",
    "instrument_id": "SHOP_STATE",
    "isin": "STATE000SHOP",
    "instrument_name": "State SHOP",
    "notes": "state map"
  }
}
```

Key is the raw Yahoo symbol/ticker. Payload is intentionally explicit and workbook-compatible.

## Conflict Rule

- `ProjectState` `instrument_map` wins when an entry exists for the raw symbol.
- Workbook `Instrument_Map` rows are fallback only when state has no entry.
- Generated/default identity applies only after both sources are missing.

## Fallback Rule

- normal runtime does not auto-adopt workbook `Instrument_Map` into `.stock_tax_state.json`
- workbook rows remain readable as legacy fallback
- missing map rows still fall back to default generated identity

## Adoption Behavior

Explicit adoption is available through:

`adopt_legacy_workbook_state(project_dir, legacy_state, overwrite=False)`

Behavior:

- copies workbook `Instrument_Map` rows into `.stock_tax_state.json`
- does not overwrite existing `ProjectState` entries by default
- overwrites only when `overwrite=True`

## Workbook Export Behavior

Workbook export writes `Instrument_Map` from the effective merged/canonical runtime map.

If workbook fallback conflicts with `ProjectState`:

- exported `Instrument_Map` reflects `ProjectState`
- stale workbook fallback does not regain ownership
- sheet layout remains unchanged

## API Behavior

Existing API routes continue to work.

Affected outputs now reflect the effective instrument map where that mapping is part of the live calculation path:

- `/api/sales`
- sales detail payloads
- any downstream calculations keyed by `tx.instrument_id`

`/api/open-positions` remains unchanged in shape. In current fixtures, some open-position rows still reflect preserved lot/frozen state keyed by existing `Instrument_ID`s, so this slice does not retroactively rewrite those other workbook-backed domains.

## Tests Added

- `test_project_state_instrument_map_beats_workbook_fallback`
- `test_workbook_instrument_map_fallback_still_works`
- `test_default_generated_instrument_map_still_works`
- `test_explicit_legacy_adoption_migrates_instrument_map_without_overwriting_by_default`
- `test_workbook_export_reflects_project_state_instrument_map`
- `test_api_outputs_reflect_project_state_instrument_map`

## Commands Run

- `py -3 -m pytest -q test_project_state_store.py`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
- `py -3 -m pytest -q`
- backend smoke snippet from the task brief

## Pass/Fail Results

- `py -3 -m pytest -q test_project_state_store.py`
  - pass
  - `15 passed`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
  - pass
  - `27 passed`
- `py -3 -m pytest -q`
  - pass
  - `44 passed`
- backend smoke snippet
  - pass
  - `/api/status` -> `200`
  - `/api/years` -> `200`
  - `/api/sales` -> `200`
  - `/api/open-positions` -> `200`

## Remaining Workbook-Backed Domains

- `corporate_actions`
- `locked_years`
- `frozen_inventory`
- `frozen_lot_matching`
- `frozen_snapshots`
- `filed_year_reconciliation`

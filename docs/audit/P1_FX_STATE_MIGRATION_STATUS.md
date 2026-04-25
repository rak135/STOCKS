# P1.1 FX State Migration Status

## Scope

This slice migrates only FX ownership into backend `ProjectState`:

- `fx_yearly`
- `fx_daily`

Not migrated in this slice:

- `instrument_map`
- `corporate_actions`
- `locked_years`
- `frozen_inventory`
- `frozen_lot_matching`
- `frozen_snapshots`
- `filed_year_reconciliation`

## Old FX Ownership

Before P1.1, runtime FX truth was workbook-primary:

- `FX_Yearly` sheet
- `FX_Daily` sheet
- CNB daily cache JSON as a fill source for missing daily rows
- built-in yearly defaults in `DEFAULT_FX_YEARLY`

`build_stock_tax_workbook.calculate_workbook_data()` loaded workbook rows first and `build_fx_tables()` built runtime FX tables directly from workbook user state.

## New FX Ownership

After P1.1, canonical FX owner is backend `ProjectState` in `.stock_tax_state.json`:

- `fx_yearly`
- `fx_daily`

Normal runtime now:

1. loads workbook user state
2. loads backend `ProjectState`
3. merges `ProjectState` FX over workbook fallback
4. builds effective FX tables from the merged state
5. uses CNB cache/download only to fill still-missing daily rates

## ProjectState FX Schema Shape

Schema version remains `1`.

`fx_yearly` shape:

```json
{
  "2025": {
    "currency_pair": "USD/CZK",
    "rate": 21.84,
    "source_note": "GFŘ-D-75",
    "manual": false
  }
}
```

`fx_daily` shape:

```json
{
  "2020-02-03": {
    "currency_pair": "USD/CZK",
    "rate": 23.55,
    "source_note": "manual override",
    "manual": true
  }
}
```

Keys are the canonical year or ISO date. The entry payload is intentionally small and workbook-compatible.

## Conflict Rule

- `ProjectState` FX wins when an entry exists there.
- Workbook FX sheet rows are fallback only for missing `ProjectState` entries.
- CNB cache/download fills only still-missing daily dates.
- Built-in yearly defaults apply only after both `ProjectState` and workbook fallback are missing.

## Fallback Rule

- No automatic workbook-to-state adoption happens during normal runtime.
- Workbook FX remains readable as legacy fallback.
- P0.3 strictness is preserved:
  - daily mode does not fall back to yearly FX
  - trusted calculation still blocks on required missing FX
  - no generic `22.0` fallback is reintroduced

## Adoption Behavior

Explicit adoption remains available through:

`adopt_legacy_workbook_state(project_dir, legacy_state, overwrite=False)`

Behavior:

- copies workbook `FX_Yearly` and `FX_Daily` into `.stock_tax_state.json`
- does not overwrite existing `ProjectState` FX entries by default
- can overwrite only when explicitly requested with `overwrite=True`

## Workbook Export Behavior

Workbook export writes FX sheets from effective canonical runtime FX:

- `FX_Yearly` writes merged/effective yearly rates
- `FX_Daily` writes merged/effective daily rates
- `Source / note` is now written for both yearly and daily FX rows

Conflicting stale workbook values do not regain ownership after export; exported sheets reflect the merged runtime state with `ProjectState` precedence.

## API Behavior

`GET /api/fx` continues to report the effective FX state used by the engine:

- yearly rate comes from `ProjectState` when present
- workbook fallback is used only when state is missing
- missing daily dates remain visible through `missing_dates`
- blocked strict-FX states still surface through backend status/checks

## Tests Added

- `test_project_state_yearly_fx_beats_workbook_fallback`
- `test_project_state_daily_fx_beats_workbook_fallback`
- `test_workbook_fx_fallback_still_works_when_project_state_missing`
- `test_explicit_legacy_adoption_migrates_fx_without_overwriting_existing_entries`
- `test_project_state_fx_can_unblock_strict_daily_fx`
- `test_missing_fx_still_blocks_after_project_state_merge_path`
- `test_workbook_export_reflects_project_state_fx`

## Commands Run

- `py -3 -m pytest -q test_project_state_store.py`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
- `py -3 -m pytest -q`
- backend smoke snippet from the task brief

## Pass/Fail Results

- `py -3 -m pytest -q test_project_state_store.py`
  - pass
  - `10 passed`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
  - pass
  - `26 passed`
- `py -3 -m pytest -q`
  - pass
  - `38 passed`
- backend smoke snippet
  - pass
  - `/api/status` -> `200`
  - `/api/fx` -> `200`
  - `/api/years` -> `200`

## Remaining Workbook-Backed Domains

- `instrument_map`
- `corporate_actions`
- `locked_years`
- `frozen_inventory`
- `frozen_lot_matching`
- `frozen_snapshots`
- `filed_year_reconciliation`

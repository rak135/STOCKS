# FX Workbook Fallback Retirement Status (P3.4)

Scope: P3.4 - Retire FX_Yearly / FX_Daily workbook fallback from normal runtime.

## 1. Old behavior

Before P3.4, normal runtime merged workbook FX sheets into effective state when ProjectState lacked entries.

- `_merge_fx_yearly_rows` started from workbook `FX_Yearly` rows and overlaid ProjectState.
- `_merge_fx_daily_rows` started from workbook `FX_Daily` rows and overlaid ProjectState.
- `_build_fx_years` and `_daily_rate_source` could report `workbook_fallback` provenance.

Effect: stale workbook FX rows could silently influence runtime yearly and strict-daily FX behavior.

## 2. New ownership

ProjectState is now the runtime owner for FX domains:

- `ProjectState.fx_yearly`
- `ProjectState.fx_daily`

Workbook `FX_Yearly` / `FX_Daily` rows are no longer read as automatic fallback in normal runtime.

## 3. Normal runtime rule

Normal runtime now follows this rule:

- Ignore workbook FX rows during merge.
- Use ProjectState FX rows if present.
- If yearly FX is missing, keep existing generated/default/static behavior from engine policy.
- If strict daily FX is missing, keep existing blocker behavior (no silent fallback).

## 4. Explicit migration path

New helper:

- `project_store.adopt_legacy_workbook_fx(project_dir, workbook_path, overwrite=False)`
- convenience wrapper: `build_stock_tax_workbook.adopt_legacy_workbook_fx(...)`

Behavior:

- Reads workbook `FX_Yearly` and `FX_Daily`.
- Normalizes year/date and currency pair.
- Validates rate and skips invalid rows.
- Writes into `ProjectState.fx_yearly` and `ProjectState.fx_daily`.
- Returns separate summaries for yearly and daily domains.

## 5. Validation and normalization rules

Adoption helper rules:

- Yearly row is valid only when:
  - `Tax year` parses as integer.
  - `USD_CZK` parses as float and `rate > 0`.
  - currency pair normalizes to `USD/CZK`.
- Daily row is valid only when:
  - `Date` parses to ISO date.
  - `USD_CZK` parses as float and `rate > 0`.
  - currency pair normalizes to `USD/CZK`.
- Invalid or ambiguous rows are skipped and counted.

## 6. Conflict and overwrite rules

Runtime precedence:

- ProjectState always wins in normal runtime.
- Workbook FX rows never override automatically.

Adoption precedence:

- `overwrite=False` (default): fill only missing ProjectState keys; count conflicts as skipped.
- `overwrite=True`: replace conflicting ProjectState keys and count overwrites.

## 7. Effective FX resolution order

### Yearly/unified FX

1. `ProjectState.fx_yearly[year]` if present.
2. Existing static/generated/default yearly path (`GFR_OFFICIAL_RATES` / `DEFAULT_FX_YEARLY`) from engine.
3. `unavailable` if no yearly value exists.

There is no workbook yearly fallback step in normal runtime.

### Strict daily FX

1. `ProjectState.fx_daily[date]` coverage for required dates.
2. CNB cache/download path when available via existing refresh behavior.
3. Missing required daily dates remain blocked and reported.

There is no workbook daily fallback step in normal runtime.

## 8. API/status/provenance behavior

- FX provenance no longer emits `workbook_fallback` for FX yearly/daily runtime ownership paths.
- Yearly FX source reports `project_state`, `static_config`, or `unavailable`.
- Strict daily FX source reports `project_state`, `cnb_cache`, or `unavailable`.
- Missing strict-daily coverage continues to surface blocked status and unresolved checks.

## 9. Missing-FX blocker behavior

No tax math was changed.

- Strict daily mode still raises/report-blocks when required daily dates are missing.
- Runtime does not silently consume workbook daily rows anymore.

## 10. Workbook export behavior

Workbook export remains intact.

- Export still writes `FX_Yearly` / `FX_Daily` from canonical effective runtime state.
- Exported workbook is compatibility output, not runtime authority.

## 11. Tests added/updated

Updated:

- `test_p3_4_runtime_ignores_workbook_fx_yearly_when_project_state_missing`

Added in `test_project_state_store.py`:

- `test_p3_4_runtime_ignores_workbook_fx_daily_when_project_state_missing`
- `test_p3_4_adopt_legacy_workbook_fx_migrates_yearly`
- `test_p3_4_adopt_legacy_workbook_fx_migrates_daily_and_unblocks`
- `test_p3_4_adopt_legacy_workbook_fx_overwrite_rules`
- `test_p3_4_adopt_legacy_workbook_fx_skips_invalid_rows_with_counters`
- `test_p3_4_project_state_fx_survives_recalc_and_reload`

Added in `test_stock_tax_app_api.py`:

- `test_p3_4_api_fx_yearly_does_not_use_workbook_fallback_source`
- `test_p3_4_api_strict_daily_still_blocks_when_only_workbook_daily_exists`

Existing export and blocker tests remain green.

## 12. Commands run

- `py -3 -m pytest -q test_project_state_store.py` -> `51 passed`
- `py -3 -m pytest -q test_stock_tax_app_api.py` -> `71 passed`
- `py -3 -m pytest -q test_root_excel_absent.py` -> `4 passed`
- `py -3 -m pytest -q` -> `128 passed`
- `py -3 test_locked_year_roundtrip.py` -> PASS (3-pass roundtrip script succeeded)

No frontend build was run (frontend files were untouched).

## 13. Remaining workbook fallback domains

Intentionally unchanged in this slice:

- `Corporate_Actions`
- `Locked_Years`
- `Frozen_Inventory`
- `Frozen_Lot_Matching`
- `Frozen_Snapshots`
- `Filed_Year_Reconciliation`

## 14. Next recommended slice

Retire `Corporate_Actions` workbook fallback from normal runtime with the same pattern:

- ProjectState-owned runtime semantics.
- Explicit adoption helper for legacy workbook rows.
- Preserve export compatibility.
- Preserve clear provenance and blocker truthfulness.

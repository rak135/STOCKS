# P0 FX Strictness Status

## Scope

This document covers only P0.3: remove silent FX fallback from trusted calculation paths.

Intentionally unchanged:

- workbook-centered persistence architecture
- frontend pages and routing
- year policy ownership
- review-state ownership
- tax formulas other than preventing fake FX inputs

## Old FX Behavior

### FX sources traced

- workbook `FX_Yearly` sheet
- workbook `FX_Daily` sheet
- CNB cache JSON: `cnb_daily_cache.json`
- built-in yearly defaults in `DEFAULT_FX_YEARLY`
- silent fallback values inside `FXResolver.rate_for()`

### Old trusted-path resolution behavior

Before this change, `build_stock_tax_workbook.FXResolver.rate_for()` behaved like this:

- `FX_DAILY_CNB`
  - exact daily rate if present
  - otherwise nearest earlier daily rate within 10 days
  - otherwise yearly FX fallback if available
  - otherwise hardcoded `22.0`
- `FX_UNIFIED_GFR`
  - yearly FX if present
  - otherwise built-in default yearly entry
  - otherwise hardcoded `22.0`

### Trusted call sites traced

`rate_for()` was used in trusted calculation paths for:

- lot ranking for `MIN_GAIN` / `MAX_GAIN`
- building match lines
- global optimizer scoring
- yearly summary inputs via generated match lines

It was also used in non-primary output/display paths such as:

- open-lot cost basis shaping
- workbook review sheets that display CZK amounts

### Old missing-FX check behavior

The old checks could report missing FX facts, but only after fallback values had already been used.

That meant the app could still compute tax-looking numbers from:

- yearly fallback in daily mode
- hardcoded `22.0`

## New Strict Behavior

### Resolver behavior

Trusted FX lookup is now strict:

- `FX_DAILY_CNB`
  - exact date still allowed
  - earlier daily backfill within 10 days is still allowed
  - yearly fallback is no longer used
  - hardcoded `22.0` fallback is no longer used
- `FX_UNIFIED_GFR`
  - explicit yearly rate is required
  - if none exists, lookup is treated as missing

`FXResolver.inspect_date()` now reports whether a required rate is actually available.
`FXResolver.rate_for()` raises a controlled `ValueError` when a required rate is missing instead of returning a fake number.

### Calculation behavior

`calculate_workbook_data()` now performs an FX preflight before trusted matching/tax calculation:

- if required FX is complete, calculation runs normally
- if required FX is missing, trusted calculation is blocked
- missing FX is surfaced as explicit `ERROR` problems:
  - `missing_fx_daily`
  - `missing_fx_yearly`
  - `fx_calculation_blocked`

When blocked:

- status becomes `blocked`
- unresolved FX checks are exposed through the existing checks/status mechanism
- trusted tax outputs are not recomputed from fake FX
- API sales / tax-year / open-position result lists are returned empty rather than pretending values are final

### Workbook/export behavior

- API/runtime `write_workbook=True` now skips workbook writing if calculation is blocked by missing FX.
- direct workbook write path raises a controlled `RuntimeError` with a clear message instead of silently exporting fake results.

## Yearly Fallback Status

Yearly fallback in daily mode is no longer allowed in trusted calculation paths.

Allowed daily behavior now is only:

- exact daily rate
- earlier daily rate within 10 days

No yearly fallback is used for `FX_DAILY_CNB` trusted calculations.

## Hardcoded 22.0 Status

Silent hardcoded `22.0` fallback has been removed from trusted resolution paths.

One explicit `22.0` value still remains:

- `DEFAULT_FX_YEARLY[2026] = 22.00`

This remains as a named table entry with an explicit placeholder comment, not as a silent generic fallback. It is still visible/editable through workbook state and is no longer reached through a generic “otherwise use 22.0” path.

## Files Changed

- `build_stock_tax_workbook.py`
- `stock_tax_app/engine/core.py`
- `test_stock_tax_app_api.py`
- `docs/audit/P0_FX_STRICTNESS_STATUS.md`

## Tests Added

- direct resolver test proving missing daily FX is explicit and never silently returns `22.0`
- direct resolver test proving complete FX still works, including 10-day daily backfill
- API/status test proving missing FX blocks calculation and exposes unresolved FX checks while preserving frontend-safe hrefs
- blocked workbook/export test proving `write_workbook=True` does not silently write fake FX output and direct workbook write fails cleanly

## Commands Run

- `py -3 -m pytest -q test_stock_tax_app_api.py`
  - PASS
  - `23 passed in 13.55s`

- `py -3 -m pytest -q`
  - PASS
  - `25 passed in 13.16s`

- Backend smoke probe

```powershell
@'
from stock_tax_app.backend.main import create_app
from fastapi.testclient import TestClient

app = create_app()
client = TestClient(app)

status = client.get('/api/status')
print('status_code', status.status_code)
print('global_status', status.json().get('global_status'))
print('next_action', status.json().get('next_action'))
print('unresolved_checks', status.json().get('unresolved_checks'))

fx = client.get('/api/fx')
print('fx_status', fx.status_code)
'@ | py -3 -
```

  - PASS
  - observed output:
    - `status_code 200`
    - `global_status needs_review`
    - `next_action {'label': 'Review checks', 'href': '/'}`
    - unresolved checks still exposed normally
    - `fx_status 200`

## Pass/Fail Summary

- P0.3 implementation: PASS
- Focused FX tests: PASS
- Full Python suite: PASS
- Backend smoke probe: PASS

## Remaining Risks

- `DEFAULT_FX_YEARLY` still contains an explicit placeholder entry for 2026 that should be revisited when authoritative yearly data is available.
- When FX is blocked, some API result lists are intentionally empty to avoid fake trusted outputs; richer partial-state UX would need later product/API work.
- Workbook-centered FX persistence remains in place and is outside this P0.3 slice.

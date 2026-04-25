# P0 Stabilization Status

## Scope

This document covers only the implemented P0 stabilization slice:

- P0.1: unify year policy into one source of truth
- P0.4: stop routing operators into placeholder frontend pages

The following were intentionally not changed:

- P0.2 split review-state ownership
- P0.3 FX fallback behavior
- workbook extraction or Excel retirement
- workbook sheet layout
- tax calculation formulas or results
- frontend code or route structure

## What Changed

### P0.1 Year policy canonicalization

- `stock_tax_app.engine.policy` is now the canonical source for:
  - filed years
  - auto-locked years
  - supported matching methods
  - default matching method
  - year-specific default/resolved method behavior
- `2024` remains filed, locked, and resolved to `LIFO`.
- `2025` is now explicitly defined in policy as resolving to `FIFO`.
- `build_stock_tax_workbook.py` no longer defines independent year-policy constants. It uses compatibility aliases derived from `stock_tax_app.engine.policy` and delegates method resolution to policy helpers.

### P0.4 Safe backend href routing

- Backend status/check routing now passes through a frontend-ready allowlist.
- Placeholder destinations are remapped to live pages without hiding unresolved checks.
- Current allowed frontend href targets are:
  - `/`
  - `/import`
  - `/tax-years`

## Policy Source Of Truth

Canonical owner after this change:

- `stock_tax_app/engine/policy.py`

Workbook compatibility wrappers now derive from that module:

- `build_stock_tax_workbook.py`
  - `SUPPORTED_METHODS`
  - `DEFAULT_METHOD`
  - `YEAR_DEFAULT_METHODS`
  - `FILED_YEARS`

## Files Changed

- `stock_tax_app/engine/policy.py`
- `build_stock_tax_workbook.py`
- `stock_tax_app/engine/core.py`
- `test_stock_tax_app_api.py`
- `docs/audit/P0_STABILIZATION_STATUS.md`

## Tests Added Or Updated

- Policy canonical behavior:
  - `2024` filed/locked/LIFO
  - `2025` explicit `FIFO` default/resolution
- Workbook-policy parity regression:
  - workbook aliases derive from engine policy
  - workbook method-selection behavior matches canonical policy for `2024` and `2025`
- Status-routing safety:
  - `GET /api/status` `next_action.href` stays off placeholder routes
  - unresolved checks still appear after href remap
  - unresolved-check hrefs stay within the live route allowlist
  - category mapping never returns placeholder frontend routes

## Commands Run

### Required validation

- `py -3 -m pytest -q`
  - Result: PASS
  - Output summary: `17 passed in 3.22s`

- Backend status smoke probe:
  - Command:

```powershell
@'
from stock_tax_app.backend.main import create_app
from fastapi.testclient import TestClient

app = create_app()
client = TestClient(app)
r = client.get('/api/status')
print(r.status_code)
print(r.json().get('next_action'))
print(r.json().get('unresolved_checks'))
'@ | py -3 -
```

  - Result: PASS
  - Observed output:
    - status code: `200`
    - `next_action`: `{'label': 'Review checks', 'href': '/'}`
    - unresolved checks still present and currently route to `/`

### Additional focused check

- `py -3 -m pytest -q test_stock_tax_app_api.py`
  - Result: PASS
  - Output summary: `15 passed in 3.47s`

- Year-policy runtime probe:
  - Observed `[(2024, 'LIFO', True, True), (2025, 'FIFO', False, False)]`

## Pass/Fail Summary

- P0.1 implementation: PASS
- P0.4 implementation: PASS
- Full Python test suite: PASS
- Backend status smoke probe: PASS

## Behavior Intentionally Not Changed

- Tax calculations and tax results were not changed.
- Workbook support remains in place.
- Workbook sheet layout was not changed.
- Frontend files were not touched.
- Unresolved checks still surface honestly; only their href targets were remapped to live pages.

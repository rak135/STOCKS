# P0 Review State Status

## Scope

This document covers only P0.2: kill split review-state ownership.

Out of scope and intentionally unchanged:

- P0.3 FX fallback behavior
- workbook engine extraction
- Excel removal
- tax formulas and tax outputs
- frontend implementation
- general persistence redesign

## Before Implementation

### Old split ownership

Sale review state was split between:

- backend/API UI state in `stock_tax_app/engine/ui_state.py` persisted to `.ui_state.json`
- legacy workbook state in the `Review_State` sheet via `build_stock_tax_workbook.py`

### Traced flow

- `PATCH /api/sales/{sell_id}/review`
  - `stock_tax_app/backend/routes/sales.py`
  - `BackendRuntime.update_sell_review()`
  - `stock_tax_app.engine.ui_state.load() / save()`
- API response shaping
  - `stock_tax_app/engine/core.py`
  - `run()` loaded `.ui_state.json` after calculation
  - `_build_sales()` layered UI review state onto sells
- Workbook review-state read path
  - `build_stock_tax_workbook.load_existing_user_state()`
  - `build_stock_tax_workbook.load_review_state()`
  - `build_stock_tax_workbook.calculate_workbook_data()`
- Workbook review-state write path
  - `build_stock_tax_workbook.write_calculation_result()`
  - `build_stock_tax_workbook.write_workbook()`
  - `build_stock_tax_workbook._write_review_state()`
  - `build_stock_tax_workbook._write_sell_review()`

### Exact findings

- The API already preferred `.ui_state.json` for review status and sell notes.
- The workbook generator still loaded `Review_State` into `CalculationResult.review_state` and wrote it back out again.
- That meant workbook export could preserve a stale truth even when the API showed a newer truth from `.ui_state.json`.
- Workbook `Review_State` used raw sell IDs such as `Revolut.csv#101`, while API/UI state used canonicalized sell IDs such as `Revolut.csv_101`.
- Result: workbook review export could drift from API review state even without changing tax logic.

### Could workbook override API state after recalc?

Not directly in API responses.

- `engine.core.run()` loaded `.ui_state.json` after workbook calculation and used it when shaping sales.
- So stale workbook `Review_State` did not beat `.ui_state.json` in the API.

But workbook state could still survive independently:

- `calculate_workbook_data()` loaded workbook `Review_State`
- `write_workbook()` wrote that legacy review state back into workbook sheets
- later recalcs could therefore keep exporting stale workbook review values even while API responses showed `.ui_state.json`

## After Implementation

### Canonical owner

Canonical owner is now:

- `stock_tax_app/engine/ui_state.py`

This module now also owns:

- canonical sell ID normalization
- legacy workbook review-state fallback resolution
- export of canonical review state for workbook writers

### New ownership model

- API review status and notes come from `UIState`.
- Workbook `Review_State` is no longer an independent source of truth.
- Workbook export writes canonical backend UI state into:
  - `Review_State`
  - `Sell_Review`

### Legacy workbook fallback

Legacy workbook `Review_State` is kept only as an explicit migration fallback.

Behavior:

- if `.ui_state.json` already has a value for a sell, it wins
- if `.ui_state.json` does not have a value for a sell, legacy workbook `Review_State` is adopted for that sell
- adopted legacy review rows are migrated into `.ui_state.json`
- conflicting workbook rows are ignored rather than merged over backend state

### Conflict rule

Deterministic conflict rule:

- `.ui_state.json` wins over workbook `Review_State` for the same sell ID

This is documented in `stock_tax_app/engine/ui_state.py` and enforced by `load_with_legacy_review_fallback()`.

### Workbook behavior now

- Workbook `Review_State` is still written for compatibility.
- Workbook sheet layout was not changed.
- Export values are sourced from canonical UI state, not from workbook-loaded legacy state.
- Raw workbook sell IDs are preserved on export where available, but lookup is done through canonical sell-ID normalization so workbook and API stay aligned.

## Files Changed

- `stock_tax_app/engine/ui_state.py`
- `stock_tax_app/engine/core.py`
- `build_stock_tax_workbook.py`
- `test_stock_tax_app_api.py`
- `docs/audit/P0_REVIEW_STATE_STATUS.md`

## Tests Added Or Updated

- sale review PATCH survives recalc without workbook write and survives runtime reload
- `.ui_state.json` beats conflicting workbook `Review_State`
- workbook export writes backend UI review state into the `Review_State` sheet
- legacy workbook `Review_State` migrates into `.ui_state.json` when backend state is missing
- existing patch review test still verifies UI-state persistence and tax-year stability

## Commands Run

- `py -3 -m pytest -q test_stock_tax_app_api.py`
  - PASS
  - `19 passed in 11.18s`

- `py -3 -m pytest -q`
  - PASS
  - `21 passed in 11.15s`

- Backend smoke probe

```powershell
@'
from stock_tax_app.backend.main import create_app
from fastapi.testclient import TestClient

app = create_app()
client = TestClient(app)

sales = client.get('/api/sales').json()
sales_count = len(sales if isinstance(sales, list) else sales.get('items', []))
print('sales_count', sales_count)
print('status', client.get('/api/status').status_code)
'@ | py -3 -
```

  - PASS
  - observed output:
    - `sales_count 35`
    - `status 200`

## Pass/Fail Summary

- P0.2 implementation: PASS
- Focused review-state tests: PASS
- Full Python test suite: PASS
- Backend smoke probe: PASS

## Remaining Risks

- Legacy workbook fallback is still present, so workbook `Review_State` has not been deleted yet; it is only demoted to migration input and compatibility export.
- The current smoke probe still exercises repo-root workbook state because backend defaults remain workbook-centered; that broader architecture remains for later phases.
- Filed-year reconciliation input still remains workbook-backed and is outside this P0.2 slice.

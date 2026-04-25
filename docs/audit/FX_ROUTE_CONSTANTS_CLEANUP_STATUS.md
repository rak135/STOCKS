# FX Route Constants Cleanup Status

## Old duplication

- `stock_tax_app/backend/routes/years.py` defined its own local `SUPPORTED_FX_METHODS = ("FX_UNIFIED_GFR", "FX_DAILY_CNB")`.
- `stock_tax_app/engine/fx.py` already defined the FX runtime source-of-truth tuple.

## New source of truth

- `stock_tax_app.engine.fx.SUPPORTED_FX_METHODS` is now the single source of truth used by the backend year route validation.

## Files changed

- `stock_tax_app/backend/routes/years.py`
- `test_stock_tax_app_api.py`
- `docs/audit/FX_ROUTE_CONSTANTS_CLEANUP_STATUS.md`

## Tests added or updated

- Added `test_api_patch_year_rejects_invalid_fx_method` to cover invalid year-route FX method validation.
- Existing `test_api_patch_year_updates_fx_method_for_unlocked_year` remained unchanged and still passes.

## Commands run

- `py -3 -m pytest -q test_stock_tax_app_api.py::test_api_patch_year_updates_fx_method_for_unlocked_year`
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_api_patch_year_rejects_invalid_fx_method`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
- `py -3 -m pytest -q test_project_state_store.py`
- `py -3 -m pytest -q`

## Results

- `test_api_patch_year_updates_fx_method_for_unlocked_year`: pass
- `test_api_patch_year_rejects_invalid_fx_method`: pass
- `test_stock_tax_app_api.py`: `62 passed`
- `test_project_state_store.py`: `22 passed`
- Full pytest suite: `86 passed`

## Behavior preservation notes

- Allowed FX method values remain unchanged: `FX_UNIFIED_GFR` and `FX_DAILY_CNB`.
- Year mutation behavior is unchanged.
- The route still uppercases the incoming value and validates against the same allowed set.
- Error status and error message format for invalid `fx_method` remain unchanged.

## Remaining FX duplication

- No remaining duplicate `SUPPORTED_FX_METHODS` tuple was found in `stock_tax_app/backend/routes/years.py` after this cleanup.
- Other FX constants and logic already use `stock_tax_app/engine/fx.py` after the prior FX ownership cleanup.

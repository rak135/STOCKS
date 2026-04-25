# FX Clean Wiring Status

## Old split ownership

- `build_stock_tax_workbook.py` still owned active FX runtime logic.
- `stock_tax_app/engine/fx.py` already existed and was used by extracted modules.
- Result: extracted modules used engine FX ownership, but monolith compatibility/runtime paths still duplicated FX constants, CNB cache helpers, FX table building, FX resolution, and required-FX preflight logic.

## New owner

- `stock_tax_app/engine/fx.py` is now the single owner of FX runtime logic.
- `build_stock_tax_workbook.py` keeps compatibility names only as aliases or thin wrappers.

## Constants, functions, and wrappers changed

- `build_stock_tax_workbook.py`
- `DEFAULT_FX_METHOD` now aliases `stock_tax_app.engine.fx.DEFAULT_FX_METHOD`
- `SUPPORTED_FX_METHODS` now aliases `stock_tax_app.engine.fx.SUPPORTED_FX_METHODS`
- `DEFAULT_FX_YEARLY` now aliases `stock_tax_app.engine.fx.DEFAULT_FX_YEARLY`
- `GFR_OFFICIAL_RATES` now aliases `stock_tax_app.engine.fx.GFR_OFFICIAL_RATES`
- `CNB_DAILY_CACHE_FILE` now aliases `stock_tax_app.engine.fx.CNB_DAILY_CACHE_FILE`
- `FXResolver` now aliases `stock_tax_app.engine.fx.FXResolver`
- `build_fx_tables(...)` now delegates to `stock_tax_app.engine.fx.build_fx_tables(...)` and injects `parse_trade_date` and `_to_bool`
- `_cnb_cache_path(...)` now delegates to `stock_tax_app.engine.fx.cnb_cache_path(...)`
- `_load_cnb_cache(...)` now delegates to `stock_tax_app.engine.fx.load_cnb_cache(...)`
- `_save_cnb_cache(...)` now delegates to `stock_tax_app.engine.fx.save_cnb_cache(...)`
- `download_cnb_daily_rates_year` now aliases `stock_tax_app.engine.fx.download_cnb_daily_rates_year`
- `refresh_fx_daily_for_years(...)` now delegates to `stock_tax_app.engine.fx.refresh_fx_daily_for_years(...)`
- `collect_required_fx_problems(...)` now delegates to `stock_tax_app.engine.fx.collect_required_fx_problems(...)`

## Strict FX behavior preservation notes

- `stock_tax_app/engine/fx.py` already matched the prior monolith FX runtime behavior before this cleanup.
- `FX_DAILY_CNB` still resolves only an exact daily rate or an earlier daily backfill within the existing 10-day window.
- `FX_DAILY_CNB` still does not silently fall back to yearly FX in trusted calculation.
- `FX_UNIFIED_GFR` still requires an actual yearly rate.
- Missing required FX still produces explicit `missing_fx_daily`, `missing_fx_yearly`, and `fx_calculation_blocked` problems.
- Trusted calculation still blocks when required FX is unavailable; no silent yearly fallback or generic `22.0` fallback was reintroduced.
- `/api/status` and `/api/fx` behavior stayed intact, including rate source and provenance expectations covered by tests.
- The `DEFAULT_FX_YEARLY[2026]` placeholder remains only as the explicit configured yearly placeholder entry.

## Duplicated logic removed from build_stock_tax_workbook.py

- FX constants
- yearly and daily FX table construction
- CNB cache path and JSON cache read/write logic
- CNB yearly daily-rate download logic
- daily refresh orchestration
- FX resolver implementation
- required-FX preflight problem construction

## Compatibility note

- Focused FX tests monkeypatch `build_stock_tax_workbook.download_cnb_daily_rates_year`.
- To preserve that public patch point while making `engine/fx.py` the logic owner, `stock_tax_app.engine.fx.refresh_fx_daily_for_years(...)` now accepts optional injected helper callables and the monolith wrapper passes the compatibility names through.

## Tests run

- `py -3 -m pytest -q test_stock_tax_app_api.py -k "fx or FX or missing"`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
- `py -3 -m pytest -q test_project_state_store.py`
- `py -3 -m pytest -q`
- `py -3 test_locked_year_roundtrip.py`
- `py -3 verify_workbook.py stock_tax_system.xlsx`

## Results

- Focused FX tests: `13 passed, 48 deselected`
- `test_stock_tax_app_api.py`: `61 passed`
- `test_project_state_store.py`: `22 passed`
- Full pytest suite: `85 passed`
- `test_locked_year_roundtrip.py`: pass
- `verify_workbook.py stock_tax_system.xlsx`: validation passed

## Remaining extraction risks

- `build_stock_tax_workbook.py` still exposes compatibility aliases and wrappers, so stale callers can still depend on monolith names until a later deliberate migration removes them.
- `stock_tax_app.engine.fx.refresh_fx_daily_for_years(...)` now has optional helper injection parameters solely to preserve compatibility patch points; future cleanup should only remove them after callers and tests stop relying on monolith hook names.
- `stock_tax_app/backend/routes/years.py` still carries its own local `SUPPORTED_FX_METHODS` tuple; that was left untouched in this slice because it is outside the requested narrow FX runtime cleanup.

# Corporate Actions Extraction Status

Date: 2026-04-25

## Scope

Behavior-preserving structural extraction only.

No changes were made to:
- tax formulas
- ProjectState schema
- API models
- frontend
- workbook sheet layout
- non-corporate domains (FX/matching/open-positions broad logic)

## What Was Extracted

New module:
- `stock_tax_app/engine/corporate_actions.py`

Extracted functions/constants:
- `CA_TYPES`
- `_is_blank_corporate_action_row`
- `_corporate_action_issue`
- `_parse_target_from_note`
- `build_corporate_actions`
- `apply_corporate_action_to_lots`

## Integration in Workbook Engine

`build_stock_tax_workbook.py` now imports extracted logic from `stock_tax_app.engine.corporate_actions`.

`build_stock_tax_workbook.py` retains thin wrappers:
- `build_corporate_actions(...)` delegates to extracted `build_corporate_actions(...)`
- `apply_corporate_action_to_lots(...)` delegates to extracted `apply_corporate_action_to_lots(...)`

The wrapper for `build_corporate_actions` passes existing workbook helpers (`parse_trade_date`, `_coerce_float`, `_to_bool`, `_to_float`) into the extracted module to preserve parsing/coercion behavior exactly.

## What Intentionally Stayed in build_stock_tax_workbook.py

Stayed because they are shared outside corporate actions or are workbook orchestration:
- `parse_trade_date` (shared date parsing behavior)
- `_to_bool`, `_to_float` (generic workbook coercion helpers)
- `_coerce_float` (used through wrapper injection for exact existing behavior)
- call sites in calculation/simulation flow (`calculate_workbook_data`, `simulate`)
- workbook data validation usage of `CA_TYPES` remains unchanged via imported constant

No open-position provenance logic was moved.

## Behavior Preservation Notes

- Corporate-action parsing accepts both legacy workbook and ProjectState-converted row keys.
- Duplicate `action_id` diagnostics remain end-to-end functional.
- Validation issue categories/messages are unchanged.
- Corporate-action lot application logic (split/reverse_split/ticker_change) is unchanged.

## Files Changed

1. `stock_tax_app/engine/corporate_actions.py` (new)
2. `build_stock_tax_workbook.py` (imports + wrapper delegation)
3. `docs/audit/CORPORATE_ACTIONS_EXTRACTION_STATUS.md` (this document)

## Tests Run

1. `py -3 -m pytest -q test_stock_tax_app_api.py::test_invalid_corporate_actions_surface_in_status_and_audit`
- Result: PASS (1 passed)

2. `py -3 -m pytest -q test_stock_tax_app_api.py`
- Result: PASS (58 passed)

3. `py -3 -m pytest -q test_project_state_store.py`
- Result: PASS (22 passed)

4. `py -3 -m pytest -q`
- Result: PASS (82 passed)

## Remaining Refactor Candidates

Small, low-risk next slices (not done here):
- Move wrapper-level helper-injection boilerplate into a tiny adapter function to keep workbook file cleaner.
- Add focused unit tests directly for `stock_tax_app/engine/corporate_actions.py` to decouple future changes from monolithic workbook tests.

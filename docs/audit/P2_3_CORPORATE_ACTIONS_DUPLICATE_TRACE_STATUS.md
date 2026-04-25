# P2.3 Corporate Actions Duplicate action_id Trace Status

Date: 2026-04-25

## Summary

The duplicate action_id did not disappear in state storage loading. It disappeared during ProjectState-to-legacy merge conversion for Corporate_Actions rows.

## End-to-end Trace

### 1) Raw .stock_tax_state.json
- Preserved both duplicate rows.
- Preserved duplicate action_id values.

### 2) load_project_state(project_dir)
- Preserved both duplicate rows in ProjectState.corporate_actions.
- Preserved action_id values.

### 3) merge_project_state_with_legacy_fallback(project_state, legacy_state)
- Row count remained 4.
- Disappearance point: _project_state_action_to_legacy_row did not include Action ID/action_id in merged legacy rows.
- Result: merged user_state["Corporate_Actions"] rows had no action_id field, so downstream duplicate-id validator had no key to compare.

### 4) build_corporate_actions(...)
- Before fix: received rows with no action_id key and therefore did not emit corporate_action_duplicate_action_id.
- After fix: received rows including Action ID and emitted corporate_action_duplicate_action_id as expected.

### 5) calculate_workbook_data(...)
- After fix: duplicate-id issue appears in calculation problems.

### 6) engine status/audit mapping
- No code change required in mapping.
- After action_id preservation fix, existing mapping surfaces the issue through /api/status unresolved_checks and /api/audit status_reasons.

## Exact Fix Made

File changed:
- stock_tax_app/state/project_store.py

Function changed:
- _project_state_action_to_legacy_row

Change:
- Added extraction of action_id from ProjectState action.
- Added legacy-row field "Action ID" carrying that value.

Why this is the correct minimal fix:
- build_corporate_actions already validates duplicate IDs using Action ID/action_id keys.
- The duplicate diagnostic path failed only because merge conversion dropped the identifier.
- Preserving Action ID at conversion keeps validation downstream where it belongs.

## Files Changed

1. stock_tax_app/state/project_store.py
2. docs/audit/P2_3_CORPORATE_ACTIONS_DUPLICATE_TRACE_STATUS.md

## Tests Run

1. py -3 -m pytest -q test_stock_tax_app_api.py::test_invalid_corporate_actions_surface_in_status_and_audit
- PASS (1 passed)

2. py -3 -m pytest -q test_stock_tax_app_api.py
- PASS (58 passed)

3. py -3 -m pytest -q test_project_state_store.py
- PASS (22 passed)

4. py -3 -m pytest -q
- PASS (82 passed)

## Repository Status

- Repo is now green.
- Duplicate action_id validation now survives end-to-end and is observable in status/audit diagnostics.

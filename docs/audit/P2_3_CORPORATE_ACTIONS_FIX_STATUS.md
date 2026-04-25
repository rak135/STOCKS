# P2.3 Corporate Actions Duplicate action_id Fix Status

Date: 2026-04-25

## Scope Requested

Apply only a scoped fix in `stock_tax_app/state/project_store.py`, function `_normalize_corporate_actions_payload`, to remove silent deduplication and preserve duplicate entries for downstream validation.

## What Was Wrong

`_normalize_corporate_actions_payload` previously used a `seen` set and `_corporate_action_identity_key(...)` to deduplicate normalized corporate action entries during storage normalization.

That behavior removed duplicate `action_id` entries too early, which conflicts with the intended design: duplicate detection should happen in downstream validation (`build_corporate_actions`) where issues are surfaced to API status/audit checks.

## Exact Function Changed

- File: `stock_tax_app/state/project_store.py`
- Function: `_normalize_corporate_actions_payload`
- Change made:
  - Removed `seen` set creation
  - Removed identity-key lookup
  - Removed duplicate skip branch
  - Kept normalization/filtering of blank entries via `_normalize_corporate_action_entry`

Resulting behavior of this function now:
- normalizes names/values
- filters blank/invalid entries (same as before)
- preserves multiple rows even with same `action_id`

## Why Validation Belongs Downstream

Storage normalization should not perform semantic validation or data-loss deduplication.

`build_corporate_actions` is the validation layer that emits explicit issue records (including duplicate `action_id`) used by `/api/status` and `/api/audit` reporting. Preserving raw normalized entries until that stage is required for transparent operator diagnostics.

## Commands Run

1. `py -3 -m pytest -q test_stock_tax_app_api.py::test_invalid_corporate_actions_surface_in_status_and_audit`
   - Result: FAIL
   - Failure: expected unresolved check containing "duplicate action_id" not found.

2. `py -3 -m pytest -q test_stock_tax_app_api.py`
   - Result: FAIL (1 failed, 57 passed)
   - Only failing test: `test_invalid_corporate_actions_surface_in_status_and_audit`

3. `py -3 -m pytest -q test_project_state_store.py`
   - Result: PASS (22 passed)

4. `py -3 -m pytest -q`
   - Result: FAIL (1 failed, 81 passed)
   - Only failing test: `test_invalid_corporate_actions_surface_in_status_and_audit`

## Pass/Fail Summary

- Targeted test: FAIL
- API module: FAIL (single test)
- Project state store module: PASS
- Full suite: FAIL (single test)

## Current Conclusion

The requested dedup-removal fix in `_normalize_corporate_actions_payload` is implemented correctly and safely, but by itself it is not sufficient to make the duplicate `action_id` API assertion pass in this repository snapshot.

There is still an additional downstream path where `action_id` does not reach validation diagnostics for status checks, so duplicate detection is not currently observable in `/api/status` unresolved messages for this test case.

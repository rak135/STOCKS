# Soft Lock Snapshot Policy Status

## Old behavior

- The matcher seeded from the latest locked year that had any frozen snapshot data.
- If an earlier year was newly locked without its own snapshot, the engine still seeded from the later snapshot.
- That skipped the earlier year's buys and could cascade into `insufficient_lots` / unmatched sells.
- `Locked_Years` and policy comments also still described lock state as effectively permanent for filed years.

## New soft-lock product decision

- Locks are soft locks only.
- An explicit unlock is allowed by lower-level backend policy.
- `build_locked_years()` now treats policy lock state as the default only; an explicit workbook lock row can override it.
- `policy.check_unlock()` now reflects the soft-lock rule and no longer treats unlock as permanently forbidden.

## Snapshot invalidation / rebuild policy implemented

- If year `X` is locked or otherwise lacks a valid matching snapshot while a later locked frozen snapshot year `Y` exists, the engine emits an explicit rebuild-required error.
- Later snapshot years marked by that condition are not trusted for seed selection.
- Later frozen matching rows for those stale years are also skipped, so the engine does not silently reuse stale frozen audit data.
- `Frozen_Snapshots` now persists stale status metadata so later runs keep surfacing the rebuild requirement instead of silently trusting stale snapshots.

## Check code and message

- Check code: `locked_year_snapshot_rebuild_required`
- Current message shape:
  `Year X was changed or locked without a matching snapshot while later frozen snapshot year(s) Y exist. Those later snapshots may be stale. Rebuild/recalculate frozen snapshots from X onward is required.`

## What `test_locked_year_roundtrip.py` verifies now

- Runs entirely inside a temp sandbox.
- Never mutates the root `stock_tax_system.xlsx`.
- Baseline build still succeeds in the sandbox.
- Locking 2020 under the fixture's existing 2024 frozen snapshot produces a controlled build failure with explicit `locked_year_snapshot_rebuild_required` output.
- The failure message mentions both the changed year (`2020`) and the later snapshot year (`2024`).
- Explicit unlock of 2020 is still possible afterward, and the sandbox rebuild succeeds again.

## Files changed

- `build_stock_tax_workbook.py`
- `stock_tax_app/engine/matching.py`
- `stock_tax_app/engine/policy.py`
- `stock_tax_app/engine/workbook_export.py`
- `test_locked_year_roundtrip.py`
- `test_stock_tax_app_api.py`
- `docs/audit/SOFT_LOCK_SNAPSHOT_POLICY_STATUS.md`

## Commands run

- `py -3 test_locked_year_roundtrip.py`
  Result: PASS. The script now expects and validates the explicit controlled rebuild-required failure, then verifies explicit unlock in the sandbox.
- `py -3 -m pytest -q test_stock_tax_app_api.py`
  Result: PASS (`61 passed`).
- `py -3 -m pytest -q test_project_state_store.py`
  Result: PASS (`22 passed`).
- `py -3 -m pytest -q`
  Result: PASS (`85 passed`).
- `py -3 verify_workbook.py stock_tax_system.xlsx`
  Result: PASS. Root workbook integrity checks succeeded with `Checks` ERROR rows = `0`.
- `git status --short`
  Result: root `stock_tax_system.xlsx` was not modified.

## Pass / fail summary

- Roundtrip script: PASS
- Targeted API tests: PASS
- Targeted project-state tests: PASS
- Full pytest: PASS
- Root workbook verification: PASS

## Remaining gap

- This is the conservative safety implementation, not a full rebuild pipeline.
- The engine now detects and persists stale later snapshots and refuses to trust them automatically.
- It does not yet regenerate later frozen inventory/matching snapshots automatically once they are marked stale; an explicit rebuild workflow from the changed year onward is still needed.
- The API/UI still does not expose a dedicated unlock-and-rebuild flow, so the soft-lock policy is currently covered at the lower-level workbook/policy path rather than a full end-user workflow.

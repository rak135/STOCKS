# Locked Year Roundtrip Investigation Status

Timestamp: 2026-04-25T14:23:44.1579491+02:00

## Summary

`test_locked_year_roundtrip.py` does not pass.

The failure is not caused by the previously restored workbook-export compatibility wrappers.
The failure reproduces even when the script runs in an isolated temp copy.

Root cause found:
- the script tries to lock `2020`
- the workbook fixture already has `2024` locked with frozen snapshots for `2024` only
- current matching/snapshot logic seeds from the latest locked year that already has frozen data
- when `2020` is flipped to locked without a `2020` frozen baseline, `matching.py` skips `2020` transactions from historical replay and cannot regenerate a valid `2020` snapshot in that run
- `checks.py` then emits `locked_year_no_snapshot`, and several sells that depend on 2020 buy lots become unmatched

This is a matching/snapshot behavior issue surfaced by the roundtrip scenario, not a workbook-export replace/rename bug.

## What The Script Does

Before fix:
- used the root `stock_tax_system.xlsx`
- used root `.csv/*` files
- ran `build_stock_tax_workbook.py` against the root workbook
- set `Locked_Years[2020] = TRUE`
- expected pass 2 to create frozen `2020` rows in `Frozen_Inventory` and `Frozen_Lot_Matching`
- then changed `FX_Yearly[2020]` to `30.0` and expected pass 3 tax to stay unchanged
- only restored FX/unlock state at the very end

Unsafe behavior before fix:
- if pass 2 failed, the script exited without restoring the root workbook
- this left fixture drift behind (`2020` stayed locked)

After fix:
- the script now copies the workbook and CSV inputs into a temp sandbox
- all mutation happens only inside that sandbox
- the root workbook is no longer mutated by the script

## Root Workbook Mutation Check

Verified root workbook state before and after the isolated script run:
- `Locked_Years`: `2020=False`, `2024=True`
- `Frozen_Snapshots`: only `2024`
- `Frozen_Inventory`: only `2024`
- `Frozen_Lot_Matching`: only `2024`
- `Checks`: 6 rows, 0 errors

Conclusion:
- before fix, the script mutated the root workbook and was not safe on failure
- after fix, the root fixture is safe for repeated runs of this script

## Exact Failure Result

Command:
- `py -3 test_locked_year_roundtrip.py`

Result:
- FAIL on pass 2

Failure output highlights:
- `locked_year_no_snapshot: Year 2020 marked Locked but no frozen snapshot manifest exists yet.`
- 6 unmatched sells over tolerance
- `Validation failed for temporary workbook; requested output was not replaced.`

The failing temporary workbook showed:
- `Checks` sheet: 10 rows, 5 errors
- `Open_Position_Check`: 0 errors
- `Filed_Year_Reconciliation`: 0 errors
- `Lot_Matching`: unmatched sells for:
  - `XTB_CZK.csv#31`
  - `Revolut.csv#82`
  - `Revolut.csv#93`
  - `Revolut.csv#94`
  - `Revolut.csv#95`
  - `Revolut.csv#101`

## Traced Root Cause

### 1. Snapshot / seed-year behavior

In `stock_tax_app/engine/matching.py`:
- `snapshot_years` is built from `frozen_snapshots` and `frozen_inventory`
- `seed_year` is chosen as the latest locked year with frozen data
- with the fixture, that year is `2024`

Relevant path:
- `matching.py:401-424`

### 2. Historical replay exclusion

Still in `matching.py`:
- historical replay only includes years `< seed_year` that are **not** locked
- once the script sets `2020=True`, 2020 transactions are excluded from historical replay

Relevant path:
- `matching.py:435-465`

### 3. Why sells become unmatched

The unmatched sells in the failing temp workbook are matched in the good root workbook against 2020 buys:
- `XTB_CZK.csv#31` matched to buy date `2020-12-10`
- `Revolut.csv#82` matched to buy dates `2020-10-21`, `2020-04-01`, `2020-03-20`
- `Revolut.csv#94` matched to buy date `2020-03-17`
- `Revolut.csv#93` matched to buy date `2020-03-17`
- `Revolut.csv#95` matched to buy date `2020-07-16`
- `Revolut.csv#101` matched to buy date `2020-02-03`

Because `2020` becomes locked without a corresponding frozen baseline, those 2020 lots are not recreated for pass 2.

### 4. Why `locked_year_no_snapshot` appears

In `stock_tax_app/engine/checks.py`:
- `manifest_years` only includes existing frozen snapshots plus `year_end_inventory` for locked years produced in the current run
- because the run seeded from `2024` and excluded locked `2020` historical transactions, `year_end_inventory` does not include `2020`
- therefore `2020` remains locked with no manifest and the check becomes an error

Relevant path:
- `checks.py:124-137`

## Cause Classification

Investigation conclusion:
- `1. caused by mutated fixture state` -> previously yes as a side effect, but not the underlying failure once isolated
- `2. caused by phase 7 workbook export extraction` -> no evidence
- `3. caused by matching/snapshot behavior regression` -> yes, this is the active runtime failure path
- `4. caused by the script itself using unsafe production fixture state` -> yes, independently true and fixed in this slice
- `5. already fixed by the restored fixture state` -> no

## Files Changed

- `test_locked_year_roundtrip.py`
- `docs/audit/LOCKED_YEAR_ROUNDTRIP_INVESTIGATION_STATUS.md`

No engine logic, tax formulas, workbook layout, frontend, or API contract code was changed in this investigation slice.

## Commands Run And Results

1. `git status --short`
- completed

2. `git diff --stat`
- completed

3. `py -3 -m pytest -q`
- PASS (`82 passed`)

4. `py -3 test_locked_year_roundtrip.py`
- FAIL (reproduced before and after script isolation)

5. Root workbook inspection before/after script
- root workbook unchanged after isolated run

6. `py -3 -m pytest -q test_stock_tax_app_api.py`
- PASS (`58 passed`)

7. `py -3 -m pytest -q test_project_state_store.py`
- PASS (`22 passed`)

8. `py -3 -m pytest -q`
- PASS (`82 passed`)

9. `py -3 verify_workbook.py stock_tax_system.xlsx`
- PASS

## Fixture Safety Status

Safe now:
- yes, for repeated script runs

Why:
- the script now uses an isolated temp copy and does not leave root fixture drift behind on failure

## Remaining Risks

1. The roundtrip scenario still fails functionally when trying to newly lock `2020` while `2024` is already the latest frozen locked year.
2. The exact product decision is still unresolved: should the engine support backfilling an older newly locked year when a later locked snapshot already exists?
3. Because this investigation did not change engine behavior, the underlying roundtrip failure remains open.

## Next Recommended Action

Investigate the locked-year engine behavior in `matching.py` and related snapshot generation logic as a dedicated bug fix:
- define the intended behavior for newly locking an earlier year when a later frozen locked year already exists
- then implement the minimal engine fix and revalidate with:
  - `py -3 test_locked_year_roundtrip.py`
  - `py -3 -m pytest -q`

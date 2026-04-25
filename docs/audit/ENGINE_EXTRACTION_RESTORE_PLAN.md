# Engine Extraction Restore Plan

Timestamp: 2026-04-25T14:11:38.9386004+02:00

This plan is based only on verification findings. No fixes were applied.

## 1. Failing Commands

### Failure A

Command:
- `py -3 -m pytest -q test_stock_tax_app_api.py`
- `py -3 -m pytest -q`
- `py -3 -m pytest -q test_stock_tax_app_api.py -k "year or tax or exemption or audit"`

Failure text:
```text
AttributeError: module 'build_stock_tax_workbook' has no attribute '_replace_output_or_fail'
```

Likely responsible phase/file:
- Phase 7
- `build_stock_tax_workbook.py`
- `stock_tax_app/engine/workbook_export.py`

Minimal restore/fix plan:
1. Restore backward-compatible monolith wrappers or re-exports for:
`_tmp_output_path`, `_backup_existing_output`, `_replace_output_or_fail`
2. Keep the wrappers thin and delegating into `stock_tax_app.engine.workbook_export`.
3. Do not change workbook behavior while restoring these symbols.

Commands to revalidate:
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_locked_output_fails_without_alternate_workbook`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
- `py -3 -m pytest -q`

### Failure B

Command:
- `py -3 test_locked_year_roundtrip.py`

Failure text excerpt:
```text
Checks sheet contains ERROR rows.
Unmatched SELL quantity exceeds tolerance.
locked_year_no_snapshot: Year 2020 marked Locked but no frozen snapshot manifest exists yet.
Validation failed for temporary workbook; requested output was not replaced.
```

Likely responsible phase/file:
- Phase 7 integration, with possible phase 3 / phase 5 interaction
- `stock_tax_app/engine/workbook_export.py`
- `build_stock_tax_workbook.py`
- possibly `stock_tax_app/engine/matching.py` and/or check generation around locked-year snapshots

Minimal restore/fix plan:
1. Reproduce only `py -3 test_locked_year_roundtrip.py` in a clean temp copy after fixing failure A.
2. Compare pass-1 and pass-2 rebuild behavior for:
`Frozen_Inventory`, `Frozen_Lot_Matching`, `Frozen_Snapshots`, `Checks`, `Lot_Matching`.
3. Verify whether the locked-year snapshot is being generated during the rebuild but still flagged as missing by pre-write checks.
4. Verify whether the unmatched SELL rows are a simulation regression or only a validation/input-selection issue after locking.
5. Do not continue any further extraction until the roundtrip script passes again.

Commands to revalidate:
- `py -3 test_locked_year_roundtrip.py`
- `py -3 verify_workbook.py stock_tax_system.xlsx`
- `py -3 -m pytest -q`

## 2. Structural Restore Priorities

1. Restore green test status before any more refactor work.
2. Reconcile phase 7 boundary issues:
`workbook_export.py` should not become a second home for phase 2 open-position logic.
3. Decide whether to finish or roll back incomplete phase 2/3/4 extraction wiring:
- phase 2: wire monolith wrappers to `open_positions.py`
- phase 3: replace monolith `build_check_rows` with a thin wrapper
- phase 4: replace monolith FX runtime ownership with thin wrappers/re-exports
4. Update or recreate extraction status docs only after the repo is green.

## 3. Revalidation Sequence

Run in this order after the minimal restore:

1. `py -3 -m pytest -q test_stock_tax_app_api.py::test_locked_output_fails_without_alternate_workbook`
2. `py -3 -m pytest -q test_project_state_store.py`
3. `py -3 -m pytest -q test_stock_tax_app_api.py`
4. `py -3 -m pytest -q test_min_gain_optimality.py`
5. `py -3 test_locked_year_roundtrip.py`
6. `py -3 -m pytest -q`
7. `py -3 verify_workbook.py stock_tax_system.xlsx`
8. `npm run build` in `ui/frontend`

If all of the above pass, re-run backend smoke and only then consider launcher smoke.

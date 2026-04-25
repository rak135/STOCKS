# Engine Extraction Restore Status

Timestamp: 2026-04-25T14:23:44.1579491+02:00

## Summary

This restore slice fixed the backward-compatible workbook-export helper surface expected from `build_stock_tax_workbook.py`.

Broken before restore:
- full API/full pytest were failing because `build_stock_tax_workbook._replace_output_or_fail` no longer existed after phase 7 extraction work

Additional fixture-state issue found during validation:
- the root workbook fixture `stock_tax_system.xlsx` had `Locked_Years[2020] = TRUE` while frozen sheets only contained `2024`
- this matched prior validation drift from the interrupted `test_locked_year_roundtrip.py` run and caused unrelated API tests to fail against a mutated fixture copy
- the fixture state was restored minimally by setting 2020 back to unlocked

## Exact Wrappers Restored

Restored in `build_stock_tax_workbook.py` as thin delegations to `stock_tax_app.engine.workbook_export`:
- `_tmp_output_path(out_path)`
- `_backup_existing_output(out_path)`
- `_replace_output_or_fail(temp_path, out_path)`

These wrappers do not duplicate implementation logic.

## Files Changed

- `build_stock_tax_workbook.py`
- `docs/audit/ENGINE_EXTRACTION_RESTORE_STATUS.md`
- `stock_tax_system.xlsx` fixture state restored locally for test correctness

## Tests Run

1. `py -3 -m pytest -q test_stock_tax_app_api.py::test_locked_output_fails_without_alternate_workbook`
- PASS (`1 passed`)

2. `py -3 -m pytest -q test_stock_tax_app_api.py`
- PASS (`58 passed`)

3. `py -3 -m pytest -q test_project_state_store.py`
- PASS (`22 passed`)

4. `py -3 -m pytest -q`
- PASS (`82 passed`)

## Result

Full pytest is green: yes.

## Remaining Issues Not Addressed

- `test_locked_year_roundtrip.py` was not investigated or rerun in this slice.
- Phase 2/3/4/7 extraction boundary problems identified in the verification report were not addressed.
- No additional extraction work, workbook layout changes, frontend changes, or behavior changes were made here.

## Next Action

Now that full pytest is green, investigate `test_locked_year_roundtrip.py` separately using the restore/verification docs as the baseline, without expanding the scope into further extraction work.

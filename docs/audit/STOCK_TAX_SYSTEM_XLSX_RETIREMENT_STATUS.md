# STOCK_TAX_SYSTEM_XLSX_RETIREMENT_STATUS

## Summary

- Goal of this slice: remove the repo-root `stock_tax_system.xlsx` from normal runtime and automated test dependency paths without deleting workbook export support.
- Result: backend/API now runs without the root workbook present, automated tests no longer copy or mutate the root workbook, and `POST /api/recalculate` no longer writes a workbook by default.
- Root `stock_tax_system.xlsx` is still kept as a legacy/export artifact and manual validation target.

## Changes Made

- `stock_tax_app/backend/main.py`
  - Changed `POST /api/recalculate` from `runtime.calculate(write_workbook=True)` to `runtime.calculate(write_workbook=False)`.
- `test_stock_tax_app_api.py`
  - Stopped copying the repo-root workbook into temp projects.
  - Added temp-workbook generation helper that builds `stock_tax_system.xlsx` only when a test explicitly needs workbook sheets.
  - Added `test_api_runs_without_root_workbook_and_only_exports_explicitly`.
- `test_project_state_store.py`
  - Stopped copying the repo-root workbook into temp projects.
  - Added temp-workbook generation helper for workbook-fallback/export tests.
- `test_locked_year_roundtrip.py`
  - Stopped copying the repo-root workbook into the sandbox.
  - The script now creates its workbook by running the builder inside the temp sandbox.

## Reference Audit

### Runtime default output

- `stock_tax_app/backend/main.py:21`
  - Backend default `output_path` is still `project / "stock_tax_system.xlsx"`.
  - Classification: runtime default output.
- `build_stock_tax_workbook.py:72,1467-1489`
  - Canonical output name and CLI `--output` default remain `stock_tax_system.xlsx`.
  - Classification: workbook export output.
- `verify_workbook.py:159`
  - Default path argument is still `stock_tax_system.xlsx`.
  - Classification: manual script / explicit legacy validation.

### API/backend calculation input or optional workbook fallback

- `build_stock_tax_workbook.py:444-458`
  - `load_existing_user_state(path)` reads workbook sheets only if the output workbook exists; missing workbook returns `{}`.
  - Classification: API/backend optional legacy fallback.
- `build_stock_tax_workbook.py:1200-1298`
  - `calculate_workbook_data(...)` merges `ProjectState` with optional legacy workbook state and loads UI state next to the workbook path.
  - Classification: API/backend optional legacy fallback.
- `stock_tax_app/engine/core.py:1267-1289`
  - Engine resolves the output path, calculates from CSV/project state, then optionally loads workbook fallback state if a workbook exists.
  - Classification: API/backend optional legacy fallback.
- `stock_tax_app/engine/ui_state.py:149-190`
  - `.ui_state.json` is stored next to the workbook path, but workbook existence is not required.
  - Classification: backend state sidecar, not workbook dependency.

### Workbook export output

- `stock_tax_app/engine/workbook_export.py:114-179,186-281`
  - Explicit workbook-writing path plus validation hook.
  - Classification: workbook export output.
- `build_stock_tax_workbook.py:1391-1498`
  - Explicit write/export entry points.
  - Classification: workbook export output.
- Test code still references `stock_tax_system.xlsx` as a temp output filename:
  - `test_stock_tax_app_api.py`
  - `test_project_state_store.py`
  - `test_locked_year_roundtrip.py`
  - Classification: temp generated workbook paths, not root-workbook dependency.

### Tests and scripts

- `test_stock_tax_app_api.py`
  - Still uses workbook paths for export and workbook-fallback scenarios, but only in temp project dirs.
  - Classification: test fixture via temp generated workbook.
- `test_project_state_store.py`
  - Still uses workbook paths for workbook-fallback adoption/export checks, but only in temp project dirs.
  - Classification: test fixture via temp generated workbook.
- `test_locked_year_roundtrip.py`
  - Still uses `sandbox / "stock_tax_system.xlsx"`, but it is built inside the sandbox.
  - Classification: manual test script via temp generated workbook.
- `verify_workbook.py stock_tax_system.xlsx`
  - Still validates an explicit workbook path.
  - Classification: manual script / legacy validation target.

### Docs only or stale historical references

- `README_OPERATOR.md`
- `docs/API_CONTRACT.md`
- `ui/frontend/README.md`
- `ui/DESIGN.md`
- `docs/audit/FX_CLEAN_WIRING_STATUS.md`
- `docs/audit/CHECKS_CLEAN_WIRING_STATUS.md`
- `docs/audit/OPEN_POSITIONS_CLEAN_WIRING_STATUS.md`
- `docs/audit/GREEN_CHECKPOINT_REPO_HYGIENE_REPORT.md`
- `docs/audit/SOFT_LOCK_SNAPSHOT_POLICY_STATUS.md`
- `docs/audit/LOCKED_YEAR_ROUNDTRIP_INVESTIGATION_STATUS.md`
- `docs/audit/ENGINE_EXTRACTION_RESTORE_STATUS.md`
- `docs/audit/ENGINE_EXTRACTION_RESTORE_PLAN.md`
- `docs/audit/ENGINE_EXTRACTION_VERIFICATION_REPORT.md`
- `docs/audit/CLEANUP_AND_REFACTOR_PLAN.md`
- `docs/audit/DELETION_CANDIDATES.md`
- `docs/audit/AUDIT_STATUS.md`
- `docs/audit/EXCEL_RETIREMENT_AUDIT.md`
- `docs/audit/FILE_INVENTORY.md`
- `docs/audit/REPO_TRUTH_MAP.md`

Notes:

- Some of these docs are now stale because they still describe the root workbook as an automated test fixture or `POST /api/recalculate` as workbook-writing.
- They were not mass-updated in this slice; this doc is the authoritative retirement status for the current cut.

## Runtime Behavior

- Does FastAPI require `stock_tax_system.xlsx` to exist?
  - No.
- Does `/api/status` require it?
  - No.
- Does `/api/years` require it?
  - No.
- Does `/api/sales` require it?
  - No.
- Does `/api/recalculate` read it or only write it?
  - It may read it as optional legacy fallback state if the workbook exists.
  - It no longer writes the workbook by default in this slice.
- Does `build_stock_tax_workbook.py` load state from it by default?
  - Yes, only if the target workbook exists.
  - If the workbook is missing, it uses empty/default legacy workbook state and continues from CSV plus JSON state.
- What happens if `stock_tax_system.xlsx` is temporarily renamed?
  - Backend smoke still passes.
  - Root workbook was restored immediately after the check.
  - `git status --short -- stock_tax_system.xlsx` returned no output.

## Test Dependency Audit

### What previously depended on the root workbook

- `test_stock_tax_app_api.py` copied the repo-root workbook into each temp project.
- `test_project_state_store.py` copied the repo-root workbook into each temp project.
- `test_locked_year_roundtrip.py` copied the repo-root workbook into its sandbox.

### What depends on it now

- No automated pytest path depends on the repo-root workbook existing.
- Workbook-oriented tests still depend on a workbook shape, but they now generate that workbook inside temp project dirs from CSV input.
- `verify_workbook.py stock_tax_system.xlsx` remains an explicit manual legacy/export validation step.

### Do tests mutate the root workbook?

- No automated tests in this slice mutate the root workbook.
- `test_locked_year_roundtrip.py` mutates only its sandbox workbook.
- API and project-state tests mutate only temp generated workbooks.

## Recalculate Behavior

- Before this slice:
  - `POST /api/recalculate` wrote and validated `stock_tax_system.xlsx`.
- After this slice:
  - `POST /api/recalculate` recalculates state only.
  - Workbook creation remains explicit via export-oriented code paths such as `runtime.calculate(write_workbook=True)` and the workbook CLI.

## Validation Commands And Results

- Requested search command:
  - `rg -n "stock_tax_system\.xlsx|Path\([^)]*xlsx|output_path|write_workbook|verify_workbook|test_locked_year_roundtrip|Locked_Years|Frozen_Snapshots" .`
  - Result: `rg` was not available in the PowerShell environment.
  - Follow-up: repository grep tooling was used to perform the equivalent audit across `*.py` and `*.md`.
- `py -3 -m pytest -q test_stock_tax_app_api.py`
  - PASS (`63 passed`)
- `py -3 -m pytest -q test_project_state_store.py`
  - PASS (`22 passed`)
- `py -3 -m pytest -q`
  - PASS (`87 passed`)
- `py -3 test_locked_year_roundtrip.py`
  - PASS
- Explicit no-root-workbook smoke:
  - Renamed `stock_tax_system.xlsx` to `stock_tax_system.xlsx.bak`
  - Ran `py -3 -m pytest -q test_stock_tax_app_api.py -k "without_root_workbook"`
  - PASS (`1 passed, 62 deselected`)
  - Restored `stock_tax_system.xlsx`
  - `git status --short -- stock_tax_system.xlsx` produced no output
- `py -3 verify_workbook.py stock_tax_system.xlsx`
  - PASS

## What Was Decoupled

- Normal backend startup and read-only API flows no longer require the root workbook to exist.
- `POST /api/recalculate` no longer creates or overwrites the workbook as part of normal UI recalc.
- Automated tests no longer use the repo-root workbook as a shared mutable fixture.
- The locked-year roundtrip script no longer starts from a copy of the repo-root workbook.

## What Still Depends On Workbook Semantics

- Explicit workbook export code paths.
- Workbook validation via `verify_workbook.py`.
- Legacy fallback domains when a workbook is present:
  - `locked_years`
  - `frozen_inventory`
  - `frozen_snapshots`
  - `filed_year_reconciliation`
  - parts of other workbook-era sheets when not yet migrated
- Manual/operator docs still assume a canonical workbook artifact exists at the repo root.

## Remaining Blockers Before Deleting `stock_tax_system.xlsx`

- Default output naming still points at `stock_tax_system.xlsx` in backend/CLI flows.
- Several domains still support workbook fallback if a workbook is present, so legacy compatibility is not fully isolated yet.
- Manual docs still instruct operators to use `stock_tax_system.xlsx` directly.
- Historical audit docs contain now-stale statements about the root workbook being a required test fixture and about `/api/recalculate` writing a workbook.
- No dedicated explicit API export route exists yet; export is still a lower-level runtime/CLI action.

## Exact Next Slice

- Add an explicit workbook export action/API contract separate from recalculate.
- Update stale docs to reflect that recalculate is state-only and workbook creation is export-only.
- Continue retiring remaining workbook-fallback domains so legacy workbook reads become isolated compatibility-only behavior.
- After that, re-run the suite and manual export validation, then remove the repo-root `stock_tax_system.xlsx` if no required root-path references remain.

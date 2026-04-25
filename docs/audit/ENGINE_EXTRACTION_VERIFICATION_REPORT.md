# Engine Extraction Verification Report

Timestamp: 2026-04-25T14:11:38.9386004+02:00

Recovery/verification classification: `PARTIAL_NEEDS_FIX`

## 1. Summary

Phases 2-7 were not all completed safely.

What is true:
- All expected phase 2-7 modules exist in `stock_tax_app/engine/`.
- Matching and tax-summary extraction are mostly wired and their focused tests passed.
- Frontend build passed.
- Backend smoke passed.
- Existing `stock_tax_system.xlsx` passes `verify_workbook.py`.

What is not true:
- The repository is not green.
- Full API/full pytest do not pass.
- Phase 2, 3, 4, and 7 are not fully completed per the phase plan.
- The current worktree does not match a clean "phase 7 completed" claim.

No code was changed during this verification audit.

## 2. Git Status / Diff Summary

Commands run:
- `git status --short`
- `git diff --stat`
- `git diff --name-only`
- `git diff --cached --stat`
- `git diff --cached --name-only`

Observed worktree:
- Staged: `docs/audit/CORPORATE_ACTIONS_EXTRACTION_STATUS.md`, `stock_tax_app/engine/corporate_actions.py`
- Unstaged: `build_stock_tax_workbook.py`
- Untracked: `_phase7_patch.py`, `docs/audit/ENGINE_EXTRACTION_PHASE_PLAN.md`, `stock_tax_app/engine/checks.py`, `stock_tax_app/engine/fx.py`, `stock_tax_app/engine/matching.py`, `stock_tax_app/engine/open_positions.py`, `stock_tax_app/engine/tax_summary.py`, `stock_tax_app/engine/workbook_export.py`

`git diff --stat`:
- `build_stock_tax_workbook.py | 2459 +++----------------------------------------`
- `1 file changed, 124 insertions(+), 2335 deletions(-)`

Important audit note:
- The staged area does not contain the phase 2-7 work. The new phase 2-7 engine modules are currently untracked.
- The current worktree is a mixed state: staged prior corporate-actions artifacts plus unstaged/untracked later extraction work.

### Changed File Classification

| File | Classification | Why it changed | Phase | Appears safe? | Keep / review / revert |
|---|---|---|---|---|---|
| `build_stock_tax_workbook.py` | `BROKEN_CHANGE` | Main integration point for extraction; large workbook-writer removal, matching/tax wrappers added, but FX and checks still in monolith; phase 7 helper compatibility broke | 2-7 | No | Review/rework before keep |
| `docs/audit/CORPORATE_ACTIONS_EXTRACTION_STATUS.md` | `PHASE_STATUS_DOC` | Prior extraction status doc | Prior CA phase | Doc claim does not match current worktree wiring | Review |
| `stock_tax_app/engine/corporate_actions.py` | `EXPECTED_EXTRACTION_CHANGE` | Prior extracted module | Prior CA phase | Module itself imports cleanly; current monolith does not use it | Review/keep after wiring audit |
| `_phase7_patch.py` | `GENERATED_ARTIFACT` | Local helper script used to generate/edit phase 7 extraction | 7 | Not production/runtime code | Do not keep in final refactor set |
| `docs/audit/ENGINE_EXTRACTION_PHASE_PLAN.md` | `PHASE_STATUS_DOC` | Refactor plan document | 2-7 | Yes | Keep |
| `stock_tax_app/engine/open_positions.py` | `EXPECTED_EXTRACTION_CHANGE` | New extracted phase 2 module | 2 | Module looks structurally fine; not wired as planned | Review |
| `stock_tax_app/engine/checks.py` | `EXPECTED_EXTRACTION_CHANGE` | New extracted phase 3 module | 3 | Module looks structurally fine; monolith still owns logic | Review |
| `stock_tax_app/engine/fx.py` | `EXPECTED_EXTRACTION_CHANGE` | New extracted phase 4 module | 4 | Module looks structurally fine; monolith still owns runtime FX | Review |
| `stock_tax_app/engine/matching.py` | `EXPECTED_EXTRACTION_CHANGE` | New extracted phase 5 module | 5 | Mostly wired and focused tests pass | Review/likely keep |
| `stock_tax_app/engine/tax_summary.py` | `EXPECTED_EXTRACTION_CHANGE` | New extracted phase 6 module | 6 | Mostly wired and focused tests pass | Review/likely keep |
| `stock_tax_app/engine/workbook_export.py` | `BROKEN_CHANGE` | New extracted phase 7 module; workbook writer moved, but helper compatibility incomplete and open-position logic duplicated here | 7 | No | Review/rework before keep |

## 3. Module Existence And Boundary Audit

All expected phase 2-7 modules exist.

### Module Table

| Module | Exists | Contents seen | Imports `build_stock_tax_workbook.py`? | Import-cycle issue seen? | DI / `Any` boundary | Behavior-change concern |
|---|---|---|---|---|---|---|
| `stock_tax_app/engine/open_positions.py` | Yes | `extract_position_rows_with_provenance`, `extract_position_rows`, `build_open_position_rows` | No | No import-cycle seen; module imports cleanly | Uses `Any` for `RawRow`/`Lot`; injects `safe_float`, `parse_trade_date` | No obvious logic drift inside module; not wired as planned |
| `stock_tax_app/engine/checks.py` | Yes | `build_check_rows` | No | No import-cycle seen; module imports cleanly | Uses `Any` for `FXResolver`/`MatchLine`/`Lot`; injects `supported_methods` | Module looks behavior-preserving; monolith still has full copy |
| `stock_tax_app/engine/fx.py` | Yes | `DEFAULT_FX_METHOD`, `SUPPORTED_FX_METHODS`, `DEFAULT_FX_YEARLY`, `GFR_OFFICIAL_RATES`, `CNB_DAILY_CACHE_FILE`, `build_fx_tables`, `cnb_cache_path`, `load_cnb_cache`, `save_cnb_cache`, `download_cnb_daily_rates_year`, `refresh_fx_daily_for_years`, `FXResolver`, `collect_required_fx_problems` | No | No import-cycle seen; module imports cleanly | Injects `parse_trade_date`, `to_bool`; uses `Any` for transactions | Logic still looks strict/no-fallback; not wired into monolith runtime |
| `stock_tax_app/engine/matching.py` | Yes | `_add_years`, `_coerce_date`, `_clone_lots`, `_lots_from_frozen`, `_expected_contribution_per_share_czk`, `rank_lots_for_sell`, `_make_match_line`, `match_sell`, `_match_global_optimized`, `simulate` | No | No cycle seen | Uses `Any`; injects `lot_factory`, `match_line_factory`, `to_bool`, `parse_trade_date`; imports `FXResolver` and corporate actions | Mostly aligned, but plan expected `default_method_for` injection; actual code uses injected `default_method` string |
| `stock_tax_app/engine/tax_summary.py` | Yes | `DEFAULT_TAX_RATE`, `DEFAULT_APPLY_100K`, `DEFAULT_100K_THRESHOLD`, `DEFAULT_FX_METHOD`, `build_yearly_summary`, `run_method_comparison`, `split_audit` | No | No cycle seen | Uses `Any`; `supported_methods` optional | Diverges from plan by importing `matching.simulate` directly instead of taking injected `simulate_fn` |
| `stock_tax_app/engine/workbook_export.py` | Yes | Style constants, `autosize_columns`, `write_header`, `add_table`, `write_calculation_result`, `write_workbook`, `_tmp_output_path`, `_backup_existing_output`, `_replace_output_or_fail`, all `_write_*` sheet writers, plus duplicated open-position helpers | No | No cycle seen | Uses `Any`; injects `safe_float`, `parse_trade_date`; calls extracted checks module | Boundary violation: duplicates phase 2 open-position logic internally instead of importing `open_positions.py`; phase 7 compatibility is incomplete |

Additional boundary findings:
- None of the new engine modules import `build_stock_tax_workbook.py`.
- All six modules import successfully.
- `stock_tax_app.engine.core` still imports `build_stock_tax_workbook` as the runtime facade, so the repo still depends on the monolith surface.

## 4. `build_stock_tax_workbook.py` Audit

Approximate line count now:
- Before: 3806 lines (from `docs/audit/ENGINE_EXTRACTION_PHASE_PLAN.md`)
- After: 1835 lines (measured)

This is a large reduction, but it is still far above the plan's expected ~700-900 line post-extraction target. That matches the code audit: several major responsibilities still remain in the monolith.

### Remaining major responsibilities still in the monolith

- Data models and parsing helpers
- Workbook/user-state loading and coercion helpers
- Settings, instrument-map, locked-year, frozen-state loading
- Full corporate-actions parsing and application logic
- Full FX constants, table building, CNB cache helpers, FX resolver, FX preflight
- Full `build_check_rows`
- Main orchestration in `calculate_workbook_data`
- CLI `main`

### Wrapper audit

| Domain | Wrapper state in monolith | Thin delegation? | Notes |
|---|---|---|---|
| Open positions | Only `build_open_position_rows` remains | Thin, but delegates to `workbook_export.py`, not `open_positions.py` | `extract_position_rows` and `extract_position_rows_with_provenance` wrappers are missing |
| Checks | `build_check_rows` remains as full implementation | No | Phase 3 not actually extracted from monolith |
| FX | `build_fx_tables`, `FXResolver`, CNB helpers, `collect_required_fx_problems` remain as full implementations | No | Phase 4 not actually extracted from monolith |
| Matching | `_expected_contribution_per_share_czk`, `_add_years`, `rank_lots_for_sell`, `_make_match_line`, `_match_global_optimized`, `match_sell`, `_lots_from_frozen`, `simulate`, `_clone_lots`, `_coerce_date` remain as wrappers | Yes | These are the cleanest extraction wrappers |
| Tax summary | `build_yearly_summary`, `run_method_comparison`, `split_audit` remain | Yes | Thin wrappers |
| Workbook export | `write_calculation_result`, `write_workbook`, `autosize_columns`, `write_header`, `add_table` remain | Yes for those symbols | `_tmp_output_path`, `_backup_existing_output`, `_replace_output_or_fail` wrappers/re-exports are missing and tests fail because of that |

### Compatibility audit

- Public/tested helper compatibility is broken: `build_stock_tax_workbook._replace_output_or_fail` no longer exists.
- This is a concrete regression detected by `test_stock_tax_app_api.py::test_locked_output_fails_without_alternate_workbook`.

## 5. Phase-By-Phase Verification

| Phase | Planned | Actually extracted | Wrappers present | Tests run | Pass / fail | Concerns |
|---|---|---|---|---|---|---|
| 2 `open_positions.py` | Move `extract_position_rows`, `extract_position_rows_with_provenance`, `build_open_position_rows` | Module exists with all 3 functions | Only `build_open_position_rows` wrapper exists, and it points to `workbook_export.py` instead of `open_positions.py`; other wrappers missing | 6 focused open-position tests; API suite | Focused tests passed | Reported-position provenance behavior is still present, including `unknown`/`partial` source handling, but extraction is only partial and the runtime path is miswired |
| 3 `checks.py` | Move `build_check_rows` | Module exists with `build_check_rows` | No thin monolith wrapper; monolith still contains full implementation | API suite; full suite; focused `-k` runs | Behavior mostly okay, but repo still red | `core.py` still holds frontend-safe href logic as expected; checks still surface in API; extraction itself is incomplete |
| 4 `fx.py` | Move FX constants, resolver, cache helpers, `build_fx_tables`, `collect_required_fx_problems` | Module exists with all planned symbols | No thin monolith wrappers/re-exports in actual runtime path; monolith still owns FX | FX-focused tests; project-state suite; full suite | FX-focused tests passed | Strict no-fallback behavior still holds in tests and code; phase wiring is incomplete |
| 5 `matching.py` | Move ranking/matching/simulate core | Module exists with all expected core functions | Thin wrappers are present and used | `test_min_gain_optimality.py`; focused matching sales/method tests; API suite | Focused tests passed | Most complete extraction phase; implementation differs slightly from plan by taking `default_method` instead of injected `default_method_for` |
| 6 `tax_summary.py` | Move yearly summary, method comparison, split audit | Module exists with all expected functions | Thin wrappers are present and used | Focused yearly/tax tests; API suite | Behavior tests passed; one `-k "year or tax or exemption or audit"` run failed only because phase 7 helper regression was also selected | Imports `matching.simulate` directly instead of injected simulate function, but no behavior drift was detected |
| 7 `workbook_export.py` | Move write layer, helpers, styles, verify integration | Module exists with broad write surface and helper functions | Thin wrappers exist only for `write_calculation_result`, `write_workbook`, `autosize_columns`, `write_header`, `add_table` | Full API/full pytest; `verify_workbook.py stock_tax_system.xlsx`; `test_locked_year_roundtrip.py` | Failed overall | Missing helper compatibility (`_replace_output_or_fail`); open-position logic duplicated here instead of using phase 2 module; locked-year roundtrip failed during rebuild |

### Phase conclusions

- Safely verified: phase 5 mostly complete, phase 6 mostly complete.
- Partially complete: phase 2.
- Incomplete: phase 3 and phase 4.
- Broken/partial: phase 7.

## 6. Required Validation Commands And Results

### Baseline Python suites

| Command | Result |
|---|---|
| `py -3 -m pytest -q test_project_state_store.py` | PASS (`22 passed`) |
| `py -3 -m pytest -q test_stock_tax_app_api.py` | FAIL (`1 failed, 57 passed`) |
| `py -3 -m pytest -q` | FAIL (`1 failed, 81 passed`) |

Failing test in both failing runs:
- `test_stock_tax_app_api.py::test_locked_output_fails_without_alternate_workbook`
- Failure: `AttributeError: module 'build_stock_tax_workbook' has no attribute '_replace_output_or_fail'`

### Focused open-position tests

All six exact tests passed:
- `test_open_positions_exact_match_is_ok_and_ready`
- `test_open_positions_warn_difference_creates_needs_review_and_status_check`
- `test_open_positions_material_difference_blocks_collection_and_surfaces_audit_reason`
- `test_open_positions_missing_reported_position_is_unknown_not_ok`
- `test_open_positions_provenance_missing_snapshot_date_is_honest`
- `test_open_positions_multiple_reported_rows_expose_ambiguity_and_source_count`

### Focused FX tests

| Command | Result |
|---|---|
| `py -3 -m pytest -q test_stock_tax_app_api.py -k "fx or FX or missing"` | PASS (`13 passed, 45 deselected`) |

### Focused matching / tax tests

| Command | Result |
|---|---|
| `py -3 -m pytest -q test_min_gain_optimality.py` | PASS (`2 passed`) |
| `py -3 -m pytest -q test_stock_tax_app_api.py -k "sales or method or match or gain or year"` | PASS (`23 passed, 35 deselected`) |
| `py -3 -m pytest -q test_stock_tax_app_api.py -k "year or tax or exemption or audit"` | FAIL (`1 failed, 57 passed`) |

Note on the last command:
- The failure was the same phase 7 helper compatibility failure, not a direct tax-formula failure.

### Corporate actions regression

| Command | Result |
|---|---|
| `py -3 -m pytest -q test_stock_tax_app_api.py::test_invalid_corporate_actions_surface_in_status_and_audit` | PASS |

### Workbook/manual validation

| Command | Result |
|---|---|
| `py -3 test_locked_year_roundtrip.py` | FAIL |
| `py -3 verify_workbook.py stock_tax_system.xlsx` | PASS |

`test_locked_year_roundtrip.py` failed on pass 2 with:
- `Checks` sheet ERROR rows present
- `locked_year_no_snapshot` reported for year 2020
- unmatched SELL quantities present
- temporary workbook validation failed and output was not replaced

### Frontend build

| Command | Result |
|---|---|
| `npm run build` in `ui/frontend` | PASS |

### Backend smoke

Requested command used a Bash heredoc form that is not supported by PowerShell 5.1.
Equivalent safe command was run with `py -3 -c`.

Result:
- `/api/status` -> 200
- `/api/import` -> 200
- `/api/years` -> 200
- `/api/sales` -> 200
- `/api/open-positions` -> 200
- `/api/fx` -> 200
- `/api/audit` -> 200
- `/api/settings` -> 200

### Launcher smoke

Skipped by instruction because "run launcher smoke if all above pass" was not satisfied.

## 7. API Smoke Results And Shape Spot-Check

### Response shape status

- `/api/years`, `/api/sales`, `/api/open-positions`, `/api/fx` all returned top-level `{ items, truth }`
- `truth` metadata remained present with keys: `status`, `reasons`, `sources`, `summary`, `item_count`, `empty_meaning`
- `/api/open-positions` still includes provenance fields such as `reported_position_source_file`, `reported_position_source_row`, `reported_position_snapshot_date`, `reported_position_source_status`, `reported_position_source_reason`, `reported_position_source_count`, `reported_position_sources`
- `/api/fx` still includes `rate_source`
- `/api/years` still includes year method/tax provenance-related fields such as `method_source`, `settings_source`, `tax_rate`, `fx_method`
- `/api/audit` still returns `summary_only` explicitly, and it was `true` in the smoke response
- `/api/status` and `/api/settings` both returned successful shapes consistent with current backend expectations

Corporate action diagnostics status:
- Current smoke did not intentionally inject invalid corporate actions.
- Regression coverage still passed via `test_invalid_corporate_actions_surface_in_status_and_audit`.

## 8. Documentation Verification

Required phase status docs checked:
- `docs/audit/OPEN_POSITIONS_EXTRACTION_STATUS.md` -> missing
- `docs/audit/CHECKS_EXTRACTION_STATUS.md` -> missing
- `docs/audit/FX_EXTRACTION_STATUS.md` -> missing
- `docs/audit/MATCHING_EXTRACTION_STATUS.md` -> missing
- `docs/audit/TAX_SUMMARY_EXTRACTION_STATUS.md` -> missing
- `docs/audit/WORKBOOK_EXPORT_EXTRACTION_STATUS.md` -> missing
- `docs/audit/ENGINE_EXTRACTION_FINAL_STATUS.md` -> missing
- `docs/audit/ENGINE_EXTRACTION_STOP_REPORT.md` -> missing

Only related extraction status doc currently present in the worktree:
- `docs/audit/CORPORATE_ACTIONS_EXTRACTION_STATUS.md`

Important doc mismatch:
- That corporate-actions doc claims `build_stock_tax_workbook.py` now imports and delegates to extracted corporate-actions logic.
- The current worktree does not reflect that claim; `build_stock_tax_workbook.py` still contains full corporate-actions implementations.

## 9. Risks Found

1. Concrete regression in phase 7 compatibility surface.
`build_stock_tax_workbook._replace_output_or_fail` is missing, and full pytest is red because of it.

2. Phase 2 boundary violation.
`workbook_export.py` duplicates `extract_position_rows*` / `build_open_position_rows` instead of importing `open_positions.py`, increasing drift risk.

3. Phase 3 not actually completed.
`build_stock_tax_workbook.py` still owns the full `build_check_rows` implementation.

4. Phase 4 not actually completed.
`build_stock_tax_workbook.py` still owns full FX constants, cache helpers, `FXResolver`, `build_fx_tables`, and `collect_required_fx_problems`.

5. Locked-year roundtrip regression remains unresolved.
`test_locked_year_roundtrip.py` fails during rebuild with locked-year snapshot/check consistency issues and unmatched SELL validation errors.

6. Extraction docs are incomplete and partially unreliable against the current worktree.

7. The worktree is mixed staged/unstaged/untracked state, so any summary that claims a completed extraction without revalidation is unsafe.

## 10. Exact Next Recommended Action

Do not continue extraction.

First restore the phase 7 compatibility surface in `build_stock_tax_workbook.py` so the monolith still exposes `_tmp_output_path`, `_backup_existing_output`, and `_replace_output_or_fail`, then re-run:
- `py -3 -m pytest -q test_stock_tax_app_api.py::test_locked_output_fails_without_alternate_workbook`
- `py -3 -m pytest -q test_stock_tax_app_api.py`
- `py -3 -m pytest -q`

Only after full pytest is green should the locked-year roundtrip regression be re-investigated and the incomplete phase 2/3/4/7 extraction boundaries be either completed correctly or rolled back.

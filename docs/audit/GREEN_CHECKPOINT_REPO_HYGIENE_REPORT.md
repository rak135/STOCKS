# Green Checkpoint Repo Hygiene Report

Date: 2026-04-25

## Current Test Status

Validated on the current dirty worktree:

| Command | Result |
|---|---|
| `py -3 -m pytest -q` | PASS (`85 passed in 70.92s`) |
| `py -3 test_locked_year_roundtrip.py` | PASS |
| `py -3 verify_workbook.py stock_tax_system.xlsx` | PASS |
| `npm run build` in `ui/frontend` | Not run; no dirty frontend files were present in `git status --short` |

Root workbook status:

- `stock_tax_system.xlsx` remains unmodified in the repo worktree.
- `verify_workbook.py` reported `Checks` ERROR rows = `0`.

## Worktree Inspection

Commands run:

- `git status --short`
- `git diff --stat`
- `git diff --name-only`
- `git diff --cached --stat`
- `git diff --cached --name-only`

Observed status before creating this report:

```text
 M build_stock_tax_workbook.py
A  docs/audit/CORPORATE_ACTIONS_EXTRACTION_STATUS.md
A  stock_tax_app/engine/corporate_actions.py
 M stock_tax_app/engine/policy.py
 M test_locked_year_roundtrip.py
 M test_stock_tax_app_api.py
?? _phase7_patch.py
?? docs/audit/ENGINE_EXTRACTION_PHASE_PLAN.md
?? docs/audit/ENGINE_EXTRACTION_RESTORE_PLAN.md
?? docs/audit/ENGINE_EXTRACTION_RESTORE_STATUS.md
?? docs/audit/ENGINE_EXTRACTION_VERIFICATION_REPORT.md
?? docs/audit/LOCKED_YEAR_ROUNDTRIP_INVESTIGATION_STATUS.md
?? docs/audit/SOFT_LOCK_SNAPSHOT_POLICY_STATUS.md
?? stock_tax_app/engine/checks.py
?? stock_tax_app/engine/fx.py
?? stock_tax_app/engine/matching.py
?? stock_tax_app/engine/open_positions.py
?? stock_tax_app/engine/tax_summary.py
?? stock_tax_app/engine/workbook_export.py
```

Unstaged diff summary at inspection time:

```text
build_stock_tax_workbook.py    | 2466 +++-------------------------------------
stock_tax_app/engine/policy.py |   30 +-
test_locked_year_roundtrip.py  |  160 +--
test_stock_tax_app_api.py      |  116 ++
4 files changed, 345 insertions(+), 2427 deletions(-)
```

Staged diff summary at inspection time:

```text
docs/audit/CORPORATE_ACTIONS_EXTRACTION_STATUS.md |  82 +++++++
stock_tax_app/engine/corporate_actions.py         | 271 ++++++++++++++++++++++
2 files changed, 353 insertions(+)
```

## Worktree Classification Table

| File | Git state at inspection | Classification | Why it changed | Currently used by runtime/tests | Tests prove it | Include in next commit | Revert or leave for later |
|---|---|---|---|---|---|---|---|
| `build_stock_tax_workbook.py` | unstaged modified | `KEEP_NOW_RUNTIME` | Current runtime facade now delegates matching, tax summary, workbook export, restores helper compatibility wrappers, and carries the soft-lock default behavior used by `build_locked_years()` | Yes, runtime and tests import this file directly | Yes: full `pytest`, roundtrip script, workbook verify | Yes | Keep now |
| `stock_tax_app/engine/policy.py` | unstaged modified | `KEEP_NOW_RUNTIME` | Soft-lock policy change: filed years remain default-locked, but explicit unlock is now allowed by policy | Yes, runtime and tests use it | Yes: full `pytest` and new policy/lock tests | Yes | Keep now |
| `stock_tax_app/engine/corporate_actions.py` | staged added | `KEEP_NOW_RUNTIME` | Extracted corporate-action parsing/application logic | Yes, via `stock_tax_app.engine.matching` import path | Yes, indirectly in green suite/runtime path | Yes | Keep now |
| `stock_tax_app/engine/checks.py` | untracked | `KEEP_NOW_RUNTIME` | Extracted check-row shaping used by workbook writing path | Yes, via `stock_tax_app.engine.workbook_export._write_checks()` | Yes, indirectly through workbook export paths and green suite | Yes | Keep now |
| `stock_tax_app/engine/fx.py` | untracked | `KEEP_NOW_RUNTIME` | Extracted FX helpers/constants/type surface required by extracted modules | Yes, imported by `matching.py`, `tax_summary.py`, `workbook_export.py` | Yes, indirectly through green suite/runtime imports | Yes | Keep now |
| `stock_tax_app/engine/matching.py` | untracked | `KEEP_NOW_RUNTIME` | Extracted matching/snapshot engine, including stale-snapshot rebuild handling | Yes, imported at module load by `build_stock_tax_workbook.py` | Yes: full `pytest`, roundtrip script, workbook verify | Yes | Keep now |
| `stock_tax_app/engine/tax_summary.py` | untracked | `KEEP_NOW_RUNTIME` | Extracted yearly summary, method comparison, split audit helpers | Yes, used by `build_stock_tax_workbook.py` wrappers | Yes: full `pytest` and workbook generation path | Yes | Keep now |
| `stock_tax_app/engine/workbook_export.py` | untracked | `KEEP_NOW_RUNTIME` | Extracted workbook write layer and compatibility helper targets | Yes, used by `write_workbook()`, `write_calculation_result()`, open-position wrapper, and backend export flow | Yes: full `pytest`, roundtrip script, workbook verify | Yes | Keep now |
| `test_locked_year_roundtrip.py` | unstaged modified | `KEEP_NOW_TEST` | Changed from unsafe fixture mutation to sandboxed validation of controlled stale-snapshot failure plus unlock recovery | Yes, direct validation script | Yes: command passes now | Yes | Keep now |
| `test_stock_tax_app_api.py` | unstaged modified | `KEEP_NOW_TEST` | Added API/backend coverage for soft-lock override and stale-snapshot rebuild checks | Tests only | Yes: included in `85 passed` | Yes | Keep now |
| `docs/audit/CORPORATE_ACTIONS_EXTRACTION_STATUS.md` | staged added | `KEEP_NOW_DOC` | Documents the corporate-actions extraction slice | No runtime use | No | Yes, if `corporate_actions.py` is committed | Keep now |
| `docs/audit/SOFT_LOCK_SNAPSHOT_POLICY_STATUS.md` | untracked | `KEEP_NOW_DOC` | Documents the current green soft-lock/stale-snapshot behavior and validation results | No runtime use | No | Yes | Keep now |
| `docs/audit/GREEN_CHECKPOINT_REPO_HYGIENE_REPORT.md` | created by this pass | `KEEP_NOW_DOC` | This hygiene audit and checkpoint recommendation | No runtime use | No | Yes | Keep now |
| `stock_tax_app/engine/open_positions.py` | untracked | `UNTRACKED_EXTRACTION_CANDIDATE` | Phase-2 extraction candidate exists, but runtime is not wired to it | No current runtime path uses it | No direct proof; current tests do not import it | No | Leave untracked or drop from branch before commit |
| `_phase7_patch.py` | untracked | `GENERATED_ARTIFACT` | Local helper script used to generate/edit extraction work | No | No | No | Drop from branch or keep outside repo |
| `docs/audit/ENGINE_EXTRACTION_PHASE_PLAN.md` | untracked | `UNKNOWN` | Planning document for the broader extraction attempt | No | No | No for green checkpoint | Leave untracked for reference |
| `docs/audit/ENGINE_EXTRACTION_RESTORE_PLAN.md` | untracked | `UNKNOWN` | Historical restore-plan document for the previously broken state | No | No | No for green checkpoint | Leave untracked for reference |
| `docs/audit/ENGINE_EXTRACTION_RESTORE_STATUS.md` | untracked | `UNKNOWN` | Historical restore-status document after compatibility repair | No | No | No for green checkpoint | Leave untracked for reference |
| `docs/audit/ENGINE_EXTRACTION_VERIFICATION_REPORT.md` | untracked | `SUSPICIOUS` | Historical report explicitly says the repo was not green; useful history but misleading in a green checkpoint commit | No | No | No | Leave untracked; do not include in green checkpoint |
| `docs/audit/LOCKED_YEAR_ROUNDTRIP_INVESTIGATION_STATUS.md` | untracked | `SUSPICIOUS` | Historical investigation doc says the roundtrip still fails; that is now superseded by the passing soft-lock implementation/status | No | No | No | Leave untracked; do not include in green checkpoint |

## Module Usage Table

| Module | Imported by runtime? | Used by `build_stock_tax_workbook.py`? | Used only by tests? | Untracked? | Safe to keep now? | Reason |
|---|---|---|---|---|---|---|
| `stock_tax_app/engine/corporate_actions.py` | Yes | Yes, indirectly through `matching.py` | No | No | Yes | Current matching runtime imports it; keeping it matches the current green runtime dependency graph |
| `stock_tax_app/engine/open_positions.py` | No | No | No | Yes | No | The current runtime wrapper points to `workbook_export.build_open_position_rows`, not this module |
| `stock_tax_app/engine/checks.py` | Yes | Yes, indirectly through `workbook_export.py` | No | Yes | Yes | Workbook writing imports it for `Checks` sheet generation; omitting it would leave the writer import chain incomplete |
| `stock_tax_app/engine/fx.py` | Yes | Yes, indirectly through `matching.py`, `tax_summary.py`, and `workbook_export.py` | No | Yes | Yes | Extracted modules import its constants/types at module load; it is part of the current runtime import surface |
| `stock_tax_app/engine/matching.py` | Yes | Yes, directly | No | Yes | Yes | `build_stock_tax_workbook.py` imports it at top level and delegates core matching there |
| `stock_tax_app/engine/tax_summary.py` | Yes | Yes, directly via wrappers | No | Yes | Yes | Runtime wrappers call into it for yearly summary, method comparison, and split audit |
| `stock_tax_app/engine/workbook_export.py` | Yes | Yes, directly via wrappers | No | Yes | Yes | Current write/export paths and compatibility helper wrappers point here |

## Partial Extraction Risk Review

| Module | Wired? | Duplicated logic still in `build_stock_tax_workbook.py`? | Would keeping it uncommitted create confusion? | Would reverting it break current green tests? | Decision |
|---|---|---|---|---|---|
| `stock_tax_app/engine/open_positions.py` | No | No direct duplication in `build_stock_tax_workbook.py`; the logic currently lives inside `workbook_export.py` instead | Yes; the file looks like a finished extraction but is not actually used | No, current green runtime does not import it | Do not include in next commit |
| `stock_tax_app/engine/checks.py` | Partially | Yes; `build_stock_tax_workbook.py` still has its own `build_check_rows()` for calculation/tests, while `workbook_export.py` uses the extracted module for writing | Yes | Yes, because `workbook_export.py` imports it | Include with the current runtime checkpoint |
| `stock_tax_app/engine/fx.py` | Partially | Yes; `build_stock_tax_workbook.py` still owns active calculation FX building/resolution, but extracted modules import `fx.py` for constants/types | Yes | Yes, because extracted runtime modules import it | Include with the current runtime checkpoint |
| `stock_tax_app/engine/workbook_export.py` | Yes | Mostly no for workbook writing; `build_stock_tax_workbook.py` now keeps thin wrappers only. The open-position helpers are duplicated here instead of using `open_positions.py` | Yes | Yes, current write/export/runtime paths depend on it | Include with the current runtime checkpoint |

Key risk conclusion:

- `open_positions.py` is the clearest incomplete extraction artifact and should not be part of the next checkpoint commit.
- `checks.py` and `fx.py` are partial extractions, but they are already part of the active import graph because `workbook_export.py`, `matching.py`, and `tax_summary.py` depend on them.
- `workbook_export.py`, `matching.py`, and `tax_summary.py` are no longer optional experiments; the current green runtime already routes through them.

## Checkpoint Recommendation

Recommended strategy: `COMMIT_CORE_REVERT_PARTIAL_EXTRACTION`

Rationale:

1. The repo is green on the current runtime code path.
2. The current index is unsafe as-is because only the corporate-actions pieces are staged; that staged subset is not a self-contained checkpoint.
3. Several untracked modules are now required by the active runtime (`matching.py`, `tax_summary.py`, `workbook_export.py`, plus their import dependencies `fx.py` and `checks.py`).
4. One extraction module (`open_positions.py`) is still not wired and would add confusion if committed now.
5. Several audit docs describe broken intermediate states and should not be part of a green checkpoint commit.

### Exact Files To Commit In The Next Green Checkpoint

Code and tests:

- `build_stock_tax_workbook.py`
- `stock_tax_app/engine/policy.py`
- `stock_tax_app/engine/corporate_actions.py`
- `stock_tax_app/engine/checks.py`
- `stock_tax_app/engine/fx.py`
- `stock_tax_app/engine/matching.py`
- `stock_tax_app/engine/tax_summary.py`
- `stock_tax_app/engine/workbook_export.py`
- `test_locked_year_roundtrip.py`
- `test_stock_tax_app_api.py`

Docs to include with that checkpoint:

- `docs/audit/CORPORATE_ACTIONS_EXTRACTION_STATUS.md`
- `docs/audit/SOFT_LOCK_SNAPSHOT_POLICY_STATUS.md`
- `docs/audit/GREEN_CHECKPOINT_REPO_HYGIENE_REPORT.md`

### Exact Files To Leave Out Of The Next Commit

Leave untracked or move aside before committing:

- `stock_tax_app/engine/open_positions.py`
- `docs/audit/ENGINE_EXTRACTION_PHASE_PLAN.md`
- `docs/audit/ENGINE_EXTRACTION_RESTORE_PLAN.md`
- `docs/audit/ENGINE_EXTRACTION_RESTORE_STATUS.md`
- `docs/audit/ENGINE_EXTRACTION_VERIFICATION_REPORT.md`
- `docs/audit/LOCKED_YEAR_ROUNDTRIP_INVESTIGATION_STATUS.md`

Drop from the branch or keep outside the repo:

- `_phase7_patch.py`

### Staging Guidance

- Do not commit the current staged set unchanged.
- First clear the partial staged state, then stage the exact green-checkpoint file group above.
- The next commit should represent the tested runtime actually exercised by the green validation commands, not the current mixed staged/untracked snapshot.

## Validation Commands Run

Git inspection:

- `git status --short`
- `git diff --stat`
- `git diff --name-only`
- `git diff --cached --stat`
- `git diff --cached --name-only`

Code/runtime validation:

- `py -3 -m pytest -q`
  Result: PASS (`85 passed in 70.92s`)
- `py -3 test_locked_year_roundtrip.py`
  Result: PASS
- `py -3 verify_workbook.py stock_tax_system.xlsx`
  Result: PASS

## Next Recommended Engineering Slice

One minimal next slice after checkpointing:

1. Decide whether Phase 2 `open_positions.py` should be wired for real or dropped entirely.
2. If kept, make that a dedicated behavior-preserving extraction slice that changes only the open-position path, removes the duplicated implementation from `workbook_export.py`, and reruns the same green validation set.

# Root `stock_tax_system.xlsx` Removal — Status

## Product Decision

This program must not be Excel-based. Excel is not the runtime truth,
not the primary UI, not the normal export target, and not a required
repository artifact.

This slice is the first real Excel-removal step: it deletes the
repo-root `stock_tax_system.xlsx` as a product/runtime artifact and
makes the repository stay green without it.

Out of scope for this slice (deferred):

- Adding a workbook export API.
- Re-introducing workbook writing into `POST /api/recalculate`.
- Removing all workbook export code.
- Migrating every remaining legacy workbook fallback domain.
- Changing tax formulas or frontend behaviour.

## File Removed

- `stock_tax_system.xlsx` (repository root).
  - It was already untracked (`.gitignore` excludes `stock_tax_system.xlsx`
    and `*.xlsx`), so no `git rm` was required.
  - The on-disk file at the repo root was deleted.
  - No automated test depends on it. The repo has no tracked workbook
    artifact.

## References Changed (Must Change Now)

| File | Change | Why |
|------|--------|-----|
| `stock_tax_app/backend/main.py` | Default `output_path` is now `project / "stock_tax_export.xlsx"` instead of `project / "stock_tax_system.xlsx"`. | The runtime no longer presents a "canonical product workbook" path — its default points at an explicitly-named export file. |
| `stock_tax_app/engine/core.py` | `engine.run()` falls back to a new `ENGINE_DEFAULT_EXPORT_NAME = "stock_tax_export.xlsx"` instead of `workbook.CANONICAL_OUTPUT_NAME`. | Mirrors the backend default so direct `engine.run()` calls (tests, scripts) do not silently target the legacy product name. |
| `verify_workbook.py` | The `path` argument is required; there is no implicit default. | The validator can no longer imply that a canonical `stock_tax_system.xlsx` exists at the repo root. |
| `README_OPERATOR.md` | Banner clarifies this is the legacy/manual workbook export workflow. CLI examples point `--output` at `exports/stock_tax_export.xlsx`. References to "rebuild always targets `stock_tax_system.xlsx`" removed. | Operators must not infer that a root product workbook exists. |
| `docs/API_CONTRACT.md` | Frontend constraint generalised to "must never parse any Excel workbook" and explicitly notes Excel is a legacy export, not runtime truth. | Document the product decision at the contract layer. |
| `ui/frontend/README.md` | Same generalisation: frontend must not parse any Excel workbook. | Same. |
| `docs/api_samples/status.json` | Sample `output_path` updated to `stock_tax_export.xlsx`. | Sample data must match the new default. |

## References Changed (Test Fixtures)

| File | Change | Why |
|------|--------|-----|
| `test_stock_tax_app_api.py` | `_workbook_path()` now returns `project / "stock_tax_export.xlsx"`; all in-test `project / "stock_tax_system.xlsx"` literals updated to the export name. | Test pre-seed paths must match the runtime default for round-tripping. The literals were always inside `tmp_path` projects — none of these files lived at the repo root. |
| `test_project_state_store.py` | Same update as above. | Same. |
| `test_stock_tax_app_api.py::test_api_runs_without_root_workbook_and_only_exports_explicitly` | Hardened: now asserts the runtime's `output_path.name != CANONICAL_OUTPUT_NAME`, that no `stock_tax_system.xlsx` is created in the project, and that an explicit `runtime.calculate(write_workbook=True)` writes only to the export path. | Make the no-root invariant a regression test. |

## References Intentionally Unchanged (Safe Legacy / Manual)

- `build_stock_tax_workbook.py` — the legacy workbook CLI still uses
  `CANONICAL_OUTPUT_NAME = "stock_tax_system.xlsx"` and still rejects
  alternate names without `--allow-alternate-output`. This guardrail is
  scoped to the manual CLI; deleting it is a future slice.
- `test_locked_year_roundtrip.py` — uses `sandbox / "stock_tax_system.xlsx"`
  *inside a temp sandbox*. It is purely a temp output and does not touch
  the repo root.
- `test_stock_tax_app_api.py::test_locked_output_fails_without_alternate_workbook`
  — uses `tmp_path / "stock_tax_system.xlsx"` to test the error message
  formatting of `_replace_output_or_fail`. Temp file in `tmp_path`, not
  repo root.
- `verify_workbook.py` itself — kept as a manual/legacy validator. It
  no longer defaults to a repo-root file but still validates any
  explicit workbook path passed in.
- `docs/audit/*` audit history (e.g. `EXCEL_RETIREMENT_AUDIT.md`,
  `STOCK_TAX_SYSTEM_XLSX_RETIREMENT_STATUS.md`,
  `LOCKED_YEAR_ROUNDTRIP_INVESTIGATION_STATUS.md`, etc.) — historical
  records. Not mass-edited; this status doc is the current authority.
- `IMPLEMENTATION_NOTES.md`, `ui/DESIGN.md`, `ui/prototype.html` — older
  design / prototype artifacts. They mention `stock_tax_system.xlsx`
  in historical context. Not in scope for this slice.

## What Still Has Optional Workbook / Export Compatibility

- The legacy CLI `build_stock_tax_workbook.py` continues to write a
  workbook at any `--output` path (defaults to `stock_tax_system.xlsx`,
  rejected with `--allow-alternate-output` for any other name).
- `BackendRuntime.calculate(write_workbook=True)` can still produce a
  workbook export at `runtime.output_path`. This path is **never**
  triggered by `POST /api/recalculate`; it is reachable only by direct
  Python calls (tests, manual scripts).
- Workbook-backed legacy fallbacks for review state, instrument map,
  FX, and method selection still work when a legacy workbook is
  present at the runtime's `output_path`. Those fallbacks remain
  covered by tests in `test_project_state_store.py`.
- `verify_workbook.py` still validates workbook structure when passed
  an explicit workbook path.

## Backend / API Behaviour Without Root Excel

Smoke run (from a clean repo with no `stock_tax_system.xlsx` and no
`stock_tax_export.xlsx`):

| Endpoint | Status |
|----------|--------|
| `GET /api/status` | 200 |
| `GET /api/years` | 200 |
| `GET /api/sales` | 200 |
| `POST /api/recalculate` | 200 |

After all four calls:

- `stock_tax_system.xlsx` does not exist at the repo root.
- `stock_tax_export.xlsx` does not exist at the repo root.

The backend runs entirely from `.csv/`, project state, and
`.ui_state.json`. No workbook is required, read, or written.

## Recalculate Behaviour

`POST /api/recalculate` calls
`BackendRuntime.calculate(write_workbook=False)`. It is state-only:

- Recomputes the engine result.
- Updates the in-memory `_last_result` cache.
- Does **not** write any workbook.
- Does **not** touch `stock_tax_system.xlsx` or
  `stock_tax_export.xlsx` on disk.

Workbook export remains opt-in via direct
`runtime.calculate(write_workbook=True)` (used by a handful of export
tests) or via the legacy `build_stock_tax_workbook.py` CLI.

## Tests Run and Results

| Command | Result |
|---------|--------|
| `py -3 -m pytest -q test_stock_tax_app_api.py` | 63 passed |
| `py -3 -m pytest -q test_project_state_store.py` | 22 passed |
| `py -3 -m pytest -q test_root_excel_absent.py` | 4 passed |
| `py -3 -m pytest -q` (full suite) | 91 passed |
| `py -3 test_locked_year_roundtrip.py` | PASS (Pass 1, controlled-fail Pass 2, Pass 3) |

New regression tests (`test_root_excel_absent.py`):

- `test_repo_root_legacy_workbook_is_absent` — `stock_tax_system.xlsx`
  must not exist at the repo root.
- `test_backend_default_output_path_is_not_legacy_name` — backend
  runtime default `output_path` does not point at the legacy name.
- `test_backend_api_runs_without_legacy_workbook` — `/api/status`,
  `/api/years`, `/api/sales` succeed without any workbook present.
- `test_recalculate_does_not_create_legacy_workbook` —
  `POST /api/recalculate` does not create the legacy workbook (or any
  workbook).

## Does Any Automated Path Still Require Root Excel?

No. No test in the suite requires `stock_tax_system.xlsx` at the repo
root, and no runtime path reads or writes it.

## Remaining Blockers Before Removing Workbook Fallback Code Entirely

These are deliberately out of scope for this slice:

1. Workbook-backed fallback domains (review state, instrument map, FX,
   method selection) still read from `runtime.output_path` if a legacy
   workbook is present. Migration to project-state-only ownership is a
   separate slice per domain.
2. `build_stock_tax_workbook.py` and `stock_tax_app/engine/workbook_export.py`
   remain as the export pipeline. They are not "required" but they are
   live code.
3. `verify_workbook.py` is still imported by the workbook export path
   for post-write validation. It can only be deleted when the workbook
   export path itself is deleted.
4. `.ui_state.json` is currently located next to `output_path`. If the
   default output path moves into a subdirectory (e.g. `exports/`), the
   UI state file must be decoupled from the workbook path first to
   avoid losing existing user state. Kept at the project root in this
   slice.
5. `README_OPERATOR.md`, `IMPLEMENTATION_NOTES.md`, `ui/DESIGN.md`, and
   `ui/prototype.html` still describe the legacy workbook workflow at
   length. Trim or retire as Excel export is fully removed.

## Recommended Next Slice

Move the default backend `output_path` into a clearly export-only
subdirectory (e.g. `project / "exports" / "stock_tax_export.xlsx"`) by
first decoupling `.ui_state.json` location from the workbook path —
store it directly at the project root via a dedicated helper. That is
the smallest follow-up that further isolates Excel as a pure export
target without risking existing user UI state.

# Cleanup And Refactor Plan

## Guardrails

- Do not change tax outputs while extracting architecture unless a step explicitly targets a correctness bug.
- Do not delete workbook support until backend-owned replacements exist and are tested.
- Keep each step independently releasable.
- Prefer “extract and redirect” over giant rewrites.

## P0: Correctness And Architectural Blockers

### P0.1 Unify year policy into one source of truth

- Goal: Remove duplicate filed/locked/default method policy across `build_stock_tax_workbook.py` and `stock_tax_app.engine.policy`.
- Files touched:
  - `stock_tax_app/engine/policy.py`
  - `build_stock_tax_workbook.py`
  - `test_stock_tax_app_api.py`
  - add new policy regression tests
- Files not to touch:
  - frontend files
  - workbook sheet writer layout
- Acceptance criteria:
  - Only one module defines filed years and default method behavior
  - 2024 remains filed/locked/LIFO
  - 2025 default is explicit and tested, not implied by a fallback comment
- Tests to add/run:
  - pytest for policy parity between engine and workbook adapter
  - existing `py -3 -m pytest -q`
- Risk: Low to medium. Could accidentally change year defaults.
- Rollback strategy: Restore old constants and rerun snapshot/API tests.

### P0.2 Kill split review-state ownership

- Goal: Make sale review state and reconciliation notes live in one backend-owned store only.
- Files touched:
  - `stock_tax_app/engine/ui_state.py`
  - `stock_tax_app/backend/runtime.py`
  - `stock_tax_app/engine/core.py`
  - `build_stock_tax_workbook.py`
  - `test_stock_tax_app_api.py`
- Files not to touch:
  - matching logic
  - frontend router layout
- Acceptance criteria:
  - Sale review PATCH survives recalc
  - Workbook export, if kept, reflects the same review state the API returns
  - Workbook `Review_State` is no longer an independent truth source
- Tests to add/run:
  - sale review survives recalc/write test
  - reconciliation note persistence test
  - existing pytest suite
- Risk: Medium. State migration bug risk.
- Rollback strategy: Keep migration shim that can still read old workbook state while new store is introduced.

### P0.3 Remove silent FX fallback from trusted path

- Goal: Stop calculating “real” results using implicit yearly or hardcoded `22.0` fallback when daily FX is missing.
- Files touched:
  - `build_stock_tax_workbook.py`
  - `stock_tax_app/engine/core.py`
  - tests for FX failure behavior
- Files not to touch:
  - frontend visual layout
- Acceptance criteria:
  - Missing daily FX produces explicit blocked/error behavior
  - No hardcoded fallback is used in the frontend-first calculation path
  - API exposes missing-rate facts clearly
- Tests to add/run:
  - missing daily rate test
  - “no silent yearly fallback” test
  - existing pytest suite
- Risk: Medium to high. Could block current calculations that previously limped through.
- Rollback strategy: Feature-flag strict FX mode temporarily if needed.

### P0.4 Stop routing operators into placeholder screens

- Goal: Ensure `next_action.href` and unresolved-check deep links only target real frontend pages.
- Files touched:
  - `stock_tax_app/engine/core.py`
  - possibly `ui/frontend/src/App.tsx` if route handling needs a safer fallback
- Files not to touch:
  - tax calculation logic
- Acceptance criteria:
  - Current live `GET /api/status` never points to `/audit`, `/fx`, or `/open-positions` until those pages are real
  - Overview CTA never lands on a placeholder page
- Tests to add/run:
  - API status route target test
  - basic frontend router smoke if added later
- Risk: Low.
- Rollback strategy: Restore old href map.

## P1: Remove Excel As Core Dependency

### P1.1 Extract pure engine modules out of `build_stock_tax_workbook.py`

- Goal: Move import, FX, matching, summary, positions, and checks logic into `stock_tax_app/engine/*` modules.
- Files touched:
  - new `stock_tax_app/engine/imports.py`
  - new `stock_tax_app/engine/fx.py`
  - new `stock_tax_app/engine/matching.py`
  - new `stock_tax_app/engine/summary.py`
  - new `stock_tax_app/engine/positions.py`
  - new `stock_tax_app/engine/checks.py`
  - `stock_tax_app/engine/core.py`
  - `build_stock_tax_workbook.py`
- Files not to touch:
  - frontend
  - workbook sheet layout output, except adapter imports
- Acceptance criteria:
  - `engine.core.run()` can assemble `EngineResult` without depending on workbook sheet loaders/writers
  - workbook script becomes a consumer of engine modules, not their owner
- Tests to add/run:
  - parity tests comparing old vs extracted outputs on current fixture data
  - existing pytest suite
- Risk: High. This is the core extraction.
- Rollback strategy: Keep workbook script delegating behind a compatibility wrapper until parity is proven.

### P1.2 Introduce backend-owned project state store

- Goal: Replace workbook-sheet persistence with a real backend state layer.
- Files touched:
  - new state module, likely `stock_tax_app/state/project_store.py`
  - `stock_tax_app/engine/core.py`
  - `stock_tax_app/backend/runtime.py`
  - `build_stock_tax_workbook.py`
- Files not to touch:
  - frontend pages except maybe display of paths if contract changes
- Acceptance criteria:
  - year settings, FX values, instrument map, corporate actions, method selection, locked snapshots, and filed reconciliation inputs can all be loaded without opening `.xlsx`
  - engine read path works when `stock_tax_system.xlsx` does not exist
- Tests to add/run:
  - state roundtrip tests
  - engine run with no workbook present
  - locked snapshot parity tests
- Risk: High.
- Rollback strategy: Keep workbook readback adapter as migration fallback for one release.

### P1.3 Convert workbook generation into export-only adapter

- Goal: Make workbook generation consume backend-owned state and `EngineResult`, instead of being the core runtime path.
- Files touched:
  - `build_stock_tax_workbook.py`
  - `verify_workbook.py`
  - backend route(s) for export/recalc
- Files not to touch:
  - frontend feature pages
- Acceptance criteria:
  - `POST /api/recalculate` can run without writing a workbook
  - workbook generation is triggered by explicit export/rebuild behavior only
  - workbook validator runs only in export path
- Tests to add/run:
  - recalc-without-workbook-write test
  - export-workbook smoke test
  - existing pytest suite
- Risk: Medium.
- Rollback strategy: Temporarily preserve old recalc behavior behind a flag.

## P2: Frontend-First Product Workflow

### P2.1 Ship a real Sales Review screen

- Goal: Replace the placeholder with list/detail review using live `/api/sales` endpoints.
- Files touched:
  - `ui/frontend/src/App.tsx`
  - `ui/frontend/src/lib/api.ts`
  - new sales screen/components
  - possibly minor backend filtering support
- Files not to touch:
  - workbook writer
- Acceptance criteria:
  - operator can list sales, inspect matched lots, and set review state
  - placeholder route is gone
- Tests to add/run:
  - frontend API contract tests
  - backend sales route tests
  - frontend build
- Risk: Medium.
- Rollback strategy: Keep old placeholder route available on a branch if needed.

### P2.2 Make Tax Years actually editable where policy allows

- Goal: Implement real year mutation flow for method, FX mode, tax rate, 100k toggle, and lock/freeze behavior.
- Files touched:
  - `stock_tax_app/backend/routes/years.py`
  - backend state store modules
  - `ui/frontend/src/screens/tax-years-screen.tsx`
  - `ui/frontend/src/lib/api.ts`
- Files not to touch:
  - sales UI unless needed for shared components
- Acceptance criteria:
  - unlocked years can be edited
  - filed/locked years are rejected server-side
  - frontend shows mutation failures honestly
- Tests to add/run:
  - backend route mutation tests
  - locked/filed year protection tests
  - frontend build
- Risk: Medium.
- Rollback strategy: Keep read-only mode behind a toggle.

### P2.3 Ship real FX and Open Positions screens

- Goal: Replace placeholder pages with actual operator review surfaces.
- Files touched:
  - `ui/frontend/src/App.tsx`
  - `ui/frontend/src/lib/api.ts`
  - new FX and open-positions screens/components
  - backend FX mutation endpoints if added
- Files not to touch:
  - workbook export writer unless export drill-down is needed
- Acceptance criteria:
  - operator can inspect missing dates/source labels/manual overrides
  - operator can inspect open position reconciliation and unknown states
- Tests to add/run:
  - route smoke tests
  - frontend build
- Risk: Medium.
- Rollback strategy: Retain read-only fallback cards if richer UI slips.

### P2.4 Add audit summary and explicit export workflow

- Goal: Stop using recalc as a hidden export mechanism and expose export as export.
- Files touched:
  - backend export route(s)
  - `ui/frontend/src/App.tsx`
  - new audit screen/components
  - workbook export adapter
- Files not to touch:
  - raw matching logic
- Acceptance criteria:
  - audit page displays trace counts and snapshot state
  - export action is explicit
  - recalc and export are separate operations
- Tests to add/run:
  - backend export smoke test
  - frontend build
- Risk: Medium.
- Rollback strategy: Keep workbook-only export available via CLI during transition.

## P3: Cleanup, Deletion, And Docs

### P3.1 Archive or delete dead prototype/doc fossils

- Goal: Remove misleading non-runtime artifacts after live replacements exist.
- Files touched:
  - `ui/prototype.html`
  - `ui/DESIGN.md`
  - `docs/api_samples/*.json`
  - `README_OPERATOR.md`
  - `IMPLEMENTATION_NOTES.md`
- Files not to touch:
  - live backend/frontend code
- Acceptance criteria:
  - no remaining doc claims nonexistent routes or workbook-first workflow as the product direction
  - any kept historical docs are clearly labeled `archive`
- Tests to add/run:
  - `rg -n "prototype|mock data|still the deliverable|PATCH /api/years/:year/settings|POST /api/audit/export" docs ui README*.md`
- Risk: Low.
- Rollback strategy: Move files to `docs/archive/` instead of deleting outright.

### P3.2 Remove stale runtime artifacts and legacy fixtures only after migration proof

- Goal: Clean out safe deletion candidates after backend-owned state is real.
- Files touched:
  - `backend_server.out.log`
  - `backend_server.err.log`
  - `temp/stock_tax_system.xlsx`
  - maybe root `stock_tax_system.xlsx` only after test fixture replacement
- Files not to touch:
  - any still-used workbook fixtures before replacement
- Acceptance criteria:
  - deletion candidates are unreferenced by `rg`
  - tests do not rely on deleted artifacts
- Tests to add/run:
  - `py -3 -m pytest -q`
  - route smoke probes
- Risk: Low for logs/temp artifacts, high for root workbook fixture
- Rollback strategy: restore deleted fixture/artifact from git or backups

## Deletion Candidates Vs Migration Candidates

### Migration candidates

- `build_stock_tax_workbook.py`
- `verify_workbook.py`
- `stock_tax_system.xlsx`
- workbook user-state sheets

### Deletion candidates after proof

- `ui/prototype.html`
- `docs/api_samples/*.json`
- `backend_server.out.log`
- `backend_server.err.log`
- `temp/stock_tax_system.xlsx`
- empty `build/`

## First Things To Do

1. Unify policy constants.
2. Kill split review-state ownership.
3. Remove silent FX fallback.
4. Stop status deep-links from sending operators into placeholder pages.

Those four steps reduce real correctness and trust risk before any big extraction starts.

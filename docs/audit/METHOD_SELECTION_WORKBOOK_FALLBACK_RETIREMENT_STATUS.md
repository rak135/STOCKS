# METHOD_SELECTION_WORKBOOK_FALLBACK_RETIREMENT_STATUS

Date: 2026-04-25
Scope: P3.1 - Retire Method_Selection workbook fallback from normal runtime

## Old behavior

- Normal runtime calculation loaded workbook user state via
  `load_existing_user_state` and merged it through
  `merge_project_state_with_legacy_fallback` in `project_store.py`.
- `_merge_method_selection_rows` carried legacy workbook `Method_Selection`
  rows through into the merged user state whenever ProjectState had no
  matching `(year, instrument_id)` entry.
- `_merge_settings_rows` carried the per-year `Settings.Method` column
  through unchanged when ProjectState had no `year_settings[year].method`.
- `build_method_selection` then consumed those merged rows, so a stale
  workbook on disk could silently set both per-instrument method overrides
  and per-year default methods for live calculation.
- `_method_source` returned `workbook_fallback` when ProjectState had no
  method but the workbook `Method_Selection` sheet did.

## New ownership

- Canonical owner of method selection is ProjectState
  (`.stock_tax_state.json`):
  - `ProjectState.method_selection[year][instrument_id]` for per-instrument
    overrides.
  - `ProjectState.year_settings[year]['method']` for the per-year default.
- Workbook `Method_Selection` is no longer a runtime authority. It survives
  only as an export artifact and an explicit migration source.

## Normal runtime rule

- `_merge_method_selection_rows` in `stock_tax_app/state/project_store.py`
  ignores `legacy_rows` entirely; only ProjectState entries are emitted into
  the merged user state.
- `_merge_settings_rows` strips the legacy `Method` column from each
  workbook `Settings` row before the merge, so `build_settings` never sees
  a workbook-derived per-year default method.
- `_method_source` in `stock_tax_app/engine/core.py` no longer consults the
  workbook `Method_Selection` sheet. It returns `static_config` for filed
  years, `project_state` when ProjectState owns the method, otherwise
  `generated_default`.
- The unused `_legacy_has_method_row` helper was removed.

## Method resolution order (effective per (year, instrument))

1. Filed-year hard rule — `policy.filed_method(year)` for filed years.
2. ProjectState per-instrument override — `ProjectState.method_selection[year][instrument_id]`.
3. ProjectState year-level default — `ProjectState.year_settings[year]['method']`.
4. Policy default — `policy.default_method_for(year)` /
   `policy.resolved_method_for(year, None)`.

There is no workbook fallback step in normal runtime.

## Explicit adoption / migration helper

Added in `stock_tax_app/state/project_store.py`:

`adopt_legacy_workbook_method_selection(project_dir, legacy_state, *, overwrite=False) -> dict[str, int]`

Wrapped in `build_stock_tax_workbook.py` for workbook-path callers:

`adopt_legacy_workbook_method_selection(project_dir, workbook_path, *, overwrite=False) -> dict[str, int]`

Behavior:

- Reads workbook `Method_Selection` rows via `load_existing_user_state`.
- Normalizes year (`int`), instrument_id (stripped str), and method
  (uppercased and validated against `FIFO|LIFO|MIN_GAIN|MAX_GAIN`).
- Skips rows with unparseable year, missing instrument_id, or unsupported
  method, counting them as `skipped_invalid`.
- Writes valid rows into `ProjectState.method_selection`. By default
  (`overwrite=False`), existing ProjectState entries are preserved and
  conflicting workbook rows are counted as `skipped_conflicts`. With
  `overwrite=True`, conflicting workbook rows replace the ProjectState
  entry and are counted as `overwritten`.
- Also adopts the legacy per-year default method from `Settings.Method`
  into `ProjectState.year_settings[year]['method']` using the same
  overwrite policy. Counters: `year_defaults_adopted`,
  `year_defaults_overwritten`, `year_defaults_skipped_conflicts`.
- Persists ProjectState only when entries actually change.
- Returns a summary dict with the counters above plus `legacy_rows`
  (number of accepted Method_Selection rows after dedupe) and `adopted`
  (per-instrument rows newly written).

The pre-existing `adopt_legacy_workbook_state` helper continues to migrate
all migrated domains (including Method_Selection) and remains the right
choice when an operator wants to bulk-adopt everything at once.

## Conflict / overwrite rules

- ProjectState always wins in normal runtime — workbook
  `Method_Selection` and `Settings.Method` are never automatically
  consulted.
- Explicit adoption with `overwrite=False` only fills gaps in
  ProjectState; existing per-instrument and per-year entries are
  preserved.
- Explicit adoption with `overwrite=True` replaces conflicting
  ProjectState entries with workbook values.
- Filed-year and locked-year guards (`policy.is_filed`, `policy.is_locked`,
  `check_year_mutation`) are unchanged. PATCH-driven mutations on a locked
  year continue to return 409.

## Workbook export behavior

- Workbook export still writes a `Method_Selection` sheet via
  `_write_method_selection` in `stock_tax_app/engine/workbook_export.py`.
- The exported rows now reflect the canonical effective state derived from
  ProjectState (`build_method_selection` over the merged ProjectState-only
  user state plus per-year defaults from `policy`). The exported workbook
  is output compatibility, not runtime authority.
- Existing export tests
  (`test_workbook_export_reflects_project_state_for_migrated_domains` and
  related) remain green.

## Tests added/updated

`test_project_state_store.py`:

- Updated `test_legacy_workbook_fallback_works_and_can_be_adopted`:
  - Asserts the workbook `Settings.Tax rate` fallback still works.
  - Asserts the workbook `Method_Selection` sheet no longer flows into
    runtime — `sale.method` is `policy.default_method_for(year)` and
    `method_source` is not `workbook_fallback`.
  - Confirms `adopt_legacy_workbook_state` still migrates both.
- Added `test_runtime_ignores_workbook_method_selection_when_project_state_missing`:
  asserts runtime uses policy default, `method_source` is not
  `workbook_fallback`, and no `.stock_tax_state.json` is silently created.
- Added `test_explicit_method_selection_adoption_migrates_workbook_rows`:
  asserts the helper writes into ProjectState and that runtime picks the
  adopted method up after migration.
- Added `test_project_state_method_beats_workbook_method_selection_conflict`:
  asserts ProjectState wins over a conflicting workbook row.
- Added `test_explicit_method_selection_adoption_overwrite_false_preserves_existing`:
  asserts `overwrite=False` increments `skipped_conflicts` and keeps the
  ProjectState value.
- Added `test_explicit_method_selection_adoption_overwrite_true_replaces_conflicts`:
  asserts `overwrite=True` increments `overwritten` and applies the
  workbook value.
- Added `test_explicit_method_selection_adoption_skips_invalid_methods`:
  asserts unparseable year, empty instrument, and unsupported method rows
  are counted as `skipped_invalid` and a valid lowercase method is
  uppercased before adoption.

`test_stock_tax_app_api.py` — kept all existing coverage:

- `test_api_patch_year_updates_method_for_unlocked_year` — PATCH method
  persists year-level ProjectState default and `method_source` is
  `project_state`.
- `test_api_patch_year_method_migrates_legacy_uniform_instrument_rows` —
  per-instrument override behavior.
- `test_year_settings_patch_survives_recalc_and_runtime_reload` — PATCH
  year-method survives recalc and runtime reload.
- `test_get_years_reflects_project_state_values_and_provenance_after_patch`
  — `method_source` is `project_state` post-PATCH.
- `test_method_selection_per_instrument_override_beats_year_default`
  (existing in `test_project_state_store.py` as
  `test_per_instrument_method_override_beats_year_method_default`) — per-
  instrument override beats year-level default.

## Commands run and results

- `py -3 -m pytest -q test_stock_tax_app_api.py` -> 69 passed
- `py -3 -m pytest -q test_project_state_store.py` -> 28 passed
- `py -3 -m pytest -q test_root_excel_absent.py` -> 4 passed
- `py -3 -m pytest -q` -> 103 passed
- `py -3 test_locked_year_roundtrip.py` -> PASS (3-phase script output;
  expected controlled stale-snapshot guidance in pass 2)

`verify_workbook.py` was not invoked in this slice; it is reserved for
explicit verification against a generated temp/export path and is not part
of automated runtime testing.

## Repo state

Repo remains green. Frontend was untouched, so no frontend build was run.

## Remaining workbook fallback domains (intentionally unchanged in P3.1)

- Settings (year_settings) fallback — `tax_rate`, `fx_method`,
  `apply_100k`, `notes` columns still flow from workbook `Settings` when
  ProjectState has no entry. Only the `Method` column was retired in this
  slice.
- FX_Yearly and FX_Daily fallback paths.
- Instrument_Map fallback paths.
- Corporate_Actions fallback paths.
- Locked_Years fallback path.
- Frozen_Inventory / Frozen_Lot_Matching / Frozen_Snapshots fallback
  paths.
- Filed_Year_Reconciliation fallback path.

These remain out of scope for this slice and continue to follow existing
explicit adoption and fallback rules.

## Recommended next slice

P3.2 — Retire the remaining year_settings (Settings sheet) workbook
fallback. Mirror the Method_Selection retirement: have
`_merge_settings_rows` stop carrying legacy `Tax rate`, `FX method`,
`Apply 100k exemption?`, and `Notes` from the workbook into runtime;
extend `adopt_legacy_workbook_state` (or add a focused helper) to migrate
those columns explicitly; and update `_year_settings_source` so it stops
returning `workbook_fallback` for normal runtime.

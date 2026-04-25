# P3.2 — Year-Settings Workbook Fallback Retirement Status

**Slice:** P3.2  
**Date:** 2026-04-25  
**Status:** RETIRED (Settings.Tax rate / FX method / Apply 100k / Notes)

---

## 1. Old Behavior (before P3.2)

During normal runtime, `_merge_settings_rows` (project_store.py) would:
1. Start with the raw legacy workbook `Settings` rows (Tax rate, FX method, Apply 100k exemption?, Notes all present).
2. Override with `ProjectState.year_settings` values where they existed.
3. Pass the merged rows to `build_settings()` (build_stock_tax_workbook.py), which read Tax rate / FX method / Apply 100k / Notes from the merged rows.
4. If ProjectState had no value for a field, the **workbook's value was silently used as truth**.

`_year_settings_source` (engine/core.py) returned `"workbook_fallback"` if the year appeared in the workbook `Settings` sheet but not in `ProjectState.year_settings`.

`GET /api/years` items therefore reported `settings_source: "workbook_fallback"` for such years.

P3.1 had already retired `Settings.Method` (per-year default method) from this path; P3.2 retires the four remaining fields.

---

## 2. New Ownership Rule (after P3.2)

**ProjectState always owns year settings in normal runtime.**

| Source | Rule |
|---|---|
| `ProjectState.year_settings[year]["tax_rate"]` | Used as-is if present. |
| `ProjectState.year_settings[year]["fx_method"]` | Used as-is if present. |
| `ProjectState.year_settings[year]["apply_100k"]` | Used as-is if present. |
| `ProjectState.year_settings[year]["notes"]` | Used as-is if present. |
| Workbook `Settings.Tax rate` | **Ignored in normal runtime.** |
| Workbook `Settings.FX method` | **Ignored in normal runtime.** |
| Workbook `Settings.Apply 100k exemption?` | **Ignored in normal runtime.** |
| Workbook `Settings.Notes` | **Ignored in normal runtime.** |
| Policy/generated default | Used when ProjectState has no value. |

---

## 3. Normal Runtime Rule

`_merge_settings_rows` now strips `"Tax rate"`, `"FX method"`, `"Apply 100k exemption?"`, and `"Notes"` from legacy rows before merging. Only `ProjectState.year_settings` values are applied.

`_year_settings_source` returns:
- `"project_state"` — year is in `ProjectState.year_settings`
- `"generated_default"` — year is NOT in `ProjectState.year_settings` (workbook_fallback never returned for these fields)

The workbook engine (`build_settings`) therefore receives only ProjectState-owned values or defaults.

---

## 4. Explicit Adoption / Migration Helper

```python
from stock_tax_app.state import project_store

summary = project_store.adopt_legacy_workbook_year_settings(
    project_dir,
    workbook_path,
    overwrite=False,   # default: fill only missing fields
)
# summary keys:
#   legacy_rows        — valid Settings rows (parseable year) seen
#   skipped_invalid    — rows with unparseable year
#   fields_adopted     — fields written for the first time
#   fields_overwritten — fields replaced (only when overwrite=True)
#   fields_skipped     — fields skipped (overwrite=False, conflict)
```

This is the **only supported path** for migrating legacy workbook Settings into ProjectState.

---

## 5. Field Validation / Normalization Rules

| Field | Validation | Normalization |
|---|---|---|
| `tax_rate` | Must be `float` in `[0.0, 1.0]`. Values outside range or non-numeric are skipped. | Stored as `float`. |
| `fx_method` | Must be in `SUPPORTED_FX_METHODS` (`FX_UNIFIED_GFR`, `FX_DAILY_CNB`). Invalid values are skipped. | Uppercased string. |
| `apply_100k` | Non-`None` values are accepted. | Coerced to `bool`. |
| `notes` | Blank/`None` values are skipped. | Stripped string. |

---

## 6. Conflict / Overwrite Rules

| Scenario | `overwrite=False` | `overwrite=True` |
|---|---|---|
| Field not in ProjectState | Written (adopted) | Written (adopted) |
| Field in ProjectState, same value | No-op | No-op |
| Field in ProjectState, different value | **Skipped** (fields_skipped++) | **Replaced** (fields_overwritten++) |
| Year not in ProjectState at all | All valid fields written | All valid fields written |

ProjectState always wins in normal runtime regardless of overwrite flag. The adoption helper is a manual, operator-triggered action.

---

## 7. Effective Source Resolution Order

For each year setting field during normal runtime:

1. `ProjectState.year_settings[year][field]` — if present: used, source=`project_state`
2. Policy/generated default (e.g., `DEFAULT_TAX_RATE=0.15`, `DEFAULT_FX_METHOD="FX_UNIFIED_GFR"`, `DEFAULT_APPLY_100K=False`) — source=`generated_default`
3. Workbook `Settings` sheet — **never** used automatically

---

## 8. Export Behavior

The workbook export (`write_workbook`) still writes a `Settings` sheet populated from:
- `ProjectState.year_settings` values (if present), rendered into the merged Settings rows
- Policy defaults for fields not in ProjectState

The exported workbook **does not become authority**. Reading it back via `load_existing_user_state` during a subsequent runtime will not restore Settings values (they are stripped in `_merge_settings_rows`). Re-adoption via `adopt_legacy_workbook_year_settings` remains the only path.

---

## 9. Tests Added / Updated

### Updated (test_project_state_store.py)
- `test_legacy_workbook_fallback_works_and_can_be_adopted` → **split into two**:
  - `test_legacy_workbook_settings_fallback_retired_p3_2` — asserts runtime uses DEFAULT_TAX_RATE (not workbook value) and settings_source=`generated_default`
  - `test_legacy_workbook_settings_adoption_still_works_after_p3_2` — asserts explicit adoption still migrates values

### New (test_project_state_store.py)
| Test | Req |
|---|---|
| `test_p3_2_runtime_ignores_workbook_tax_rate_when_project_state_missing` | A |
| `test_p3_2_runtime_ignores_workbook_fx_method_when_project_state_missing` | B |
| `test_p3_2_runtime_ignores_workbook_apply_100k_when_project_state_missing` | C |
| `test_p3_2_get_years_does_not_report_workbook_fallback_for_settings_fields` | E |
| `test_p3_2_adopt_legacy_workbook_year_settings_migrates_into_project_state` | F |
| `test_p3_2_project_state_wins_over_workbook_settings_after_adoption_attempt` | G |
| `test_p3_2_adopt_year_settings_overwrite_false_fills_only_missing_fields` | H |
| `test_p3_2_adopt_year_settings_overwrite_true_replaces_existing_fields` | I |
| `test_p3_2_adopt_year_settings_skips_invalid_tax_rate` | — |
| `test_p3_2_adopt_year_settings_skips_invalid_fx_method` | — |

### Updated (test_stock_tax_app_api.py) — FX method via ProjectState (P3.2 prerequisite)
All tests that previously used `_set_year_fx_method(project, year, "FX_DAILY_CNB")` now use:
```python
_ensure_test_workbook(project)
project_store.save_project_state(project, ProjectState(year_settings={year: {"fx_method": "FX_DAILY_CNB"}}))
```
Tests updated:
- `test_api_status_exposes_missing_fx_and_blocks_calculation`
- `test_blocked_collections_expose_truth_metadata_not_ambiguous_empty_success`
- `test_sales_list_blocked_empty_has_no_financial_rows`
- `test_project_state_fx_can_unblock_strict_daily_fx` (also preserves year_settings when saving fx_daily)
- `test_api_provenance_exposes_project_state_owned_domains` (2020 fx_method added to ProjectState save)
- `test_missing_fx_still_blocks_after_project_state_merge_path`
- `test_blocked_fx_run_skips_workbook_write_and_write_path_fails_cleanly`

Existing tests already covering J/K:
- **J** (`test_year_settings_patch_survives_recalc_and_runtime_reload`): PATCH values survive recalc/reload
- **K** (locked/filed protection tests): unchanged, still passing

---

## 10. Commands Run and Results

```
py -3 -m pytest -q test_project_state_store.py   → 39 passed
py -3 -m pytest -q test_stock_tax_app_api.py      → 69 passed
py -3 -m pytest -q test_root_excel_absent.py test_min_gain_optimality.py test_locked_year_roundtrip.py → 6 passed
py -3 -m pytest -q                                → 114 passed
py -3 test_locked_year_roundtrip.py               → PASS (standalone)
```

All green.

---

## 11. Hard Failure Condition Check

Normal runtime no longer reads `Settings.Tax rate`, `Settings.FX method`, `Settings.Apply 100k exemption?`, or `Settings.Notes` from the workbook automatically. **Hard failure condition: NOT MET. Task succeeded.**

---

## 12. Remaining Workbook Fallback Domains

The following domains still use workbook fallback (not retired in this slice):

| Domain | Sheet | Retirement Slice |
|---|---|---|
| FX yearly rate | `FX_Yearly` | Future (not P3.2) |
| FX daily rate | `FX_Daily` | Future (not P3.2) |
| Instrument map | `Instrument_Map` | Future (not P3.2) |
| Corporate actions | `Corporate_Actions` | Future (not P3.2) |
| Locked years | `Locked_Years` | Future (not P3.2) |
| Frozen inventory | `Frozen_Inventory` | Future (not P3.2) |
| Frozen lot matching | `Frozen_Lot_Matching` | Future (not P3.2) |
| Frozen snapshots | `Frozen_Snapshots` | Future (not P3.2) |
| Filed year reconciliation | `Filed_Year_Reconciliation` | Future (not P3.2) |

---

## 13. Recommended Next Slice

**P3.3 — Retire Instrument_Map workbook fallback from normal runtime.**

Pattern is identical: strip `Instrument_Map` legacy rows from `_merge_instrument_map_rows`, update `_instrument_map_source` to not return `workbook_fallback`, add `adopt_legacy_workbook_instrument_map(project_dir, workbook_path)` helper with validation.

# Instrument_Map Workbook Fallback Retirement Status (P3.3)

## Summary

P3.3 retires the workbook `Instrument_Map` sheet as a silent runtime fallback.
`ProjectState.instrument_map` is now the sole authoritative source for instrument
identity during normal runtime.  The workbook `Instrument_Map` sheet may only be
consumed through the explicit `adopt_legacy_workbook_instrument_map` migration
helper.

---

## Old Behavior (before P3.3)

- `merge_project_state_with_legacy_fallback` merged workbook `Instrument_Map` rows
  into the effective runtime `user_state` (`_merge_instrument_map_rows`).
- If `ProjectState.instrument_map` had no entry for a symbol, the workbook row was
  silently used as a fallback during `build_instrument_map` / `apply_instrument_map`.
- `_instrument_map_source` in `core.py` reported `"workbook_fallback"` when a symbol
  had a workbook row but no `ProjectState` entry.
- A stale or incorrect workbook `Instrument_Map` could silently map tickers/instruments
  and affect grouping, pairing, and reporting without any explicit operator action.

---

## New Ownership (after P3.3)

- `ProjectState.instrument_map` is the sole source for instrument mapping in normal
  runtime.
- The workbook `Instrument_Map` sheet is never read as a runtime fallback.
- Workbook data may only enter `ProjectState` through the explicit adoption helper.

---

## Normal Runtime Rule

```
instrument resolution order:
  1. ProjectState.instrument_map[symbol]  →  source = "project_state"
  2. generated/default (symbol = instrument_id, empty ISIN/name)  →  source = "generated_default"

workbook Instrument_Map:  NEVER used automatically in normal runtime (P3.3)
```

---

## Explicit Adoption / Migration Path

```python
from stock_tax_app.state import adopt_legacy_workbook_instrument_map

summary = adopt_legacy_workbook_instrument_map(
    project_dir,
    workbook_path,
    overwrite=False,  # default: fill missing only
)
# summary keys: legacy_rows, skipped_invalid, adopted, overwritten, skipped_conflicts
```

- Reads `Instrument_Map` rows from an existing workbook via `load_existing_user_state`.
- Normalizes each row through `_normalize_instrument_map_entry`.
- Writes only missing entries into `ProjectState` by default (`overwrite=False`).
- With `overwrite=True`, replaces existing `ProjectState` entries.
- Persists the updated `ProjectState` atomically.

---

## Validation / Normalization Rules

| Field | Rule |
|-------|------|
| `Yahoo Symbol` | Required (row key). Rows with blank/missing symbol are skipped and counted in `skipped_invalid`. |
| `Instrument_ID` | Preserved as-is; defaults to `Yahoo Symbol` if blank. |
| `ISIN` | Preserved as stripped string; empty string if absent. |
| `Instrument name` | Preserved as stripped string; empty string if absent. |
| `Notes` | Preserved as stripped string; empty string if absent. |

Invalid rows (blank `Yahoo Symbol`) are skipped and counted. No guessing.

---

## Conflict / Overwrite Rules

| Scenario | `overwrite=False` | `overwrite=True` |
|----------|-------------------|------------------|
| Symbol absent in ProjectState | Writes entry (`adopted += 1`) | Writes entry (`adopted += 1`) |
| Symbol exists in ProjectState (different value) | Skips (`skipped_conflicts += 1`) | Replaces (`overwritten += 1`) |
| Symbol exists in ProjectState (same value) | Skips (`skipped_conflicts += 1`) | Replaces (`overwritten += 1`) |

`ProjectState` always wins in normal runtime (no adoption call needed to enforce this).

---

## Instrument Resolution Order

```
Normal runtime (read-only, deterministic):
  1. ProjectState.instrument_map[symbol]     → project_state
  2. generated default (symbol as instrument_id)  → generated_default

Explicit adoption (one-time migration):
  adopt_legacy_workbook_instrument_map(...)  → writes into ProjectState
```

---

## API / Provenance Behavior

- `instrument_map_source` field on `Sell` and `OpenPosition` responses:
  - `"project_state"` — symbol is in `ProjectState.instrument_map`
  - `"generated_default"` — no ProjectState entry; runtime uses symbol as instrument_id
  - `"workbook_fallback"` — **never reported** after P3.3

- Existing API response contract is preserved; no new fields added.

---

## Workbook Export Behavior

- `write_calculation_result` / `write_workbook` still writes an `Instrument_Map` sheet.
- The exported sheet is built from the effective merged state
  (`merge_project_state_with_legacy_fallback` → `_merge_instrument_map_rows`).
- After P3.3, `_merge_instrument_map_rows` only emits rows for symbols present in
  `ProjectState.instrument_map`.  Symbols with no `ProjectState` entry produce no
  workbook row (they resolve to generated default at runtime).
- The exported workbook is never re-read as runtime authority.

---

## Tests Added / Updated

### Updated
| Test | Change |
|------|--------|
| `test_workbook_instrument_map_fallback_still_works` | Renamed to `test_p3_3_workbook_instrument_map_no_longer_fallback`; now verifies that workbook-only instrument map → `instrument_id == symbol` (generated default), `instrument_map_source == "generated_default"`. |

### Added
| Test | Covers |
|------|--------|
| `test_p3_3_workbook_instrument_map_no_longer_fallback` | A: Runtime ignores workbook Instrument_Map when ProjectState is missing. |
| `test_p3_3_adopt_instrument_map_migrates_entries` | B: Explicit adoption migrates workbook rows into ProjectState; runtime/API reflects adopted mapping. |
| `test_p3_3_adopt_overwrite_false_skips_conflicts` | D: `overwrite=False` skips entries already in ProjectState. |
| `test_p3_3_adopt_overwrite_true_replaces_existing` | E: `overwrite=True` replaces existing ProjectState entries. |
| `test_p3_3_adopt_invalid_rows_skipped_with_counters` | F: Rows with blank `Yahoo Symbol` are skipped and counted in `skipped_invalid`. |
| `test_p3_3_project_state_instrument_map_survives_recalc` | G: Existing ProjectState mapping is preserved through repeated recalc/reload. |
| `test_p3_3_instrument_map_source_never_workbook_fallback` | I: `instrument_map_source` must never report `"workbook_fallback"` after P3.3. |

### Pre-existing tests that remain green
| Test | What it verifies |
|------|-----------------|
| `test_project_state_instrument_map_beats_workbook_fallback` | C: ProjectState wins when both ProjectState and workbook have conflicting entries. |
| `test_explicit_legacy_adoption_migrates_instrument_map_without_overwriting_by_default` | D+E via `adopt_legacy_workbook_state` (the omnibus helper). |
| `test_default_generated_instrument_map_still_works` | Generated default resolution when no source provides an entry. |
| `test_workbook_export_reflects_project_state_instrument_map` | H: Export writes Instrument_Map from canonical ProjectState/effective state. |

---

## Commands Run

```
py -3 -m pytest -q test_project_state_store.py
py -3 -m pytest -q test_stock_tax_app_api.py
py -3 -m pytest -q test_root_excel_absent.py
py -3 -m pytest -q
py -3 test_locked_year_roundtrip.py
```

---

## Files Changed

| File | Change |
|------|--------|
| `stock_tax_app/state/project_store.py` | `_merge_instrument_map_rows`: ignore legacy rows (P3.3). Add `adopt_legacy_workbook_instrument_map`. |
| `stock_tax_app/state/__init__.py` | Export `adopt_legacy_workbook_instrument_map`. |
| `stock_tax_app/engine/core.py` | `_instrument_map_source`: remove `workbook_fallback` branch; only `project_state` or `generated_default`. |
| `test_project_state_store.py` | Update retired fallback test; add P3.3 tests. |
| `docs/audit/INSTRUMENT_MAP_WORKBOOK_FALLBACK_RETIREMENT_STATUS.md` | This file. |

---

## Remaining Workbook Fallback Domains (not retired in P3.3)

| Domain | Status |
|--------|--------|
| `FX_Yearly` | Still fallback in runtime (not retired in P3.3) |
| `FX_Daily` | Still fallback in runtime (not retired in P3.3) |
| `Corporate_Actions` | Still fallback in runtime (not retired in P3.3) |
| `Locked` / `Frozen` / `Filed` | Still fallback in runtime (not retired in P3.3) |

---

## Recommended Next Slice

**P3.4 — Retire FX_Yearly / FX_Daily workbook fallback from normal runtime.**

`ProjectState.fx_yearly` and `ProjectState.fx_daily` should become the sole runtime
sources for FX rates.  Explicit adoption helpers already exist
(`adopt_legacy_workbook_state` covers FX).  A focused `adopt_legacy_workbook_fx`
helper (or separate yearly/daily helpers) should be added and the runtime merge
(`_merge_fx_yearly_rows`, `_merge_fx_daily_rows`) updated to ignore legacy rows.

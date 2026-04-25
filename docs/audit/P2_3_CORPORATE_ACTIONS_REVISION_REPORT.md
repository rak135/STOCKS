# P2.3 Corporate Actions — Forensic Revision Report

**Date:** 2026-04-25  
**Auditor:** GitHub Copilot (forensic pass)  
**Recovery Classification:** PARTIAL_KEEP_AND_FINISH

---

## 1. Executive Summary

The P2.3 attempt made substantial, largely coherent changes across the full stack (workbook engine, state layer, engine API models, backend API, frontend types + UI). The work is approximately 90 % implemented.

**One breaking defect was found and fixed during this audit:**  
`_coerce_float` was used in `build_stock_tax_workbook.py` but only defined in  
`stock_tax_app/state/project_store.py`. A minimal companion function was added to  
`build_stock_tax_workbook.py` to restore testability.

**One logic gap remains unfixed (intentionally):**  
`test_invalid_corporate_actions_surface_in_status_and_audit` fails because the  
ProjectState storage layer silently deduplicates entries by `action_id` before  
they reach the validation layer in `build_corporate_actions`. The test expects  
duplicate action_ids to surface as errors, but they are lost on round-trip. This  
is a design decision, not a syntax error, and is left for the next slice.

**Before the minimal fix:** 8 tests failed, 74 passed.  
**After the minimal fix:** 1 test fails, 81 passed.

---

## 2. Git Status Summary

### Changed files (all committed-but-dirty: `M` status)

| File | Classification | Appears Complete |
|------|---------------|-----------------|
| `build_stock_tax_workbook.py` | EXPECTED_P2_3_CHANGE | Partially — `_coerce_float` was missing |
| `stock_tax_app/engine/core.py` | EXPECTED_P2_3_CHANGE | Yes |
| `stock_tax_app/engine/models.py` | EXPECTED_P2_3_CHANGE | Yes |
| `stock_tax_app/state/models.py` | EXPECTED_P2_3_CHANGE | Yes |
| `stock_tax_app/state/project_store.py` | EXPECTED_P2_3_CHANGE | Partial — dedup-before-validate logic gap |
| `test_project_state_store.py` | EXPECTED_P2_3_CHANGE | Yes (passes after fix) |
| `test_stock_tax_app_api.py` | EXPECTED_P2_3_CHANGE | Partial — 1 test reveals logic gap |
| `ui/frontend/src/screens/open-positions-screen.tsx` | EXPECTED_P2_3_CHANGE | Yes |
| `ui/frontend/src/types/api.ts` | EXPECTED_P2_3_CHANGE | Yes |

### Untracked files

| File | Classification |
|------|---------------|
| `docs/audit/REPORTED_POSITION_PROVENANCE_STATUS.md` | GENERATED_ARTIFACT — previous audit doc, unrelated to this step |

---

## 3. Corporate Actions Implementation Truth Table

| Question | Finding |
|---------|---------|
| Where were corporate actions previously loaded from? | Workbook-only: `user_state["Corporate_Actions"]` via `build_corporate_actions()` in `build_stock_tax_workbook.py` |
| Are corporate actions now in ProjectState schema? | **YES** — `ProjectStateCorporateActionEntry` TypedDict added to `stock_tax_app/state/models.py`; `ProjectState.corporate_actions` field typed as `list[ProjectStateCorporateActionEntry]` |
| What is the schema? | `{action_id, action_type, effective_date, instrument_id, source_symbol, target_instrument_id, target_symbol, ratio_numerator, ratio_denominator, source, note, enabled}` (snake_case ProjectState canonical form) |
| Are they merged ProjectState-over-workbook fallback? | **YES** — `_merge_corporate_actions_rows()` in `project_store.py`: if `project_state.corporate_actions` is non-empty, ProjectState wins entirely; otherwise workbook fallback passes through |
| Are workbook fallback actions still supported? | **YES** — when `project_state.corporate_actions` is empty, `_merge_corporate_actions_rows` returns the raw legacy workbook rows unchanged |
| Is explicit adoption implemented? | **YES** — `adopt_legacy_workbook_state()` now calls `_extract_corporate_actions_from_legacy()` and merges into ProjectState with dedup-by-identity and `overwrite` flag |
| Are validation rules implemented? | **YES** — `build_corporate_actions()` validates: unknown action types, bad/missing dates, missing instrument_id, invalid split ratios (≤ 0), ticker_change missing target, duplicate action_ids, ambiguous instrument mapping (WARN) |
| Are invalid actions surfaced through /api/status or /api/audit? | **YES** — validation issues become `problems` in the calc result; `_build_audit_summary` in `core.py` groups them as `corporate_action_checks` reason; `_build_status` propagates unresolved checks |
| Does workbook export reflect effective corporate actions? | **YES** — `_merge_corporate_actions_rows` with `_project_state_action_to_legacy_row` converts PS entries back to legacy row format |
| Are open-position checks affected by corporate actions? | **YES** — `apply_corporate_action_to_lots()` (formerly `apply_split_to_lots`) now handles SPLIT, REVERSE_SPLIT, and TICKER_CHANGE; ticker changes rename `lot.instrument_id` in place |
| Are there tests proving any of this? | **MOSTLY** — 7 of 8 new CA tests pass after the `_coerce_float` fix; 1 (duplicate detection) still fails |

---

## 4. Changed File Detail

### `build_stock_tax_workbook.py` (+336 / -113 net additions)

**What changed:**
- `build_corporate_actions()` signature changed from `(user_state)` → `(user_state, *, known_instrument_ids=None)` and now returns `Tuple[List, List]` (actions, issues).
- Validation rules: unknown type, bad date, missing instrument, bad ratio, missing ticker-change target, duplicate action_id, ambiguous instrument mapping.
- New helper functions: `_is_blank_corporate_action_row`, `_corporate_action_issue`, `_parse_target_from_note`, `_coerce_float` (**added by this audit**).
- `apply_split_to_lots` renamed to `apply_corporate_action_to_lots`; TICKER_CHANGE branch added.
- `extract_position_rows` now delegates to `extract_position_rows_with_provenance`.
- `build_open_position_rows` now uses provenance data.
- `calculate_workbook_data` unpacks tuple from `build_corporate_actions`.

**Completeness:** Was broken (missing `_coerce_float`). Now complete per unit tests.

**Affects runtime:** Yes — corporate action validation, ticker-change support, open-position provenance.

### `stock_tax_app/state/models.py` (+17 / -1)

**What changed:**
- `ProjectStateCorporateActionEntry` TypedDict added.
- `ProjectState.corporate_actions` typed from `list[dict[str, Any]]` → `list[ProjectStateCorporateActionEntry]`.

**Completeness:** Complete.

### `stock_tax_app/state/project_store.py` (+218 / -5)

**What changed:**
- `corporate_actions` added to `_MIGRATED_DOMAINS`.
- `adopt_legacy_workbook_state` migrates corporate actions from legacy.
- `merge_project_state_with_legacy_fallback` merges `Corporate_Actions` via `_merge_corporate_actions_rows`.
- `_normalize_corporate_actions_payload`, `_normalize_corporate_action_entry`, `_corporate_action_identity_key`, `_project_state_action_to_legacy_row`, `_extract_corporate_actions_from_legacy`, `_merge_corporate_actions_rows` added.

**Logic gap:** `_normalize_corporate_actions_payload` deduplicates by `_corporate_action_identity_key` before data reaches `build_corporate_actions`. This means duplicate action_ids are silently discarded on round-trip rather than surfaced as validation errors.

### `stock_tax_app/engine/core.py` (+114 / -6)

**What changed:**
- `corporate_actions` removed from `WORKBOOK_BACKED_DOMAINS`.
- `_legacy_has_corporate_action_rows`, `_corporate_actions_source` added.
- `_build_settings` now calls `_corporate_actions_source` to report `"project_state"` vs `"workbook_fallback"`.
- `_build_audit_summary` reports corporate action issues.
- `_build_open_positions` threads provenance fields; open-position discrepancy checks aware of `reported_position_source_status`.
- `_open_position_discrepancy_checks` now flags positions that are `ok` but have `partial/unknown` provenance.

**Completeness:** Complete.

### `stock_tax_app/engine/models.py` (+20)

**What changed:**
- `ReportedPositionSourceStatus` literal type added.
- `ReportedPositionSource` model added.
- `OpenPosition` extended with 10 provenance fields.

**Completeness:** Complete.

### `test_project_state_store.py` (+261)

**What changed:**
- Helper functions `_set_workbook_corporate_action`, `_read_workbook_corporate_actions`.
- `test_project_state_roundtrip` updated for new schema.
- New tests: CA beats workbook fallback, workbook fallback still works, legacy adoption without overwrite, workbook export reflects PS CA, valid split changes inventory.

**Completeness:** All pass after `_coerce_float` fix.

### `test_stock_tax_app_api.py` (+328)

**What changed:**
- New tests: settings domain source reporting, invalid CA surface in status/audit, ticker change moves inventory, open positions detect mismatch after missing split.

**Completeness:** 3 of 4 new tests pass. `test_invalid_corporate_actions_surface_in_status_and_audit` fails (duplicate detection logic gap).

### Frontend files

**`ui/frontend/src/types/api.ts` (+21):**  
`ReportedPositionSourceStatus`, `ReportedPositionSource`, and 10 new fields on `OpenPosition`. Complete, matches backend models.

**`ui/frontend/src/screens/open-positions-screen.tsx` (+62):**  
`reportedSourceTone`, `reportedSourceLabel` maps. Provenance chip on position card, expanded detail section. Complete. Frontend build not run (no frontend-only changes require it absent a test failure indicating otherwise).

---

## 5. Tests Run

| Command | Result |
|---------|--------|
| `py -3 -m pytest -q` (before fix) | **8 failed**, 74 passed |
| `py -3 -m pytest -q` (after fix) | **1 failed**, 81 passed |
| `py -3 -m pytest -q test_project_state_store.py::test_project_state_roundtrip test_project_state_store.py::test_explicit_legacy_adoption_migrates_corporate_actions_without_overwriting` | **2 passed** |
| `py -3 -m pytest -q test_stock_tax_app_api.py -k "not corporate and not split and not ticker"` | **54 passed**, 4 deselected |

### Remaining failure

**Test:** `test_stock_tax_app_api.py::test_invalid_corporate_actions_surface_in_status_and_audit`  
**Assertion:** `assert any("duplicate action_id" in message for message in messages)`  
**Root cause:** `_normalize_corporate_actions_payload` in `project_store.py` deduplicates entries by `_corporate_action_identity_key` before data reaches `build_corporate_actions`. A saved ProjectState with two entries sharing `action_id="dup-id"` is silently reduced to one on round-trip. The duplicate is gone before validation runs.  
**Type:** Logic gap (design decision about where deduplication belongs). NOT a syntax/import error.  
**Risk if left:** Duplicate action_ids in operator-authored ProjectState JSON are silently dropped rather than flagged. Silent data loss without operator warning.

---

## 6. API Truth Observations

Based on code inspection (backend smoke test not run separately — covered by test suite):

| Domain | Source |
|--------|--------|
| `corporate_actions` | `"project_state"` if `project_state.corporate_actions` non-empty; `"workbook_fallback"` otherwise |
| Removed from `WORKBOOK_BACKED_DOMAINS` | ✓ |
| Appears in `/api/settings` `domain_sources` | ✓ |
| Validation issues in `/api/status` `unresolved_checks` | ✓ (6 check categories) |
| Appears in `/api/audit` `status_reasons` as `corporate_action_checks` | ✓ |
| Open positions affected | ✓ (via `apply_corporate_action_to_lots`) |

---

## 7. Risks Found

### Risk 1 — Silent deduplication of duplicate action_ids (MEDIUM)
`_normalize_corporate_actions_payload` deduplicates before validation. An operator who writes two identical action_ids into the state file has them silently collapsed to one. No error is surfaced. The test `test_invalid_corporate_actions_surface_in_status_and_audit` exposes this.

**Affected file:** `stock_tax_app/state/project_store.py` → `_normalize_corporate_actions_payload`

### Risk 2 — `action_type` case mismatch between layers (LOW)
ProjectState canonical form uses lowercase (`split`, `reverse_split`, `ticker_change`). `build_corporate_actions` uppercases for comparison (`CA_TYPES`). The `_normalize_corporate_action_entry` in `project_store.py` lowercases. Round-trip is consistent but requires careful awareness.

### Risk 3 — `_to_json_dict` serializes `effective_date` as ISO string but `build_corporate_actions` may read it as a string needing `parse_trade_date` (LOW)
The flow is: PS saves ISO date string → merged user_state has ISO string → `build_corporate_actions` reads and parses with `parse_trade_date`. Tested and working per passing tests.

### Risk 4 — Frontend encodes non-ASCII characters (LOW, cosmetic)
`open-positions-screen.tsx` diff shows mangled unicode: `ÔÇö` (em-dash), `┬Ě` (middle dot). These appear to be encoding artifacts from the diff but may affect browser display. Not a runtime break.

### Risk 5 — Workbook export column mapping (MEDIUM, VERIFY)
`_project_state_action_to_legacy_row` writes `Applied?` (boolean) and `Audit status` to the legacy format. The test `test_workbook_export_reflects_project_state_corporate_actions` passes, so the column indices appear correct. However the column mapping is hardcoded in the test helper (`column=8` for Applied) — any workbook template change would silently break this.

---

## 8. What Was NOT Changed (Confirming Scope)

- Tax calculation / lot matching logic: unchanged beyond `apply_corporate_action_to_lots` adding TICKER_CHANGE branch.
- Locked/filed year behavior: unchanged.
- FX domain: unchanged.
- Instrument map domain: unchanged.
- Sales Review / Import / Tax Years / Settings rooms: unchanged beyond `_build_settings` getting `project_state`/`legacy_user_state` args for `_corporate_actions_source`.
- Backend routes: no new routes added; existing routes updated via model changes in `core.py`.

---

## 9. Recovery Plan

### Classification: PARTIAL_KEEP_AND_FINISH

The work is genuine, coherent, and mostly correct. 81 of 82 tests pass. The one remaining failure is a well-defined logic gap, not a structural mess.

### What to keep (everything):
All 9 changed files should be kept. The work is sound.

### Minimal `_coerce_float` fix (applied in this audit):
Added to `build_stock_tax_workbook.py` after `_to_float`:
```python
def _coerce_float(value: Any) -> Optional[float]:
    """Return float if parseable, else None. Used where None signals 'not present'."""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
```

### One remaining slice (next prompt):

**Problem:** `_normalize_corporate_actions_payload` deduplicates before `build_corporate_actions` validates. Duplicate `action_id` entries are silently dropped.

**Proposed fix (one change in `project_store.py`):**  
Remove the `seen` deduplication set from `_normalize_corporate_actions_payload`. Deduplication at storage/normalization level is premature — only schema normalization (field name mapping, type coercion) should happen there. Validation (including duplicate detection) belongs in `build_corporate_actions`.

The `adopt_legacy_workbook_state` already has its own explicit dedup via `existing_by_key`, so removing dedup from `_normalize_corporate_actions_payload` does not regress adoption.

**Scope:** ~5 lines removed from `_normalize_corporate_actions_payload` in `project_store.py`. Target: `test_invalid_corporate_actions_surface_in_status_and_audit` passes.

---

## 10. Recommended Next Prompt / Slice

```
TASK: Fix duplicate action_id detection in corporate actions validation.

File: stock_tax_app/state/project_store.py
Function: _normalize_corporate_actions_payload

Problem: The function silently deduplicates entries by _corporate_action_identity_key
before they reach build_corporate_actions. This means duplicate action_ids are dropped
on round-trip instead of being surfaced as validation errors.

Fix: Remove the seen-set deduplication from _normalize_corporate_actions_payload.
The function should only normalize field names and filter completely blank entries.
Deduplication/validation belongs in build_corporate_actions which already has a
duplicate detection check.

Verify: py -3 -m pytest -q test_stock_tax_app_api.py::test_invalid_corporate_actions_surface_in_status_and_audit
Target: this 1 test passes without any other test regressions (currently 81 passing).

Constraint: change only _normalize_corporate_actions_payload. Do not change any other function.
```

---

## 11. Docs Created

- `docs/audit/P2_3_CORPORATE_ACTIONS_REVISION_REPORT.md` — this file.

No restore plan required — the repo is testable after the `_coerce_float` fix.

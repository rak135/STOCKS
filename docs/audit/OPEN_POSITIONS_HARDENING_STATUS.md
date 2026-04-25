# OPEN_POSITIONS_HARDENING_STATUS

Date: 2026-04-25
Slice: P2.1 Open Positions / computed inventory hardening

## Scope
Implemented only P2.1.
Out-of-scope items were not implemented:
- corporate actions migration
- audit export implementation
- locked snapshot migration
- settings mutation
- FX manual edit UI/mutation
- dividends
- year-settings mutation changes (existing behavior preserved)
- workbook support removal
- fake broker/Yahoo position data

## Old Behavior
Before this slice:
- Open-position rows were computed from `build_open_position_rows()` in `build_stock_tax_workbook.py`.
- `calculated_qty` was derived from sum of `lot.quantity_remaining` for open lots per instrument.
- `yahoo_qty` was derived from `extract_position_rows()` by reading position-style CSV rows (no trade date, no transaction type, quantity present).
- `difference = calculated_qty - yahoo_qty` when Yahoo rows existed.
- Row status thresholds were hardcoded in workbook helper (`OK <= 1e-4`, `WARN <= 1e-2`, else `ERROR`; missing Yahoo -> `UNKNOWN`).
- Backend mostly passed through row status with generic reason text for warn/error and unknown.
- Unknown rows were not treated as OK (already explicit), but open-position discrepancies were not promoted into `/api/status` unresolved checks.
- `/api/audit` did not include open-position discrepancy reasons.

## New Reconciliation Semantics
Implemented and now explicit in backend:
- `calculated_qty`: sum of remaining open lots after known lot matching / current simulation output.
- `reported_qty`: broker/Yahoo current position if present (kept `yahoo_qty` for backward compatibility; both carry same value).
- `difference`: `calculated_qty - reported_qty` when both are known.
- `status`:
  - `ok`: `abs(difference) <= tolerance`
  - `warn`: `tolerance < abs(difference) <= material_threshold`
  - `error`: `abs(difference) > material_threshold`
  - `unknown`: reported position unavailable
- `truth_status` mapping:
  - `ok -> ready`
  - `warn -> needs_review`
  - `error -> blocked`
  - `unknown -> unknown`
- `status_reason_code` + `status_reason` are explicit and populated for all statuses.

## Tolerance Rule
- Uses explicit backend tolerance constant exposed via settings:
  - `position_reconciliation_tolerance = 1e-4`
- Material threshold for warn/error split remains conservative (`1e-2`).
- Workbook helper now accepts explicit tolerances from engine (`ok_tolerance`, `warn_tolerance`) instead of hardcoded-only semantics.
- `/api/settings` already exposes `position_reconciliation_tolerance` and remains display-only.

## Status/Check Integration
Implemented integration into app truth posture:
- `/api/status` now includes open-position discrepancy checks in `unresolved_checks`:
  - warn-level checks for `warn` and `unknown` rows
  - error-level checks for `error` rows
- `global_status`, `truth_status`, `next_action`, and `status_reasons` now incorporate these checks.
- `/api/audit` now includes open-position readiness reasons when reconciliation is not fully ready:
  - collection-level reason (for non-ready open-position truth)
  - row-level reasons for each non-OK open position
- Audit `truth_status` is forced to `blocked` if open-position collection truth is `blocked` (or if calculation itself is blocked).

## API Fields
`GET /api/open-positions` now returns hardening fields needed by frontend reconciliation workflows:
- `instrument_id`
- `ticker`
- `calculated_qty`
- `reported_qty` (new)
- `yahoo_qty` (preserved compatibility alias)
- `difference`
- `status`
- `truth_status`
- `status_reason_code`
- `status_reason`
- `instrument_map_source`
- `inventory_source`
- `lots`
- `tolerance` (new)

Collection truth now resolves by row statuses:
- `blocked` if any row blocked
- `partial` if any row unknown (and none blocked)
- `needs_review` if any row needs review (and none blocked/unknown)
- `ready` otherwise

## Frontend Changes
- No visual redesign.
- Frontend type contract updated to include additive fields:
  - `reported_qty: number | null`
  - `tolerance: number | null`
- Existing Open Positions UI remains compatible (truth banner, UNKNOWN/WARN reasons, provenance chips, expandable rows).

## Tests Added/Strengthened
Added in `test_stock_tax_app_api.py`:
- `test_open_positions_exact_match_is_ok_and_ready`
- `test_open_positions_warn_difference_creates_needs_review_and_status_check`
- `test_open_positions_material_difference_blocks_collection_and_surfaces_audit_reason`
- `test_open_positions_missing_reported_position_is_unknown_not_ok`
- `test_open_positions_tolerance_behavior_ok_vs_warn`

Existing unknown-row truth test retained and still passing.

## Commands Run
Executed in `C:\DATA\PROJECTS\STOCKS`:
- `py -3 -m pytest -q test_stock_tax_app_api.py` -> 51 passed
- `py -3 -m pytest -q test_project_state_store.py` -> 17 passed
- `py -3 -m pytest -q` -> 70 passed

Frontend build validation:
- `cd ui/frontend && npm run build` -> success

Launcher smoke:
- `./run_app.ps1 -NoBrowser -AutoStopAfterSeconds 20` -> success (frontend served on auto-selected port, backend reused)

## Remaining Gaps
- Reported position source remains CSV position-row driven; no dedicated broker snapshot API ingestion yet.
- Open-position checks currently link via existing check-href policy (frontend-ready fallback behavior still in place).
- No corporate-action migration in this slice (as required by scope).
- No audit export changes in this slice (as required by scope).

## Recommended Next Slice
P2.2:
- Introduce explicit broker snapshot ingestion/provenance for reported positions (still local-first),
- then tighten discrepancy messaging with source timestamps and account-level traceability,
- while keeping current conservative blocked/needs-review posture intact.

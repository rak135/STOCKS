# REPORTED_POSITION_PROVENANCE_STATUS

Date: 2026-04-25
Slice: P2.2 reported-position provenance and reconciliation trace depth

## Scope
Implemented only P2.2.
Out-of-scope items were not implemented:
- corporate actions migration
- audit export implementation
- locked snapshot migration
- settings mutation
- FX manual edit UX/mutation
- dividends
- year settings mutation changes
- tax formula changes
- workbook support removal
- fake broker data or broker API integration

## Old reported-position behavior
Before this slice:
- Reported quantity came from `extract_position_rows()` in `build_stock_tax_workbook.py`.
- Position rows were detected as CSV rows with empty `Transaction Type` and empty `Trade Date`, but numeric `Quantity`.
- Quantity was aggregated per instrument (`sum`), mapped via instrument map.
- `reported_qty`/`yahoo_qty` were available, but source provenance was not explicit in open-position API rows.
- Multiple position rows per instrument were silently aggregated without row-level source trace in `/api/open-positions`.

## New provenance fields
`/api/open-positions` rows now include additive reported-position provenance:
- `reported_position_source_file`
- `reported_position_source_row`
- `reported_position_broker` (from filename-derived broker when inferable)
- `reported_position_account` (from filename-derived account when inferable, else null)
- `reported_position_snapshot_date` (from CSV `Date` when parseable, else null)
- `reported_position_source_type` (`csv_position_row`)
- `reported_position_source_status` (`ready` | `partial` | `unknown`)
- `reported_position_source_reason`
- `reported_position_source_count`
- `reported_position_sources` (list of contributing source rows with file/row/broker/account/snapshot_date/type)

Existing fields are preserved:
- `reported_qty`, `yahoo_qty`, `calculated_qty`, `difference`, `status`, `truth_status`, `status_reason_code`, `status_reason`, `instrument_map_source`, `inventory_source`, `lots`, `tolerance`

## Source status policy
Conservative policy implemented:
- `unknown`:
  - no reported position source rows for instrument
- `partial`:
  - snapshot date unavailable on one or more contributing rows, or
  - multiple contributing source rows were aggregated
- `ready`:
  - reported row(s) exist and provenance has no partial flags

For reconciliation posture:
- Quantity `status=ok` does not automatically imply row readiness.
- If quantity matches but `reported_position_source_status` is `partial`/`unknown`, row `truth_status` is downgraded to `needs_review` with explicit source-related reason.

## Multiple-source handling
Current behavior still aggregates per-instrument reported quantity (sum), but now this is explicit:
- `reported_position_source_count` shows contributing row count.
- `reported_position_sources` carries contributing source references.
- `reported_position_source_status=partial` with reason text documents aggregation/source ambiguity.

## Status/check integration
`/api/status` integration now includes provenance-sensitive open-position checks:
- Quantity mismatch checks still emit as before.
- Additional warn-level unresolved checks are emitted when quantity is OK but source provenance is partial/unknown.
- Check messages explicitly include reported-position provenance context.

## Audit integration
`/api/audit` status reasons now include provenance-driven open-position readiness effects:
- collection-level non-ready open-position reason remains
- row-level reasons now also include `open_position_provenance_<instrument_id>` when quantity is OK but source provenance is weak

No audit export work was added.

## Frontend display changes
Open Positions screen (`ui/frontend/src/screens/open-positions-screen.tsx`) now shows provenance clearly without redesign:
- visible row-level source-status chip (`source ready`/`source partial`/`source unknown`)
- visible source-count chip when multiple source rows exist
- visible reason strip for partial/unknown provenance
- expanded section includes:
  - primary source file:row
  - broker/account (if present)
  - snapshot date (or explicit unknown)
  - source type
  - source count
  - contributing row list when multiple

Type contract updates are additive in `ui/frontend/src/types/api.ts`.

## Tests added/strengthened
In `test_stock_tax_app_api.py`:
- `test_open_positions_provenance_missing_snapshot_date_is_honest`
- `test_open_positions_multiple_reported_rows_expose_ambiguity_and_source_count`
- `test_status_and_audit_include_provenance_checks_for_quantity_match`

Existing tests were updated to include realistic strong provenance where needed (snapshot date provided), including exact/warn/error/tolerance cases.

Coverage now includes:
- A source file/row provenance present
- B snapshot date not fabricated and represented as null + reason
- C multiple rows expose source_count and ambiguity reason
- D exact qty match with weak provenance surfaces needs-review policy
- E missing reported position remains unknown
- F `/api/status` includes provenance-related unresolved check
- G `/api/audit` includes provenance-related status reason
- H frontend build passes after type/UI updates

## Commands run
Executed in `C:\DATA\PROJECTS\STOCKS`:
- `py -3 -m pytest -q test_stock_tax_app_api.py` -> 54 passed
- `py -3 -m pytest -q test_project_state_store.py` -> 17 passed
- `py -3 -m pytest -q` -> 73 passed

Frontend build validation:
- `cd ui/frontend && npm run build` -> success

Launcher smoke:
- `./run_app.ps1 -NoBrowser -AutoStopAfterSeconds 20` -> success

## Remaining gaps
- Provenance still depends on CSV export metadata quality (especially snapshot date availability).
- No dedicated broker snapshot ingestion path yet; source type remains `csv_position_row`.
- Broker/account inference remains filename-based and may be sparse depending on naming.

## Recommended next slice
P2.3 (still without broker API integration):
- Introduce stricter operator controls around accepted reported-position evidence (for example per-source acknowledgement state in UI/project state),
- then layer this into reconciliation readiness so accepted provenance is explicit before corporate-actions migration.

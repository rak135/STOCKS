# API Contract

The frontend talks only to the FastAPI backend. It must never parse
`stock_tax_system.xlsx` directly, and it must never inspect the raw
Excel workbook to derive state.

## Endpoints

- Collection endpoints now return `{ items, truth }` so the frontend can
  distinguish `no_data` from `blocked`, `unknown`, and
  `not_implemented`.
- `GET /api/status`
  Returns `AppStatus` with project paths, global status, recommended
  next action, unresolved checks, truth reasons, and remaining
  workbook-backed domains.
- `GET /api/import`
  Returns `ImportSummary` with the detected CSV files, row counts, date
  ranges, warnings, aggregate import totals, and import truth metadata.
- `GET /api/years`
  Returns `TaxYearList` with `items: TaxYear[]` plus collection truth.
- `PATCH /api/years/{year}`
  Reserved for year editing. The backend already enforces filed and
  locked year rules here.
- `GET /api/sales`
  Returns `SellList` with `items: SellSummary[]` plus collection truth.
- `GET /api/sales/{sell_id}`
  Returns full `Sell` evidence for one sale.
- `PATCH /api/sales/{sell_id}/review`
  Updates UI review metadata for one sale.
- `GET /api/open-positions`
  Returns `OpenPositionList` with `items: OpenPosition[]` plus
  collection truth and explicit unknown reasons.
- `GET /api/fx`
  Returns `FxYearList` with `items: FxYear[]` plus collection truth and
  effective rate provenance.
- `GET /api/audit`
  Returns `AuditSummary` with tax year rows, trace counts, locked
  snapshots, summary-only disclosure, and workbook-backed-domain truth.
- `GET /api/settings`
  Returns `AppSettings` used by the UI for display only, including
  per-field editability and domain ownership metadata.
- `POST /api/recalculate`
  Triggers a fresh engine run and returns the full `EngineResult`,
  including the same truth-aware collection envelopes.

## Key Response Shapes

- `AppStatus`
  Includes `global_status`, `truth_status`, `next_action`,
  `unresolved_checks`, `status_reasons`, and
  `workbook_backed_domains`.
- `ImportSummary`
  Includes `files[]` with source metadata for each CSV import plus
  import `truth`.
- `TaxYear`
  Carries policy and tax numbers for one year plus provenance fields for
  migrated settings and reconciliation.
- `TaxYearList`, `SellList`, `OpenPositionList`, `FxYearList`
  Carry `items[]` and a collection-level `truth` block.
- `SellSummary` and `Sell`
  The list view uses compact sale data; the detail view contains matched
  lots, source references, and truth/provenance metadata.
- `AuditSummary`
  Mirrors tax years plus trace counters used for audit confidence, but
  it remains explicitly summary-only in the current slice.

## UI-Only State

Review annotations are stored in `.ui_state.json`. This is UI metadata,
not source-of-truth tax logic. The backend merges that file into API
responses so the frontend can remain workbook-free.

## Backend Authority

- The frontend must not parse Excel for data, reconciliation state, or
  method policy.
- The backend remains the single source of truth for tax-year policy,
  sales evidence, import summaries, and audit output.
- The backend must disclose when effective data still depends on
  workbook-backed fallback or generated defaults.
- 2024 is enforced server-side as `filed = true`, `locked = true`,
  `method = LIFO`, and it must not be presented as an optimization
  target.
- For filed and locked years like 2024, `method_comparison` must remain
  hidden or `null`.

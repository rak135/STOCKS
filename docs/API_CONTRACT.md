# API Contract

The frontend talks only to the FastAPI backend. It must never parse
`stock_tax_system.xlsx` directly, and it must never inspect the raw
Excel workbook to derive state.

## Endpoints

- `GET /api/status`
  Returns `AppStatus` with project paths, global status, recommended
  next action, and unresolved checks.
- `GET /api/import`
  Returns `ImportSummary` with the detected CSV files, row counts, date
  ranges, warnings, and aggregate import totals.
- `GET /api/years`
  Returns a list of `TaxYear` items with policy, tax figures, filed and
  locked state, reconciliation state, and optional method comparison.
- `PATCH /api/years/{year}`
  Reserved for year editing. The backend already enforces filed and
  locked year rules here.
- `GET /api/sales`
  Returns `SellSummary[]` for the review list.
- `GET /api/sales/{sell_id}`
  Returns full `Sell` evidence for one sale.
- `PATCH /api/sales/{sell_id}/review`
  Updates UI review metadata for one sale.
- `GET /api/open-positions`
  Returns `OpenPosition[]` with open lots and reconciliation status.
- `GET /api/fx`
  Returns `FxYear[]` with FX sourcing per year.
- `GET /api/audit`
  Returns `AuditSummary` with tax year rows, trace counts, and locked
  snapshots.
- `GET /api/settings`
  Returns `AppSettings` used by the UI for display only.
- `POST /api/recalculate`
  Triggers a fresh engine run and returns the full `EngineResult`.

## Key Response Shapes

- `AppStatus`
  Includes `global_status`, `next_action`, and `unresolved_checks`.
- `ImportSummary`
  Includes `files[]` with source metadata for each CSV import.
- `TaxYear`
  Carries policy and tax numbers for one year. `method_comparison` is
  informational and may be absent.
- `SellSummary` and `Sell`
  The list view uses compact sale data; the detail view contains matched
  lots and source references.
- `AuditSummary`
  Mirrors tax years plus trace counters used for audit confidence.

## UI-Only State

Review annotations are stored in `.ui_state.json`. This is UI metadata,
not source-of-truth tax logic. The backend merges that file into API
responses so the frontend can remain workbook-free.

## Backend Authority

- The frontend must not parse Excel for data, reconciliation state, or
  method policy.
- The backend remains the single source of truth for tax-year policy,
  sales evidence, import summaries, and audit output.
- 2024 is enforced server-side as `filed = true`, `locked = true`,
  `method = LIFO`, and it must not be presented as an optimization
  target.
- For filed and locked years like 2024, `method_comparison` must remain
  hidden or `null`.

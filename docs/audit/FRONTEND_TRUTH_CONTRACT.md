# Frontend Truth Contract v1

## Scope

This slice defines the minimum truth contract the frontend can rely on
today without pretending the backend is farther along than it is.

The contract is intentionally explicit about:

- whether data is ready, partial, blocked, unknown, or not implemented
- where effective data came from
- why empty collections are empty
- which screens are real and which are still placeholders

## Frontend Route Map

| Route | Screen | Current frontend status | What the screen needs to be truly useful | Current endpoint(s) | Current backend truth | Truth metadata the frontend needs |
|---|---|---|---|---|---|---|
| `/` | Overview | `REAL_CONNECTED` | Global status, blocked reasons, next action, unresolved checks, tax-year summary cards, import posture | `GET /api/status`, `GET /api/import`, `GET /api/years` | `REAL_PARTIAL` | `AppStatus.truth_status`, `status_reasons`, `workbook_backed_domains`, `TaxYearList.truth` |
| `/import` | Import | `REAL_CONNECTED` | File list, warnings, ignored-row counts, explicit distinction between usable import and blocked downstream calculation | `GET /api/import` | `REAL_TRUSTED` for import facts, `REAL_PARTIAL` for downstream readiness | `ImportSummary.truth` |
| `/tax-years` | Tax Years | `PARTIAL_CONNECTED` | Year cards, effective method/settings provenance, reconciliation provenance, explicit blocked-empty handling, future editability truth | `GET /api/years`, `PATCH /api/years/{year}` | `REAL_PARTIAL` | `TaxYearList.truth`, per-year `settings_source`, `method_source`, `reconciliation_source` |
| `/sales-review` | Sales Review | `PLACEHOLDER` | Sell list, sell detail, matched lots, review mutation, blocked-empty handling | `GET /api/sales`, `GET /api/sales/{sell_id}`, `PATCH /api/sales/{sell_id}/review` | `REAL_PARTIAL` | `SellList.truth`, per-sale `truth_status`, `instrument_map_source`, detail `truth` |
| `/open-positions` | Open Positions | `PLACEHOLDER` | Position list, lot breakdown, explicit unknown reasons, blocked-empty handling | `GET /api/open-positions` | `REAL_PARTIAL` | `OpenPositionList.truth`, per-row `truth_status`, `status_reason_code`, `status_reason`, `instrument_map_source` |
| `/fx` | FX Rates | `PLACEHOLDER` | Year-level FX truth, missing-date reasons, rate provenance, explicit disclosure of fallback/cache/default source | `GET /api/fx` | `REAL_PARTIAL` | `FxYearList.truth`, per-year `rate_source`, `status_reason` |
| `/audit` | Audit Pack | `PLACEHOLDER` | Audit summary, readiness truth, workbook-backed-domain disclosure, summary-only disclosure, export readiness vs summary-only separation | `GET /api/audit` | `REAL_PARTIAL` | `AuditSummary.truth_status`, `summary_only`, `status_reasons`, `workbook_backed_domains` |
| `/settings` | Settings | `PLACEHOLDER` | Displayable settings, per-field editability, domain ownership, explicit non-implemented editing state | `GET /api/settings` | `REAL_PARTIAL` | `AppSettings.truth_status`, `status_reasons`, `field_meta`, `domain_sources` |

## Truth Status Vocabulary

| Value | Meaning |
|---|---|
| `ready` | Safe to display as ordinary data. |
| `needs_review` | Data exists, but a human should treat it as unresolved or review-worthy. |
| `blocked` | Data is unavailable or non-final because required checks failed. |
| `partial` | Data is real, but important domains or explanations are incomplete. |
| `unknown` | The backend knows it cannot resolve the item and says so explicitly. |
| `not_implemented` | The route or field is intentionally not implemented yet. |

## Source / Provenance Vocabulary

| Value | Meaning |
|---|---|
| `project_state` | Effective value came from canonical backend ProjectState. |
| `ui_state` | Effective value came from canonical UIState. |
| `workbook_fallback` | Effective value still depends on workbook-backed state. |
| `calculated` | Value was computed from normalized inputs by the engine. |
| `generated_default` | Backend generated a default because no explicit state existed. |
| `cnb_cache` | FX daily data came from the CNB/cache fetch path. |
| `static_config` | Value came from hardcoded/static backend policy or config. |
| `unavailable` | Backend cannot currently provide a truthful value. |

## Frontend Display Rules

- The frontend may display `ready` data normally.
- The frontend must visually mark `partial`, `unknown`, `needs_review`, and `blocked` data.
- The frontend must not treat `blocked` collections as ordinary empty lists.
- The frontend must not route the operator into placeholder screens as if they solve the problem.
- The frontend must show the backend reason when `status_reasons`, `status_reason`, or `truth.reasons` are present.
- The frontend must not hide `workbook_fallback` or `generated_default` provenance when the backend exposes it.
- Unknown open-position rows must remain visibly unresolved even if other rows are fine.
- Audit data must remain labeled summary-only until export and workbook-backed domains are no longer blocking trust.

## Backend Response Rules

- Collection endpoints must return `items` plus `truth`.
- Collection `truth.empty_meaning` must distinguish:
  - `no_data`
  - `blocked`
  - `unknown`
  - `not_implemented`
- `GET /api/status` must expose:
  - `global_status`
  - `truth_status`
  - `status_reasons`
  - `workbook_backed_domains`
- Per-item provenance must be exposed where the current product relies on migrated domains:
  - `TaxYear.settings_source`
  - `TaxYear.method_source`
  - `TaxYear.reconciliation_source`
  - `Sell.instrument_map_source`
  - `Sell.review_state_source`
  - `FxYear.rate_source`
  - `OpenPosition.instrument_map_source`
- Not-implemented behavior must be explicit:
  - `PATCH /api/years/{year}` still returns `501`
  - `GET /api/settings` is truthful display-only metadata
  - `GET /api/audit` is summary-only, not final readiness
- Workbook-backed fallback must be disclosed where relevant.
- Generated defaults must be disclosed where relevant.

## Current Gaps

- The Sales Review, Open Positions, FX, Audit, and Settings frontend rooms are still placeholders.
- `GET /api/open-positions` now exposes explicit unknown reasons, but it does not yet provide per-row frozen-snapshot provenance.
- `GET /api/fx` exposes year-level provenance, not per-date provenance.
- `GET /api/settings` is still display-only; no settings mutation route is implemented.
- `GET /api/audit` is still summary-only and not an export workflow.
- `PATCH /api/years/{year}` still enforces policy truthfully but does not implement real mutation yet.

## Contract Summary

The frontend no longer has to guess why a collection is empty or whether
important values are canonical, workbook-backed, generated defaults, or
blocked by missing checks. The backend now supplies that truth
explicitly, and the remaining missing product slices stay visibly
missing instead of being implied by silence.

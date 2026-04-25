# Audit Pack frontend wiring

## Endpoint used

- `GET /api/audit` → `AuditSummary` (`{ year_rows, trace_counts, locked_snapshots, truth_status, summary_only, status_reasons, workbook_backed_domains }`).

No mutation endpoint is consumed. No export endpoint is consumed.

## What was implemented

Replaced the `/audit` `ComingNextScreen` placeholder with a real cockpit room backed by `GET /api/audit`. The screen renders a summary-only audit posture, a yearly summary table, trace counts, locked-year snapshot refs, and a disabled export grid.

Layout (top → bottom):

1. `SectionHeader` — title `Audit Pack`, subtitle adapted to `summary_only`, primary chip showing `Summary-only · not final` when applicable, otherwise the truth-status chip.
2. **Summary truth banner** — `truth_status` chip + dot, summary-only chip, plain-language posture sentence, structured reasons list.
3. **Readiness card** — large icon block with a tone-coded headline (`Audit summary is ready / partial / blocked / needs review / unknown / not implemented`) and a body sentence derived from the truth status. Honest fallback line when no structured reasons exist.
4. **Workbook-backed domains card** — only rendered when the backend reports any. Warn-toned card with one chip per domain.
5. **Trace counts** — only rendered when `trace_counts` is non-empty. One card per `{key, value}` pair, with humanised labels for the common keys.
6. **Yearly summary table** — one row per `year_rows[i]` with year, method (filed-method aside if different), FX, gross proceeds, taxable base, tax, reconciliation chip, locked/filed/draft chip.
7. **Locked snapshots** — one row per locked-year reference.
8. **Export section** — four disabled cards: Excel workbook export, PDF audit report, CSV lot ledger, ZIP evidence pack — each labeled "Not wired" with tooltip.

## Summary-only handling

`summary_only` is treated as the dominant signal:

- The header subtitle becomes "Summary-only view of what a tax-office check would ask for. **This is not a final audit pack.**" when true.
- The header right-side chip is a warn `Summary-only · not final` chip when true.
- The truth banner repeats the `Summary-only · not final export readiness` chip alongside the truth-status chip.
- The truth-banner body sentence explicitly tells the operator the view is "a snapshot for human review, not the artefact a tax office would see."

The screen never refers to itself as a "final audit pack" while `summary_only` is true.

## Audit readiness display

The Readiness card converts `truth_status` into a tone-coded posture:

| `truth_status` | Headline | Tone |
| --- | --- | --- |
| `ready` | Audit summary is ready | ok |
| `partial` | Audit summary is partial | warn |
| `needs_review` | Audit summary needs review | warn |
| `blocked` | Audit summary is blocked | err |
| `unknown` | Audit readiness is unknown | filed |
| `not_implemented` | Audit readiness is not implemented | filed |

If `status_reasons` is non-empty, each reason is rendered in the truth banner as `code: message`. If it is empty *and* the status is non-ready, the readiness card prints an italic "Backend has not attached structured status reasons for this view." line so the operator knows nothing was hidden.

## Workbook-backed domains display

When `workbook_backed_domains` is non-empty:

- Rendered as a top-level card with a warn icon and warn-toned body — it is **not** buried in small text.
- One chip per domain, all warn-toned, so they remain visible even at a glance.
- Card body explicitly explains "These domains have not yet been migrated to canonical backend state. Their values still flow through the workbook fallback and must remain visible until they are."

When the list is empty, the card is omitted (no false reassurance).

## Disabled / not-wired actions

| Action | Visibility | Reason |
| --- | --- | --- |
| `Excel workbook export` | Disabled card with `Not wired` button | No backend audit-export endpoint. |
| `PDF audit report` | Disabled card with `Not wired` button | No backend PDF generator. |
| `CSV lot ledger` | Disabled card with `Not wired` button | No backend CSV ledger export. |
| `ZIP evidence pack` | Disabled card with `Not wired` button | No backend ZIP export. |

`POST /api/recalculate` (which writes a workbook) is intentionally not surfaced as an "Audit Pack export" because that conflates two workflows and the brief explicitly forbids it.

## Files changed

- `ui/frontend/src/types/api.ts` — added `AuditSummary`.
- `ui/frontend/src/lib/api.ts` — added `useAuditQuery` against `GET /api/audit`.
- `ui/frontend/src/screens/audit-screen.tsx` — **new.** Full Audit Pack room.
- `ui/frontend/src/App.tsx` — `/audit` now renders `<AuditScreen />`. No other routes touched.

No backend files were modified.

## Commands run

```
cd ui/frontend
npm run build
```

Result: ✅ pass.

```
> stock-tax-frontend@0.0.0 build
> tsc -b && vite build

vite v8.0.10 building client environment for production...
✓ 1736 modules transformed.
dist/index.html                   0.46 kB │ gzip:   0.30 kB
dist/assets/index-BBmWjqUB.css   24.94 kB │ gzip:   5.38 kB
dist/assets/index-B0MGzghr.js   394.42 kB │ gzip: 116.99 kB
✓ built in 346ms
```

Backend was not touched, so backend tests were not re-run.

## Remaining gaps

- No backend audit-export endpoint exists, so all four export cards remain disabled rather than functional.
- The Locked snapshots list shows year numbers only; the backend does not yet expose a per-snapshot timestamp, hash, or downloadable artefact.
- Trace-count keys are humanised by a small static map plus a generic title-case fallback. If the backend introduces new keys, they will render in title case rather than a curated label.
- The yearly summary table does not include per-row provenance chips (`settings_source` / `method_source` / `reconciliation_source`); those remain on the dedicated Tax Years room. The Audit table is intentionally a high-level posture view, not a duplicate of `/tax-years`.
- Workbook-backed domain names are echoed verbatim from the backend; the frontend does not maintain its own gloss for them.

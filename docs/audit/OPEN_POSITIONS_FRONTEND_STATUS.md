# Open Positions frontend wiring

## Endpoint used

- `GET /api/open-positions` → `OpenPositionList` (`{ items: OpenPosition[], truth: CollectionTruth }`).

No mutation endpoint is consumed.

## What was implemented

Replaced the `/open-positions` `ComingNextScreen` placeholder with a real cockpit room backed by `GET /api/open-positions`. The screen renders the prototype's expandable per-ticker rows and respects the frontend truth contract.

Layout:

- `SectionHeader` ("Open Positions" / "Does the residual inventory match what you actually hold?") with a disabled `Reconcile not wired` action.
- Collection-truth banner at the top.
- Filter bar: ticker/instrument search + status pill filter (`All / OK / WARN / ERROR / UNKNOWN`) + in-view-of-total counter.
- One card per position. Each card has:
  - Header row: ticker, instrument id (mono), `Calculated`, `Yahoo`, `Difference` (color-coded), `status` chip, `truth_status` chip (when not `ready`), expand chevron.
  - Always-visible reason strip when the row is `unknown`, `warn`, `error`, `needs_review`, `partial`, or `blocked` — surfaces `status_reason_code` (mono pill) + `status_reason` (or a tone-appropriate fallback line if the backend left them null).
  - Always-visible provenance chips for `instrument_map_source` and `inventory_source`, color-coded so `workbook_fallback` / `generated_default` show as warn and `unavailable` shows as err.
  - Expanded body: lot table when `lots` is non-empty, otherwise the honest line "Lot detail not available from backend."

## Truth and provenance shown

**Collection level (banner):**
- `truth.status` as both a tone-coded chip and a `StatusDot`.
- `truth.empty_meaning` as a chip — so `blocked` / `unknown` / `not_implemented` empty lists never look like ordinary "no data".
- `truth.summary` rendered inline.
- `truth.sources` rendered as one tone-coded chip per source.
- `truth.reasons[].code` + `.message` as a bullet list.
- `truth.item_count` (Total) and the locally-filtered count (In view).

**Per-position:**
- `status` chip (`OK / WARN / ERROR / UNKNOWN`) with semantic tone.
- `truth_status` chip + dot (rendered when not `ready` to keep `ready` rows uncluttered, but always visible when the truth is non-trivial).
- `instrument_map_source` and `inventory_source` chips, always visible, color-coded so any non-canonical source jumps out.
- `status_reason_code` and `status_reason` rendered always-visibly outside the expandable section whenever the row is non-OK or non-ready.

## Unknown / warn handling

Unknown rows are visually obvious before any expansion:

- The card body is tinted `bg-filed-bg/30` for `unknown` rows.
- A status chip in the header reads `UNKNOWN` (filed tone, dot included).
- The reason strip is always visible — never hidden behind the chevron.
- If the backend has not attached a `status_reason`, a tone-appropriate fallback sentence is displayed so the operator never sees a silently-unknown row. The fallback explicitly tells the operator to "verify the residual with your broker directly".

Warn and error rows follow the same pattern with their own tones (`border-warn-bg` / `border-err-bg`).

## Expandable / detail behavior

- Clicking a card header toggles the lot table.
- When `lots.length > 0`, the expanded body shows lot id, buy date, broker, qty, cost (CZK), and unrealised P/L (color-coded to ok/err when present).
- When `lots.length === 0`, the expanded body shows the honest sentence "Lot detail not available from backend." No lot rows are fabricated from the prototype mock data.

## Disabled / not-wired actions

| Action | Visibility | Reason |
| --- | --- | --- |
| Section-level "Reconcile not wired" | Disabled, with tooltip | No backend mutation endpoint for Yahoo/broker reconciliation. |

The prototype's per-row "Verify" / "Re-fetch" affordances are intentionally omitted because they have no backend counterpart.

## Files changed

- `ui/frontend/src/types/api.ts` — added `OpenPositionStatus`, `OpenLot`, `OpenPosition`, `OpenPositionList`.
- `ui/frontend/src/lib/api.ts` — added `useOpenPositionsQuery` against `GET /api/open-positions`.
- `ui/frontend/src/screens/open-positions-screen.tsx` — **new.** Full Open Positions room.
- `ui/frontend/src/App.tsx` — replaced the `/open-positions` `ComingNextScreen` placeholder with `<OpenPositionsScreen />`. No other routes touched.

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
✓ 1735 modules transformed.
dist/index.html                   0.46 kB │ gzip:   0.30 kB
dist/assets/index-DsqWMHKA.css   24.42 kB │ gzip:   5.29 kB
dist/assets/index-Dq0SU5Uv.js   382.37 kB │ gzip: 114.95 kB
✓ built in 342ms
```

Backend was not touched, so backend tests were not re-run.

## Remaining gaps

- No backend reconciliation endpoint exists, so the section-level Reconcile action is visibly disabled.
- The backend does not yet provide per-lot frozen-snapshot provenance; only per-row `instrument_map_source` and `inventory_source` are exposed and shown.
- The lot table does not show per-lot Yahoo or broker reconciliation because the backend response does not include those fields.
- No bulk export / CSV ledger affordance is offered here; the operator's audit pack is the right room for that.

# FX Rates frontend wiring

## What was implemented

Replaced the `/fx` placeholder room with a real cockpit screen backed by `GET /api/fx`. The screen renders the prototype's FX year cards and respects the frontend truth contract.

## Endpoint used

- `GET /api/fx` → `FxYearList` (`{ items: FxYear[], truth: CollectionTruth }`).

No mutation endpoint is consumed. The prototype's *Fetch all missing* / *Fetch / verify* / *Manual edit* affordances are rendered as **disabled** buttons labeled `Fetch not wired` / `Manual edit not wired`.

## Truth and provenance shown

**Collection level (banner at top of room):**
- `truth.status` rendered as both a tone-coded chip and a status dot.
- `truth.empty_meaning` rendered as a chip (so `blocked` / `unknown` / `not_implemented` empty lists never look like ordinary "no data").
- `truth.summary` rendered inline.
- `truth.sources` rendered as one chip per source, color-coded so `workbook_fallback` and `generated_default` show as warn and `unavailable` as err.
- `truth.reasons[].code` + `.message` rendered as a bullet list.
- `truth.item_count` and the locally-filtered count are both shown.

**Per-year card header chips:**
- `method` (CNB daily / GFŘ yearly).
- `truth_status` chip + dot (using the same tone vocabulary as the rest of the cockpit).
- `rate_source` chip — color-coded so `workbook_fallback`, `generated_default`, and `unavailable` are visually distinct.
- `locked` (filed-tone chip).
- `manual_override` (warn-tone chip).
- `verified_at` (ok-tone chip showing the verification date).
- Missing-rate count (warn-tone chip when `missing_dates.length > 0`).

**Per-year card body:**
- For `FX_UNIFIED_GFR`: unified rate, source label, verified-at timestamp, manual-override flag.
- For `FX_DAILY_CNB`: daily cached / expected counts, missing count, source label, verified-at timestamp.
- `source_url` rendered as an external link below the body when the backend provides one.
- `status_reason` rendered as a labeled "Backend reason" strip when the backend provides one.
- A fallback advisory strip is rendered when `rate_source` is `workbook_fallback`, `generated_default`, or `unavailable` and the backend did not attach a status reason — so the operator never sees a non-canonical source silently.

## Missing FX handling

When `missing_dates` is non-empty:

- A warn chip in the card header shows the count.
- A dedicated warn-toned strip in the card body lists every missing date as a tabular code chip (capped at 30, with a `+N more` overflow indicator).
- The strip is always visible — there is no collapsed-only UI for missing FX.

## Disabled / not-wired actions

| Action | Visibility | Reason |
| --- | --- | --- |
| Section-level "Fetch not wired" | Disabled, with tooltip | No backend mutation endpoint for FX fetch. |
| Per-year "Fetch not wired" | Disabled, with tooltip | Same. |
| Per-year "Manual edit not wired" | Disabled, with tooltip | No backend mutation endpoint for manual FX edit. |

The prototype's "Missing only" toggle is not rendered — it is purely a frontend filter and would not change the operator's understanding of the underlying truth, and the brief explicitly excludes adding features beyond the slice.

## Files changed

- `ui/frontend/src/types/api.ts` — added `FxMethod`, `FxYear`, `FxYearList`.
- `ui/frontend/src/lib/api.ts` — added `useFxQuery` against `GET /api/fx`.
- `ui/frontend/src/screens/fx-screen.tsx` — **new.** Full FX room.
- `ui/frontend/src/App.tsx` — replaced the `/fx` `ComingNextScreen` placeholder route with `<FxScreen />`. No other routes touched.

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
✓ 1734 modules transformed.
dist/index.html                   0.46 kB │ gzip:   0.30 kB
dist/assets/index-DOFnZD3G.css   24.01 kB │ gzip:   5.24 kB
dist/assets/index-DFGHue5G.js   372.91 kB │ gzip: 113.70 kB
✓ built in 351ms
```

Backend was not touched, so backend tests were not re-run.

## Remaining gaps

- No `POST /api/fx/...` mutation endpoint exists, so fetch / verify / manual-edit affordances are visibly disabled rather than functional.
- `GET /api/fx` exposes year-level provenance only. Per-date `rate_source` for daily CNB rates is not available, so the missing-dates strip lists dates without per-date provenance.
- The prototype's "Missing only" toggle and its interaction with the year list are intentionally not implemented in this slice.
- The UI does not surface broker- or FX-method-specific reconciliation against tax years; that cross-cut belongs on the Tax Years / Audit screens, not here.

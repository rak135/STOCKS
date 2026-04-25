# Frontend prototype realignment

## What was visually wrong before

The React frontend had drifted into a "luxury SaaS landing page" direction:

- Decorative serif heading font (`font-display`, Iowan Old Style / Palatino) on every section title.
- Oversized hero "Backend truth, operator review" banner under every screen.
- Heavy gradient backgrounds (`radial-gradient(...)`, glassy overlays, blur), large `rounded-[2rem]` cards, big drop shadows.
- Sidebar was a 292px floating glass card with prose subtitles, not a fixed cockpit nav.
- TopBar wasn't a topbar — it was a 3-stat hero panel rendered inside `main`.
- Density was very low: marketing-style cards with lots of whitespace, instead of compact operator rows.
- Sales Review used full-width stacked panels with a queue narrowed to one column rather than a true left-queue / right-detail cockpit room.
- Status / truth chips used arbitrary emerald/rose/amber Tailwind palettes rather than the prototype's warm semantic tones.

## Prototype principles applied

Extracted from `ui/prototype.html` and applied across the React app:

1. **Warm neutral palette** — `bg #FAF9F7`, `surface #FFFFFF`, `raised #FFFDFA`, `border #EDE8E0`, `ink #1F1E1B`, `ink2 #6E6A62`, `ink3 #A09B91`, `accent #C96442`, plus semantic `ok / warn / err / filed` paired with their `*-bg` companions.
2. **Inter / system sans only.** Removed the serif `font-display` token and all `font-display` usages.
3. **Compact uppercase section labels** with `tracking-wider`, tabular numerics (`.num`) on CZK/share values.
4. **Cockpit shell**: fixed 240px (`w-60`) left sidebar, compact "Stocks Tax / Operator cockpit" brand block, 56px top bar showing project + status chip + actions, sidebar footer with project path and last-calc.
5. **Cards**: `rounded-xl`, thin `border-borderc` border, soft `shadow-soft` only where prototype calls for it (raised hero card on Overview).
6. **Chips / badges**: `Chip` primitive with `neutral / info / ok / warn / err / filed` tones, used everywhere status, source, classification, or method comparison was previously a custom pill.
7. **Sales Review**: left queue (340px) + right detail layout, ticker-search + filter pills at the top of the queue, accent-bg highlight on the selected row, evidence-packet detail with header card, truth banner, matched-lots cards, reviewer-note + save block.
8. **Overview**: situation-room layout — status hero card, 3-up project / CSV / last-calc strip, year summary rows (filed years rendered with `bg-filed-bg/40`), unresolved-checks list with semantic-toned chips.
9. **Tax Years**: per-year card with header, 2-column body (settings on left, numbers + reconciliation on right), method-comparison strip in the bottom border. Method buttons are visually shown but read-only because the backend doesn't yet expose mutation endpoints; this is honestly labeled.
10. **Placeholder rooms** (Open Positions, FX, Audit, Settings) match the cockpit shell, label themselves "Not implemented", and explain *what's not wired yet* — they no longer pretend to be marketing slots.

## Files changed

- `ui/frontend/src/index.css` — replaced serif/cream theme with prototype color tokens (`@theme`), Inter font stack, scrollbar + focus-ring utilities, `.num` utility.
- `ui/frontend/src/App.tsx` — full rewrite of shell. Compact `Sidebar` with vertical nav and footer, `TopBar` with project name + status chip + actions, full-height flex layout (`h-screen flex`).
- `ui/frontend/src/components/ui.tsx` — **NEW.** `Chip`, `Button`, `Card`, `SectionHeader`, `KeyVal`, `EmptyState`, `StatusDot` primitives derived from the prototype.
- `ui/frontend/src/components/status-pill.tsx` — rewritten to use `Chip` + `StatusDot` with semantic prototype tones.
- `ui/frontend/src/components/panel.tsx` — **DELETED.** Was the old "eyebrow + display title" wrapper that shaped the previous landing-page look.
- `ui/frontend/src/screens/overview-screen.tsx` — rewritten as a situation room.
- `ui/frontend/src/screens/import-screen.tsx` — rewritten as compact file rows.
- `ui/frontend/src/screens/tax-years-screen.tsx` — rewritten as prototype year panels with method comparison strip.
- `ui/frontend/src/screens/sales-review-screen.tsx` — rewritten as left queue / right detail cockpit room. Live API behavior preserved (list + detail + PATCH review). Truth banner and per-sale truth/provenance kept visible.
- `ui/frontend/src/screens/coming-next-screen.tsx` — rewritten as an honest "Not implemented" placeholder room that still uses the prototype shell.

No backend files were touched.

## Components extracted / reused

Extracted into `components/ui.tsx`:

- `Chip(tone, children)` — single chip primitive used by every screen.
- `Button(variant, ...)` — primary / secondary / ghost / danger.
- `Card({ raised })` — rounded-xl thin-border surface.
- `SectionHeader({ title, subtitle, primary, secondary })` — replaces every prior `Panel(eyebrow, title, subtitle, actions)`.
- `KeyVal({ label, mono })` — compact uppercase-label + tabular value.
- `StatusDot({ status })` — semantic dot used inside chips.
- `EmptyState` (declared, not yet placed; available for future empty-collection screens).

`components/status-pill.tsx` is preserved as a thin convenience wrapper now built from `Chip + StatusDot`.

## Screens updated

| Screen          | Live data?    | Layout                                                                |
| --------------- | ------------- | --------------------------------------------------------------------- |
| Overview        | ✅ live        | Status hero card · project/CSV/last-calc strip · year rows · checks   |
| Import          | ✅ live        | Folder header card · per-file row with broker, currency, counts, warnings, symbols |
| Tax Years       | ✅ live (read) | Per-year card with header, settings panel, reconciliation, comparison strip |
| Sales Review    | ✅ live        | Left queue (search + filter + sale rows) · right detail (header card, truth chip stack, matched lots, reviewer note + PATCH) |
| Open Positions  | placeholder   | Cockpit shell + honest "Not implemented" body                         |
| FX Rates        | placeholder   | Cockpit shell + honest "Not implemented" body                         |
| Audit Pack      | placeholder   | Cockpit shell + honest "Not implemented" body                         |
| Settings        | placeholder   | Cockpit shell + honest "Not implemented" body                         |

## What still differs from the prototype

- **Method-policy buttons on Tax Years** are rendered but disabled (no mutation endpoint). The prototype's interactive year editor is intentionally not faked.
- **TopBar "Open CSV folder" / "Recalculate"** are visually present but disabled — the backend doesn't expose either endpoint yet. Better than fake buttons that throw, and better than hiding the cockpit affordances.
- **Toast on recalculation** from the prototype is omitted (no recalculate action to ack).
- **Open Positions / FX Rates / Audit Pack / Settings** screens render the prototype shell but don't yet render the prototype's interior content (positions table, FX year cards, trace diagram, settings fieldsets) — those are labeled "Not implemented" because their backend data is not yet exposed and the brief forbids fake data.
- **Number formatting** uses `en-US` locale with `style: currency, currency: CZK` (existing util), which prints `CZK 12,345`. The prototype prints `12 345 Kč`. This is a small visual discrepancy; not changed because the brief is explicit about not introducing extra surface beyond prototype alignment, and the formatter is shared backend output.
- **Right-side raw-rows drawer** in Import is omitted — backend does not yet expose raw row preview. The compact file row is preserved.

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
✓ 1733 modules transformed.
dist/index.html                   0.46 kB │ gzip:   0.30 kB
dist/assets/index-XXXX.css       23.50 kB │ gzip:   5.18 kB
dist/assets/index-XXXX.js       364.70 kB │ gzip: 112.44 kB
✓ built in 354ms
```

No backend files were modified, so backend tests were intentionally not re-run.

## Visual notes (manual)

Did not capture screenshots in this session. Verifiable manually:

- Background is now a flat warm `#FAF9F7`. No radial gradients, no glass blur.
- Sidebar is a 240px white column with thin `#EDE8E0` divider, compact CZ brand block, vertical nav with active items in `#F6EDE6` accent-bg.
- TopBar is 56px high; project label + status chip on the left, secondary + primary buttons on the right.
- Sales Review opens with a 340px queue on the left and the evidence-packet detail on the right; selected sale highlighted in `#F6EDE6/60`.
- Truth banner on Sales Review still surfaces collection truth, source chips, reasons; per-sale chips stay in the detail card.
- Tax Years 2024 (filed) renders with `#EEEBE5/30` background tint and a "do not optimise" italic strip in place of method comparison.

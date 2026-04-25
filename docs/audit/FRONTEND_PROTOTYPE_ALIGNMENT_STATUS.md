# Frontend Prototype Alignment Status

Date: 2026-04-25

## Scope

P1.4b only:

- prototype alignment audit against `ui/prototype.html`
- minimal frontend alignment fixes
- no backend/domain migrations
- no additional screen implementation beyond existing Sales Review

## Prototype Principles Extracted

- Shell layout: left persistent navigation + compact operator top bar + focused content room.
- Navigation: task rooms organized as an operator workflow, not generic pages.
- Palette: warm neutral background, high-contrast ink text, restrained accent (`#C96442`) for focus/actions.
- Typography: clean sans with strong hierarchy and tabular-feeling numeric surfaces.
- Card style: soft bordered cards with subtle layering and consistent corner radii.
- Chips/badges: compact semantic chips for status, review state, provenance, lock/frozen state.
- Status banners: immediate, prominent state banner near top of room.
- Split pane behavior: Sales Review uses queue/detail room with persistent left queue and right evidence panel.
- List density: scannable compact rows/cards, not overloaded full-width grids by default.
- Operator actions: review/flag/save controls visible at the point of evidence.
- Unresolved checks posture: clear routing from high-level state to corrective room.
- Sales Review target behavior: filterable queue, evidence detail, lot-level traceability, explicit review state.
- Truth/review/audit posture: explicit source/provenance visibility; no hidden uncertainty.

## Match / Gap Table

| Prototype concept | Current React implementation | Status | Gap | Recommended fix |
|---|---|---|---|---|
| Left navigation cockpit shell | Sidebar with all operator rooms present | PARTIAL | More card-like than prototype rail; still acceptable | Keep current shell; maintain strict room ordering and labels |
| Compact top operator bar | Top header exists with API status/contract | PARTIAL | Previously too "hero" oriented | Applied compact top bar styling and unresolved checks counter |
| Warm neutral palette with restrained accent | Warm stone palette already used | PARTIAL | Accent was underused in Sales queue focus states | Applied accent-like selected/filter states in Sales Review |
| Consistent card surfaces | `Panel` + bordered rounded cards used broadly | MATCHES | Minor variance in chip/badge styling | Keep card primitives; standardize chips later |
| Semantic chips/badges | Truth chips/status chips present | PARTIAL | Review/provenance chips were less prominent in queue | Added review chip + truth/provenance chips directly in queue rows |
| Strong status banner in room | Sales truth banner present at top | PARTIAL | Needed clearer visual emphasis for `needs_review/partial` | Strengthened banner hierarchy and added queue counters |
| Sales split-pane operator room | Sales had list + detail but list was table-heavy | PARTIAL | Felt closer to generic table app | Reworked to queue/detail split-pane with compact filterable left rail |
| Queue filtering/search in Sales | Not present before | MISSING | Harder operator triage | Added local search + review-status filter chips |
| Detail panel evidence flow | Detail already shows summary/lots/provenance/review controls | BETTER_THAN_PROTOTYPE | N/A | Keep as-is; already truthful and auditable |
| Truth/provenance visibility | Explicit truth + sources + reasons are visible | BETTER_THAN_PROTOTYPE | N/A | Preserve this posture for next screens |
| Empty/blocked state clarity | Empty meaning and reasons shown | MATCHES | N/A | Keep behavior unchanged |
| Unresolved checks flow | Overview and shell expose status pathing | PARTIAL | Not all future rooms implemented yet | Continue route truth posture; keep placeholders explicit |
| Audit-first honesty (no fake certainty) | Backend truth semantics surfaced in Sales | MATCHES | N/A | Preserve across next rooms |

## Sales Review Audit (Product/Visual)

### Does it follow split-pane operator-room feel?

Yes, now closer to prototype intent. Sales Review uses a persistent left queue rail (search + status filters + compact sale cards) and right evidence/detail panel.

### Is truth/provenance visible enough?

Yes. Collection truth banner remains top-most, and per-sale queue rows now also show truth/review/provenance chips. Detail panel still contains full truth sources/reasons.

### Does it preserve cockpit visual language?

Partial-to-yes. Palette and cards are consistent with current app shell and now use more focused accent cues in queue selection/filter chips.

### Are empty/blocked states visually obvious?

Yes. Blocked/unknown/not_implemented remain visually distinct and are not rendered as normal no-data states.

### Is detail review usable?

Yes. Review status selector, note textarea, and save action remain clear and unchanged in behavior.

### Is it too dense/plain/hidden?

Improved. The prior wide table was denser and less room-like; the queue cards are easier to scan and feel more operator-centric.

### Does it feel like a tax audit tool rather than generic CRUD?

Yes, more than before. The queue/evidence structure, truth metadata, and provenance chips keep an audit posture.

## Minimal Alignment Fixes Applied

- Shell/top bar alignment:
  - compacted `App` header into a more operator-bar feel
  - added unresolved checks count card
- Sales Review alignment:
  - added local search filter (ticker/instrument)
  - added local review-status filter chips
  - replaced dense table list with compact queue cards in left pane
  - strengthened queue selected state with accent-like visual treatment
  - elevated truth banner hierarchy and added queue counters
  - kept all truth/provenance display and backend-driven behavior

## Files Changed

- `ui/frontend/src/App.tsx`
- `ui/frontend/src/screens/sales-review-screen.tsx`
- `docs/audit/FRONTEND_PROTOTYPE_ALIGNMENT_STATUS.md`

## Commands Run

- `cd ui/frontend`
- `npm run build`

## Results

- Frontend build: Pass
- Backend tests: Not run (no backend files touched)

## Design-System Extraction Recommendation (Low Risk)

Not extracted in this slice to keep change risk low, but recommended next:

- `TruthBanner` component (collection-level truth block)
- `ProvenanceBadge` component (instrument/review source chips)
- `ReviewStatusBadge` component (unreviewed/reviewed/flagged)

These patterns are now duplicated enough to justify extraction in a small follow-up frontend-only cleanup.

## Remaining Visual/Product Gaps

- Sidebar/top bar still differ structurally from prototype in some proportions and interaction density.
- Other rooms (Open Positions/FX/Audit/Settings) remain placeholders, so cross-room cockpit consistency is incomplete.
- Shared chip/badge primitives are still local in places rather than centralized components.

## Recommended Next Frontend Screen

Open Positions is the next best slice for prototype alignment because it shares the same operator triage pattern (queue + discrepancy-focused detail) and directly supports unresolved-check workflows.

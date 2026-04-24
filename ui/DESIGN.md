# Czech Stock Tax — Operator Cockpit

Design spec + architecture for the UI that replaces the 29-sheet Excel
workbook with a calm, Claude-Desktop-style cockpit for a Czech tax
resident reconciling US-stock trades across five Yahoo-Portfolio CSVs.

Companion file: `prototype.html` — open it in any modern browser.

---

## 1. UX concept

**Operator cockpit, not a workbook.** The operator is a knowledgeable
Czech tax filer, not an accountant. They need to answer three questions,
in this order, every time they open the app:

1. **Is the model safe to trust right now?** (green/amber/red at a glance)
2. **What should I do next?** (a single recommended next action)
3. **Can I defend every number if the tax office calls?** (traceability
   in 2 clicks from headline tax down to the source CSV row)

The app is built around those three questions. Everything else — tables,
FX rates, method selection — is in service of them.

**Guiding mantras**

- _Decisions over data._ Surface the decision the operator has to make.
  The numbers exist to justify the decision, not to be browsed.
- _Evidence packet, not spreadsheet._ Every sale opens like a legal
  exhibit: here is the sell, here are the buy lots it was matched
  against, here is the FX source, here is the source CSV row.
- _Filed years are frozen._ 2024 is settled. The UI must refuse to tempt
  the operator with hypothetical re-optimisations of a filed year.
- _Honest unknowns._ If Yahoo position rows are missing, show `UNKNOWN`.
  Never green-tick something the system cannot actually verify.
- _Local-first, web-ready._ The frontend is a pure React SPA that calls
  a small HTTP API. Today that API is a localhost FastAPI wrapper around
  the existing Python engine; tomorrow it can be the same endpoints
  behind auth on a server.

---

## 2. Information architecture

```
Left sidebar (fixed, always visible)
├── Overview              ← "where do I stand?"
├── Import                ← "is my input correct?"
├── Tax Years             ← "what method / status per year?"
├── Sales Review          ← "does each sell tie to the right buy lots?"
├── Open Positions        ← "does the residual match reality?"
├── FX Rates              ← "are my rates defensible?"
├── Audit Pack            ← "export the evidence"
└── Settings              ← "paths, tolerances, defaults"

Top bar
├── Project name + path
├── Global status pill (Ready / Needs review / Blocked)
└── "Recalculate" primary action (disabled if dirty inputs)

Right-side contextual panel
└── Only on Sales Review: the selected sale's evidence
```

Screens are **not** tabs inside a dashboard. They are distinct rooms.
Each room has exactly one job, one primary action, and at most one
secondary action visible in the header.

Flow of a typical session:

```
Overview → ("4 unreviewed sells in 2025") → Sales Review
        → click through 4 sells → Overview ("Ready")
        → Audit Pack → Export ZIP evidence pack
```

---

## 3. Screen-by-screen spec

Every screen header uses the same 3-row grid: title, subtitle (one
sentence of context), primary action. No page-level tabs.

### 3.1 Overview

**One job:** answer "is the model safe, incomplete, or ready?" in
under two seconds.

Layout (top to bottom):

1. **Status hero card.** Full width, soft background. Big status word
   (`Ready` / `Needs review` / `Blocked`), one-sentence explanation,
   one CTA button wired to the recommended next action (e.g. _"Review 4
   unmatched sells in 2025"_ → deep-links to Sales Review with filter
   preset).
2. **Project strip.** Three small read-only tiles: project path, CSV
   folder (with file count badge), last calculation time. Clicking a
   tile opens the folder (desktop) or copies the path (web).
3. **Year cards.** One card per tax year, chronological. Each card
   shows: year, method pill, taxable base (CZK), tax due (CZK),
   filed/locked chip, issues count. Filed years (2024) render with a
   **muted, frozen** visual treatment — no colour accents, no
   "optimisation" hint. Unfiled years may show a small amber "1 issue"
   chip if there are unresolved checks.
4. **Unresolved issues list.** A compact list of blocking checks
   (`ERROR` / `WARN` / `INFO`). Each row links into the screen that
   can resolve it. Empty state: `"No unresolved issues."`

**Hard rule:** 2024's card must read `Filed · LIFO · Locked` and must
_not_ include any method-comparison chart, delta chip, or "save X CZK"
hint.

### 3.2 Import

**One job:** tell me whether my `.csv` folder is correct input.

Layout:

1. **Folder strip.** Path + "Open folder" button + "Recalculate from
   .csv" primary action.
2. **File cards**, one per detected file:
   - Filename, inferred broker, inferred account currency.
   - Row counts: total, valid transactions, ignored position rows.
   - Any warnings (e.g. _"2 rows have invalid trade date"_).
   - Status pill: `OK` / `Warnings` / `Error`.
   - Secondary link `"View raw rows"` — opens a drawer, never a full
     page. Raw rows are deliberately a drawer, not the main view.
3. **What was ignored** accordion: collapsed by default; expands to
   show ignored rows grouped by reason (position row, malformed date,
   zero quantity, …).

Empty state (`.csv/` empty): single card with folder icon, path,
"Drop files or open folder" CTA, and a one-line explainer of the
expected Yahoo Portfolio export format.

### 3.3 Tax Years

**One job:** manage method + filed + locked + 100 k per year.

Each year is a **year panel** (not a row in a table). Stacked
vertically, chronological, most recent first. A panel contains:

Left column (settings):
- Method policy (dropdown, with a `Filed under LIFO` lock on 2024).
- FX method (DAILY_CNB / UNIFIED_GFR).
- 100 k exemption toggle.
- Tax rate override (default 15 %).
- `Filed` checkbox + `Locked` checkbox (with confirmation dialog when
  flipping `Locked` on).

Right column (numbers):
- Taxable base, total proceeds, exempt proceeds, tax due.
- Filed tax input (for reconciliation) vs workbook tax.
- Difference line with a `Reconciled` / `Needs attention` / `Accepted
  with note` chip.

Bottom strip (collapsible):
- **Method comparison.** For _unlocked_ years only, show a small
  informational strip: _"Under FIFO this year would be CZK X; under
  MAX_GAIN CZK Y."_ For locked years (2024), the strip is replaced by
  the literal text: _"Filed year — LIFO — do not optimise."_

### 3.4 Sales Review — _the primary screen_

**One job:** let the operator personally confirm, one sell at a time,
that the system matched reasonable buy lots and that the numbers are
defensible.

Two-pane layout, Claude-Desktop style (like the conversation list +
conversation):

**Left pane (320 px).** List of sells. Sticky filter header:
- Year (chips)
- Ticker (search)
- Method (chips)
- Review status (All / Unreviewed / Reviewed / Flagged)
- Taxable / Exempt / Mixed (chips)

Each list item shows: date, ticker, broker glyph, quantity, proceeds
CZK, method pill, tiny review-status dot (unreviewed/reviewed/flagged).

**Right pane.** The evidence packet for the selected sell:

1. **Header card** — ticker, sell date, broker, qty, sell price USD,
   proceeds CZK, method, matched qty vs sell qty (warning chip if
   different), review status, `Mark reviewed` + `Flag` + `Add note`
   buttons.
2. **Matched buy lots** — one card per matched lot, not a row. Each
   card shows:
   - Buy lot ID, buy date, broker, source file + row (clickable),
     qty matched, buy price USD, sell price USD, FX buy, FX sell,
     cost basis CZK, proceeds CZK, holding days, 3-year-time-test
     chip (`Exempt` if eligible), taxable gain/loss CZK.
3. **Evidence actions row** — `Jump to raw CSV row`, `Export this
   sell as PDF`, `Open in source file`.
4. **Notes** — free-text, saved locally with timestamp + author.

Hard rule: never show 20 buy lots as a wall of rows. If a sell is
split across many lots, group cards into 3-lot bundles with a
"Show all N lots" expander — the operator should scroll through an
evidence packet, not parse a spreadsheet.

### 3.5 Open Positions

**One job:** "do the residual open lots match what I actually hold?"

Grouped by ticker. Each ticker row:
- Ticker, calculated open qty, Yahoo position qty (or `—`),
  difference, status pill (`OK` / `WARN` / `ERROR` / `UNKNOWN`).
- Expand to show per-lot breakdown (buy date, broker, qty, cost
  basis CZK, unrealised paper P/L in CZK if current price available,
  else blank).

`UNKNOWN` is a first-class status — used when Yahoo CSV has no
position rows for that ticker. Never silently rendered as `OK`.

### 3.6 FX Rates

**One job:** every rate used must be defensibly sourced.

Year panels (same visual rhythm as Tax Years):
- FX method chip.
- If UNIFIED_GFR: one rate card (USD/CZK, source link, `Cached` /
  `Manual` / `Default` badge, last-fetched timestamp, `Mark verified`
  button).
- If DAILY_CNB: summary card (rates cached X / Y days) + an expand
  that shows the daily table.
- `Fetch missing` primary button per year.
- "Show missing only" toggle in the screen header.

Locked-year FX values are read-only with a small lock glyph.

### 3.7 Audit Pack

**One job:** produce the deliverable.

- **Yearly summary table** (one row per year), read-only.
- **Traceability breadcrumb explainer** — a visual chain:
  `Yearly summary → Sell → Buy lots → Source CSV row → FX source` —
  as a horizontal diagram with live counts, to reassure the operator
  the links exist.
- **Export buttons** (primary actions stacked vertically, each with
  a one-line description):
  - Export Excel workbook
  - Export PDF audit report
  - Export CSV lot-matching ledger
  - Export ZIP evidence pack (everything + source CSVs)
- **Per-year locked snapshots list** — each entry: year, locked-at
  timestamp, method, frozen-inventory row count, `Re-export this
  snapshot` button.

### 3.8 Settings

Form, grouped:

- _Paths_ — project folder, CSV folder, output workbook path, cache
  folder.
- _Calculation defaults_ — default tax rate, default FX method,
  default 100 k toggle for new years.
- _Tolerances_ — unmatched quantity tolerance, Yahoo-position
  reconciliation tolerance.
- _Backup / lock policy_ — backup-on-recalculate toggle, require-
  confirmation-to-unlock toggle, keep-N-snapshots counter.
- _Validation_ — Excel validation behaviour (strict / warn / off).

All changes land via `PATCH /api/settings`; the app shows a subtle
`Unsaved` pill until the patch succeeds.

---

## 4. Component inventory

All primitives are `shadcn/ui` where available, wrapped in our own
thin layer (`components/ui/*`). Domain components (`components/
domain/*`) are thin, semantic, and testable in isolation.

**Primitives**

- `Button` (primary / secondary / ghost / danger)
- `IconButton`
- `Input`, `NumberInput`, `Select`, `Switch`, `Checkbox`, `Textarea`
- `Chip` (neutral / info / success / warn / error / filed)
- `Pill` (status hero — larger than Chip)
- `Card`, `CardHeader`, `CardBody`, `CardFooter`
- `Panel` (flat card, used for year panels)
- `Drawer` (right-slide, for raw-row inspection)
- `Dialog` (confirmation, lock / unlock)
- `Tooltip`, `Popover`
- `Tabs` (only inside a single card, never at page level)
- `Accordion`
- `EmptyState`
- `ProgressBar` (thin, calm)
- `Toast`

**Domain**

- `SidebarNav`, `NavItem`
- `TopBar`, `GlobalStatus`
- `StatusHero` (the Overview hero)
- `YearCard`, `YearPanel`
- `FileCard` (Import)
- `SellListItem`, `SellDetail`, `BuyLotCard`
- `OpenPositionRow`, `OpenLotBreakdown`
- `FXYearPanel`, `FXDailyTable`
- `AuditTraceDiagram`
- `ExportAction`
- `LockDialog`
- `SourceRefLink` (renders `Lynx.csv:row 184` as a clickable chip)

---

## 5. Data model (frontend TypeScript shapes)

```ts
// Always-loaded global state
type AppStatus = {
  project_path: string;
  csv_folder: string;
  output_path: string;
  last_calculated_at: string | null;   // ISO 8601
  global_status: "ready" | "needs_review" | "blocked";
  next_action: { label: string; href: string } | null;
  unresolved_checks: Check[];
};

type Check = {
  id: string;
  level: "error" | "warn" | "info";
  message: string;
  year?: number;
  sell_id?: string;
  href: string;        // deep-link target
};

type ImportSummary = {
  folder: string;
  files: ImportFile[];
};
type ImportFile = {
  name: string;
  broker: string;
  account_currency: string | null;
  total_rows: number;
  trade_rows: number;
  ignored_rows: number;
  warnings: string[];
  status: "ok" | "warnings" | "error";
};

type TaxYear = {
  year: number;
  method: Method;
  filed_method: Method | null;       // only set for filed years
  fx_method: "FX_DAILY_CNB" | "FX_UNIFIED_GFR";
  tax_rate: number;                   // e.g. 0.15
  exemption_100k: boolean;
  taxable_base_czk: number;
  gross_proceeds_czk: number;
  exempt_proceeds_czk: number;
  tax_due_czk: number;
  filed: boolean;
  locked: boolean;
  filed_tax_input_czk: number | null;
  reconciliation_status:
    | "not_filed"
    | "reconciled"
    | "needs_attention"
    | "accepted_with_note";
  reconciliation_note: string | null;
  method_comparison: Record<Method, number> | null;  // null when locked
};
type Method = "FIFO" | "LIFO" | "MIN_GAIN" | "MAX_GAIN";

type Sell = {
  id: string;
  date: string;
  ticker: string;
  instrument_id: string;
  broker: string;
  source: SourceRef;
  quantity: number;
  price_usd: number;
  proceeds_czk: number;
  method: Method;
  matched_quantity: number;
  review_status: "unreviewed" | "reviewed" | "flagged";
  note: string | null;
  classification: "taxable" | "exempt" | "mixed";
  year: number;
  matched_lots: MatchedLot[];
};

type MatchedLot = {
  lot_id: string;
  buy_date: string;
  broker: string;
  source: SourceRef;
  quantity: number;
  buy_price_usd: number;
  sell_price_usd: number;
  fx_buy: number;
  fx_sell: number;
  cost_basis_czk: number;
  proceeds_czk: number;
  holding_days: number;
  time_test_exempt: boolean;
  gain_loss_czk: number;
};

type SourceRef = { file: string; row: number };

type OpenPosition = {
  ticker: string;
  instrument_id: string;
  calculated_qty: number;
  yahoo_qty: number | null;        // null → UNKNOWN
  difference: number | null;
  status: "ok" | "warn" | "error" | "unknown";
  lots: OpenLot[];
};

type OpenLot = {
  lot_id: string;
  buy_date: string;
  broker: string;
  quantity: number;
  cost_basis_czk: number;
  unrealised_pl_czk: number | null;
};

type FxYear = {
  year: number;
  method: "FX_DAILY_CNB" | "FX_UNIFIED_GFR";
  unified_rate: number | null;
  daily_cached: number;
  daily_expected: number;
  missing_dates: string[];
  source_label: string;
  source_url: string | null;
  verified_at: string | null;
  manual_override: boolean;
  locked: boolean;
};

type Settings = {
  project_folder: string;
  csv_folder: string;
  output_path: string;
  cache_folder: string;
  default_tax_rate: number;
  default_fx_method: "FX_DAILY_CNB" | "FX_UNIFIED_GFR";
  default_100k: boolean;
  unmatched_qty_tolerance: number;
  position_reconciliation_tolerance: number;
  backup_on_recalc: boolean;
  require_confirm_unlock: boolean;
  keep_n_snapshots: number;
  excel_validation: "strict" | "warn" | "off";
};
```

---

## 6. API contract (FastAPI, v1)

All responses JSON. `application/json; charset=utf-8`. Times ISO 8601.
Monetary fields are `{ amount: number, currency: "CZK" | "USD" }` where
ambiguous; plain numbers elsewhere (documented).

```
GET  /api/status                       → AppStatus
GET  /api/import                       → ImportSummary
POST /api/recalculate                  → { run_id, started_at }
GET  /api/recalculate/:run_id          → { status, progress, log[] }

GET  /api/years                        → TaxYear[]
GET  /api/years/:year                  → TaxYear
PATCH /api/years/:year/settings        ← { method?, fx_method?,
                                           exemption_100k?, tax_rate?,
                                           filed?, locked?,
                                           filed_tax_input_czk?,
                                           reconciliation_note? }
                                       → TaxYear

GET  /api/sales?year=&ticker=&status=  → Sell[]      (list)
GET  /api/sales/:id                    → Sell        (with matched_lots)
PATCH /api/sales/:id/review            ← { review_status?, note? }
                                       → Sell
POST /api/sales/:id/export             → { download_url }

GET  /api/open-positions               → OpenPosition[]

GET  /api/fx                           → FxYear[]
POST /api/fx/fetch                     ← { year, method }
                                       → { fetched: number, missing: [] }
PATCH /api/fx/:year                    ← { manual_override?, verified?,
                                           unified_rate? }

GET  /api/audit                        → { summary, snapshots }
POST /api/audit/export                 ← { kind: "xlsx"|"pdf"|"csv"|"zip" }
                                       → { download_url }

GET  /api/settings                     → Settings
PATCH /api/settings                    ← Partial<Settings> → Settings
```

Errors: `{ error: { code, message, details? } }` with HTTP 4xx/5xx.
Long jobs (`/recalculate`, `/fx/fetch`, `/audit/export`) return a
`run_id`; the UI polls `/:run_id` or subscribes via SSE
`GET /api/events`.

---

## 7. Local-app architecture

```
┌────────────────────────────────────────────────────────────┐
│  Desktop shell  (Tauri 2.x)                                │
│  - Window + menu + file-system access                      │
│  - Spawns the Python sidecar process                       │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Frontend  (React 18 + TS + Vite + Tailwind +        │ │
│  │             shadcn/ui + TanStack Query + Zustand)     │ │
│  │  - Pure SPA, no Tauri-specific code outside           │ │
│  │    src/platform/ (swappable for web build)            │ │
│  │  - Talks to backend via `fetch("/api/…")`             │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Backend bridge  (FastAPI, local 127.0.0.1:port)     │ │
│  │  - Wraps the existing build_stock_tax_workbook.py     │ │
│  │    as a library (refactor `main()` into callable fns) │ │
│  │  - Reads `.csv/` + caches, writes stock_tax_system.xlsx│ │
│  │  - Stateless HTTP; persistent state is the workbook   │ │
│  │    + `cache/` + `.ui_state.json` (notes, flags)       │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

**Why this shape:**
- The UI never parses Excel. All it sees is JSON.
- The Python engine stays the single source of truth for calculations.
- The same React bundle works behind `localhost:3000` (dev), inside
  Tauri (desktop), or served from any host with auth (web later).
- Platform-specific concerns (open-folder, file drop, native menu)
  live in `src/platform/tauri.ts` and `src/platform/web.ts`. Every
  call site uses the abstraction — zero `if (window.__TAURI__)` sprinkled
  around.

**Directory layout**

```
ui/
  frontend/
    src/
      app/                 routes + layout
      components/
        ui/                shadcn primitives
        domain/            YearCard, SellDetail, …
      features/            one folder per screen
        overview/
        import/
        years/
        sales/
        open-positions/
        fx/
        audit/
        settings/
      lib/
        api.ts             typed fetch client
        format.ts          CZK / USD / date formatters
        queries.ts         TanStack Query keys + hooks
      platform/
        index.ts
        tauri.ts
        web.ts
      store/               Zustand (UI state only)
      types/               shared with backend via openapi-typescript
    index.html
    vite.config.ts
  backend/
    app/
      main.py              FastAPI entry
      routes/
        status.py
        years.py
        sales.py
        …
      services/
        engine.py          thin wrapper around build_stock_tax_workbook
      schemas.py           pydantic, exported to OpenAPI
    pyproject.toml
  tauri/
    tauri.conf.json
    src-tauri/main.rs      spawns sidecar FastAPI, opens window
```

---

## 8. Visual design direction

**Palette** (warm neutrals + one accent — Claude Desktop spirit)

| Token             | Light               | Dark                |
|-------------------|---------------------|---------------------|
| `bg`              | `#FAF9F7`           | `#1B1A17`           |
| `surface`         | `#FFFFFF`           | `#24221E`           |
| `surface-raised`  | `#FFFDFA`           | `#2B2924`           |
| `border`          | `#EDE8E0`           | `#3A362F`           |
| `text-primary`    | `#1F1E1B`           | `#F2EEE6`           |
| `text-secondary`  | `#6E6A62`           | `#A7A196`           |
| `text-muted`      | `#A09B91`           | `#706A5F`           |
| `accent` (CTA)    | `#C96442`           | `#E08867`           |
| `accent-soft`     | `#F6EDE6`           | `#3B2A22`           |
| `success`         | `#4E7F63`           | `#7FB793`           |
| `warn`            | `#B57614`           | `#E0A54B`           |
| `error`           | `#B0413E`           | `#E07474`           |
| `filed` (locked)  | `#5A574F` (neutral) | `#9A958A`           |

Accent is used _sparingly_: primary buttons, the recommended-next-action
CTA, and the "Mark reviewed" button. Nothing else.

**Typography**

- UI: `Inter` / system-ui, 14 px base, 1.5 line-height, tracking −0.005em.
- Numbers (monetary / quantity): `JetBrains Mono` or `Inter` with
  `font-variant-numeric: tabular-nums`. Always tabular for columnar
  alignment.
- Scale: 28 / 20 / 16 / 14 / 13 / 12.
- Weights: 400 body, 500 labels, 600 headers. No 700.

**Spacing & radius**

- 8-pt base grid. Card padding 24 px. Inter-card gap 16 px.
- Radius: 10 px cards, 8 px inputs, 999 px chips.
- Borders: 1 px, `border` token, never doubled.
- Shadows: almost none. At most `0 1px 2px rgb(0 0 0 / 0.04)` on
  raised cards. No glow, no gradient.

**Iconography**

- `lucide-react`, 16 / 20 px, 1.5 stroke. Icons are neutral-grey; they
  never carry the accent colour.

**Motion**

- 160 ms ease-out for most transitions. 240 ms for drawers. No
  bouncing, no spring curves. The app should feel still.

**Anti-patterns (explicit)**

- No dense data tables as a primary view.
- No sparklines, no donuts, no hero charts on Overview.
- No gradients, no glassmorphism, no glow.
- No emoji in UI copy.
- No exclamation points.
- No red-green diff screens — differences use amber chips, not traffic
  lights.

---

## 9. Interaction states

Every interactive component covers: default, hover, focus-visible
(accent ring, 2 px, offset 2 px), active, disabled, loading (inline
spinner or skeleton, never a blocking overlay for small actions).

**Data loading.** Every screen has three zones: known-instant (rendered
from cached store), fast (< 300 ms, skeleton blocks), and slow
(> 300 ms, progress indication + partial render). Never flash a
spinner then the data — if data arrives within 120 ms, show it
directly, no skeleton.

**Recalculate.** Long job. Trigger: confirm dialog if inputs changed →
top-bar progress strip ("Recalculating… step 4 of 9: matching lots") →
toast on completion linking to Overview. Cancellable.

**Lock a year.** Dialog: title, "Lock 2025 under LIFO?", body explains
that a locked year is frozen (snapshot stored), links to the actual
snapshot location, `Cancel` + `Lock year` buttons. `Lock year` is
accent-coloured and requires typing the year number into a confirm
field. Locking a _filed_ year is one click; locking an _unfiled_ year
prompts a secondary confirm.

**Unlock.** Destructive. Danger button. Dialog warns: "This discards
the frozen snapshot. Historical exports already delivered are still
valid." Requires typing the year.

**Mark reviewed.** One click. Stores to local state via
`PATCH /api/sales/:id/review`. Optimistic update with rollback on
error.

**Drawer for raw rows.** Right-slide 480 px, dimmed overlay, focus
trapped, `Esc` closes.

**Keyboard.**

- `g o` Overview, `g i` Import, `g y` Years, `g s` Sales, `g p`
  Positions, `g f` FX, `g a` Audit, `g ,` Settings.
- In Sales: `j` / `k` prev/next sell, `r` mark reviewed, `f` flag,
  `n` focus note.
- `⌘ K` / `Ctrl K` opens command palette (later — not in prototype).

---

## 10. Error states

**No CSV folder.** Overview status: `Blocked`. Overview CTA: "Point
me at your CSV folder" → opens Settings with the path field focused.

**CSV folder exists but empty.** Import screen empty state.

**Malformed CSV.** File card turns `Error`; the folder is still
importable for other files. Primary CTA on the file card: "Open raw
rows" (drawer). Recalculation refuses to run if _any_ file is in
`error`.

**Backend unreachable.** Top-bar status → `Blocked · backend offline`,
retry chip every 5 s. All mutating actions disabled with a tooltip.

**Recalculation failed.** Toast with short error; _full log_ opens a
drawer. Last-known-good data remains visible (we do not blank the
screen).

**Lock attempted on a year with unresolved ERROR checks.** Dialog
refuses and lists the blocking checks with deep-links.

**Sell has unmatched quantity > tolerance.** Sell header chip:
`Unmatched: 4 sh`. Prevents the year from turning `Ready`. The operator
must either flag the sell, add a note, or fix the CSV.

**Yahoo position rows missing for a ticker.** Open Positions status:
`UNKNOWN`, never `OK`. Copy: _"Yahoo did not export a current position
for MSFT. Verify from your broker directly."_

**FX rate missing for a date within the year's scope.** FX screen
shows `Stale` chip; the year's status flips to `Needs review`;
Overview lists it as an unresolved check; recalculation still runs
but the affected transactions carry a per-row warning.

**Locked-year attempt at edit.** Inline toast: _"2024 is locked.
Unlock it from Tax Years → 2024 → Unlock, then recalculate."_

---

## 11. Clickable prototype

See `prototype.html`. Single file, uses React 18 + Tailwind + Babel
standalone via CDN, fully offline-capable once the CDN payloads are
cached. Demonstrates all eight screens with mock data, including the
Sales Review two-pane flow, 2024 as filed+locked under LIFO (no
optimisation chrome), FX status with a stale-rate warning, an open
position in `UNKNOWN`, and every export action. Styling, palette and
rhythm are intended to match this spec.

---

## Recommended next implementation steps

**Week 1 — backend bridge, behind the existing engine.**
1. Refactor `build_stock_tax_workbook.py`: extract `main()` into
   `engine.run(input_files, output, options)` returning a structured
   result object (not just writing Excel).
2. Add `backend/` FastAPI app with `/api/status`, `/api/import`,
   `/api/years`, `/api/sales`, `/api/sales/:id`. Backed by the
   structured result cached in memory + `.ui_state.json` for user
   flags (reviewed / flagged / notes).
3. Keep writing `stock_tax_system.xlsx` — it is still the deliverable.
   The UI _consumes_ the same Python objects, does not re-parse Excel.

**Week 2 — frontend skeleton.**
4. Vite + React + TS + Tailwind + shadcn/ui scaffolding under
   `ui/frontend/`. TanStack Query client pointed at `127.0.0.1:8787`.
5. Implement `Overview`, `Import`, `Tax Years` using real API data.
   Kill the prototype's mock store once parity is reached.

**Week 3 — the two screens that earn the app's keep.**
6. `Sales Review` with full two-pane flow, review actions, note
   persistence, source-row drawer.
7. `FX Rates` with CNB fetcher wired up; `Open Positions` with
   `UNKNOWN` handling.

**Week 4 — outputs + desktop shell.**
8. `Audit Pack` export actions (Excel / PDF / CSV / ZIP).
9. Wrap with Tauri 2.x. Sidecar-spawn the FastAPI process. Ship as
   signed installer for Windows and macOS.

### What should be local-desktop first
- Everything that touches the user's filesystem: `.csv/` discovery,
  opening files in the native editor, writing the workbook, the ZIP
  evidence pack, backup policy, file-drop import.
- The CNB daily/yearly fetchers (so they can run offline-first from
  cache).
- The notes/flags persistence (`.ui_state.json` next to the workbook).

### What can wait for the web version
- Auth & multi-user. In local mode a single operator is assumed.
- Cloud backup. For web, move `.ui_state.json` + `cache/` behind an
  S3-compatible object store.
- Remote CNB fetch proxy. Desktop can call CNB directly; web
  deployments might need to route through a backend to respect CORS
  or rate limiting.
- PDF rendering. Desktop can shell out to headless Chromium; web
  should delegate to a dedicated rendering service.

### What backend endpoints are needed first (ship order)

1. `GET /api/status` — lights up the shell.
2. `GET /api/import` + `POST /api/recalculate` — the import flow.
3. `GET /api/years`, `PATCH /api/years/:year/settings` — year panels
   and locking (LIFO lock for 2024 is enforced server-side, not just
   UI).
4. `GET /api/sales`, `GET /api/sales/:id`, `PATCH /api/sales/:id/review`
   — sales review is the soul of the product.
5. `GET /api/fx`, `POST /api/fx/fetch` — defensibility.
6. `GET /api/open-positions` — reconciliation.
7. `POST /api/audit/export` — the deliverable.
8. `GET /api/settings`, `PATCH /api/settings` — last, because everything
   else must work with sane defaults before settings are exposed.

# Excel Retirement Audit

## Executive Verdict

Excel is not the frontend anymore, but Excel is still part of backend truth.

That is the core problem.

Evidence:

- The workbook CLI explicitly reads user-maintained sheets back from `stock_tax_system.xlsx` (`build_stock_tax_workbook.py:15-18`).
- `calculate_workbook_data()` loads workbook state before building the result (`build_stock_tax_workbook.py:1930-1995`).
- The FastAPI engine path calls that function directly (`stock_tax_app/engine/core.py:489-494`).
- The backend default output path is still `stock_tax_system.xlsx` (`stock_tax_app/backend/main.py:21`).

So the current architecture is not “backend truth with Excel export”.
It is “workbook-backed truth wrapped by the backend”.

## Every Excel Dependency

| Excel dependency | Code location | Current role | Still part of calculation truth? | Used by tests? | Retirement status |
|---|---|---|---|---|---|
| Existing workbook readback | `build_stock_tax_workbook.py:520-534` | Loads user-maintained workbook sheets into state | Yes | Indirectly yes | Must be migrated first |
| `Settings` sheet | `build_stock_tax_workbook.py:541-566`, `2407-2440` | Stores year tax rate, FX method, 100k toggle, locked flag | Yes | Yes via fixture | Must be migrated first |
| `Instrument_Map` sheet | `635-668`, `2529-2545` | Stores ticker -> instrument identity mapping | Yes | Yes via fixture | Must be migrated first |
| `FX_Yearly` sheet | `591-632`, `2573-2602` | Stores yearly FX rates and source notes | Yes | Yes | Must be migrated first |
| `FX_Daily` sheet | `591-632`, `2548-2571` | Stores daily FX overrides/cacheable data | Yes for `FX_DAILY_CNB` years | Yes | Must be migrated first |
| CNB cache JSON next to workbook | `827-925` | Supplements daily FX without workbook editing | Yes when daily FX is needed | Not directly | Must be migrated into backend-owned FX store |
| `Corporate_Actions` sheet | `715-744`, `2604-2653` | Manual split/reverse-split/ticker-change input | Yes | Yes via fixture | Must be migrated first |
| `Method_Selection` sheet | `671-696`, `2685-2714` | Stores matching method per `(year, instrument)` | Yes | Yes | Must be migrated first |
| `Locked_Years` sheet | `699-712`, `2715-2743` | Stores operator lock flag per year | Yes | Yes | Must be migrated first |
| `Frozen_Inventory` sheet | `747-757`, `2744-2819` | Snapshot seed for locked years | Yes | Yes | Must be migrated first |
| `Frozen_Lot_Matching` sheet | `760-769`, `2820-2900` | Snapshot of locked-year match lines | Yes | Yes | Must be migrated first |
| `Frozen_Snapshots` sheet | `772-780`, `2984-3040` | Snapshot manifest / audit bookkeeping | Yes for locked-year integrity checks | Yes | Must be migrated first |
| `Review_State` sheet | `783-794`, `3328-3347` | Legacy review-state persistence in workbook | No for current API truth | Indirectly yes | Can be removed after state consolidation |
| `Filed_Year_Reconciliation` sheet | `797-820`, `3282-3325` | Stores filed tax due input and comparison | Yes for filed-year reconciliation | Yes | Must be migrated first |
| Workbook write path | `2071-2124`, `2131-3535` | Materializes the 29-sheet workbook | No for pure engine math, yes for current product workflow | Yes | Keep temporarily as export/debug only |
| Workbook validator | `verify_workbook.py`, imported at `2111-2118` | Blocks invalid workbook output | No for engine math, yes for current workbook workflow | Yes | Keep only while workbook export exists |
| Root `stock_tax_system.xlsx` | runtime default + test fixture | Legacy persistence/output file | Yes today | Yes | Must not delete yet |
| `temp/stock_tax_system.xlsx` | no code refs | Scratch artifact only | No | No | Delete candidate |

## Workbook Logic That Must Move Into Backend/Engine Models

These functions live in the workbook script today. If Excel stops being core, these have to exist as backend-owned engine modules, not as worksheet side-effects.

### CSV import and normalization

- `read_csv_file()` (`330-350`)
- `normalize_transactions()` (`353-475`)

### Instrument identity

- `build_instrument_map()` (`635-658`)
- `apply_instrument_map()` (`661-668`)

### FX policy and resolution

- `build_fx_tables()` (`591-632`)
- `refresh_fx_daily_for_years()` (`890-926`)
- `FXResolver.rate_for()` (`933-961`)

### Matching and tax logic

- `rank_lots_for_sell()` (`1026-1054`)
- `_make_match_line()` (`1057-1106`)
- `_match_global_optimized()` (`1109-1213`)
- `match_sell()` (`1215-1238`)
- `simulate()` (`1275-1540`)
- `build_yearly_summary()` (`1564-1657`)
- `run_method_comparison()` (`1664-1715`)
- `build_open_position_rows()` (`1759-1787`)
- `build_check_rows()` (`1790-1921`)

### Year policy and locked history

- `build_method_selection()` (`671-696`)
- `build_locked_years()` (`699-712`)
- `load_frozen_inventory()` (`747-757`)
- `load_frozen_matching()` (`760-769`)
- `load_frozen_snapshots()` (`772-780`)
- `load_filed_reconciliation()` (`797-820`)

### UI/state history still entangled with workbook

- `load_review_state()` (`783-794`)
- `_write_review_state()` (`3328-3347`)
- `_write_sell_review()` (`3073-3144`)

This is especially messy because current API review state actually comes from `.ui_state.json`, not workbook `Review_State`, while the workbook write path still writes `result.review_state` loaded from the workbook. That is split state, not clean separation.

## What Excel Still Owns Today

### Persistence

Excel currently persists:

- per-year tax settings
- per-year FX mode
- per-year 100k toggle
- instrument identity map
- corporate actions
- method selection
- lock state
- frozen year-end inventory
- frozen match lines
- filed-year tax comparison input

That is far too much. It means a missing or stale workbook changes backend behavior.

### Audit and operator workflow

Excel currently provides:

- lot-level audit ledger
- yearly summary
- method comparison
- checks
- audit report
- frozen-year snapshot visibility

These are exactly the surfaces the frontend should own long-term.

### Export/debug only candidates

After migration, these can survive as export/debug only:

- `write_workbook()`
- workbook sheet writers
- `verify_workbook.py`
- CLI wrapper for workbook generation

They should consume backend-owned state and an `EngineResult`, not act as the persistence source.

## Can It Be Removed Now?

### Can remove now

- Nothing in the core workbook readback path can be removed safely now.
- The only near-term removable Excel state is workbook `Review_State`, but only after review persistence is consolidated to `.ui_state.json` or another backend store and the workbook export adapter is updated.

### Can migrate later but keep temporarily

- Workbook writing and workbook validation
- `Sell_Review`, `Open_Lots_Review`, `Audit_Report`, `Operator_Dashboard`, `README` sheets

These are output/reporting concerns, not engine truth.

### Must stay temporarily

- Settings / FX / instrument map / corporate actions / method selection / locked snapshots / filed reconciliation inputs

Those are currently part of engine truth.

## Exact Excel-Centering Blockers

### Blocker 1: Workbook is a state database

`load_existing_user_state()` reads real operator data from workbook sheets (`520-534`).

Until that state lives in backend-owned storage, Excel cannot stop being core.

### Blocker 2: Locked years are workbook snapshots

Locked-year replay depends on `Frozen_Inventory`, `Frozen_Lot_Matching`, and `Frozen_Snapshots` (`1275-1540`, `1866-1879`).

Until those snapshots live in backend-owned storage, filed/locked history is workbook-bound.

### Blocker 3: Review state is split across workbook and `.ui_state.json`

- workbook legacy review state: `load_review_state()` (`783-794`)
- API review state: `stock_tax_app/engine/ui_state.py`

This is already inconsistent. It has to be collapsed into one backend-owned state path before workbook retirement.

### Blocker 4: Recalculate is workbook-writing by default

`POST /api/recalculate` writes and validates the workbook (`backend/main.py:37-39`, `engine/core.py:495-496`, `build_stock_tax_workbook.py:2071-2124`).

That keeps Excel in the hot path for a backend operation that should be engine-first.

## Migration Target

Future canonical ownership should look like this:

- Backend-owned store:
  - year settings
  - FX rates and provenance
  - instrument map
  - corporate actions
  - per-year/per-instrument method selection
  - locked snapshots
  - review state and reconciliation notes
- Engine modules:
  - import normalization
  - matching
  - FX resolution
  - yearly summary
  - open positions
  - checks
- Excel:
  - optional export renderer only

Until that split exists, saying “Excel is optional” is fiction.

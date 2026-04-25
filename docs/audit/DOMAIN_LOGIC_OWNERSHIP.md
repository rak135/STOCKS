# Domain Logic Ownership

## Summary

Business logic is concentrated in one giant file, `build_stock_tax_workbook.py`. The backend package mostly reshapes its output. The frontend currently owns almost no business logic beyond display formatting.

That is good in one narrow sense: business logic is not duplicated across frontend and backend.

That is bad in the more important sense: the business logic is bundled together with workbook persistence and workbook writing.

## Domain Map

| Domain | Current owner | Duplicate owner(s) | Frontend/backend/docs disagreement | Status | Future canonical owner |
|---|---|---|---|---|---|
| Yahoo CSV import/parsing | `build_stock_tax_workbook.read_csv_file()` and `normalize_transactions()` (`330-475`) | `inspect_csvs.py` duplicates date parsing and row inspection | Docs treat import as stable; runtime truth is still workbook script driven | Risky | `stock_tax_app.engine.imports` |
| Transaction normalization | `normalize_transactions()` (`353-475`) | None in product code | None major | Safe-ish but over-centralized | `stock_tax_app.engine.imports` |
| Symbol/ticker grouping | `build_instrument_map()` and `apply_instrument_map()` (`635-668`) | `extract_position_rows()` also relies on mapped `Instrument_ID` (`3050-3070`) | Docs say map is operator-editable in workbook; no frontend editor exists | Risky | Backend state store + `engine.identity` |
| Lot matching | `simulate()`, `match_sell()`, `_match_global_optimized()` (`1109-1540`) | None | Frontend has no live sales-review UI yet | Safe logic, bad packaging | `stock_tax_app.engine.matching` |
| FIFO/LIFO/MIN_GAIN/MAX_GAIN selection | `build_method_selection()` (`671-696`) + matching methods | `stock_tax_app.engine.policy.default_method_for()` duplicates year-default logic | `ui/prototype.html` mocks 2025 as `LIFO`; live API returns 2025 as `FIFO` | Risky | One backend policy/service module |
| Yearly method policy | `build_stock_tax_workbook.FILED_YEARS`, `YEAR_DEFAULT_METHODS` (`84-93`) | `stock_tax_app.engine.policy` (`25-43`) | Internal comments disagree with runtime defaults; prototype also disagrees | Risky | `stock_tax_app.engine.policy` only |
| Locked/filed years | workbook `build_locked_years()` + snapshot loaders (`699-780`) | `stock_tax_app.engine.policy` (`25-115`) | Docs imply server truth; actual truth is split between server policy and workbook state | Risky | Backend-owned lock/snapshot store |
| 100k CZK exemption | `build_yearly_summary()` (`1624-1635`) | None | Frontend only displays results; no live edit path | Safe logic, incomplete workflow | `stock_tax_app.engine.summary` |
| Time test | `_make_match_line()` + `_add_years()` (`1074-1105`, `1018-1024`) | None | Frontend has no sale-detail view to explain exemptions | Safe logic, hidden from UI | `stock_tax_app.engine.matching` |
| FX handling | `build_fx_tables()`, `refresh_fx_daily_for_years()`, `FXResolver` (`591-632`, `890-961`) | None | `README_OPERATOR.md` says operator maintains FX tables; code can auto-download CNB data | Risky | `stock_tax_app.engine.fx` + backend FX store |
| Missing/manual FX handling | `FXResolver.rate_for()` fallback + `build_check_rows()` (`942-961`, `1839-1864`) | None | Design doc says missing FX is a visible workflow; actual frontend page is placeholder | Risky | `stock_tax_app.engine.fx` with explicit failure states |
| Tax summary by year | `build_yearly_summary()` (`1564-1657`) | `stock_tax_app.engine.core._build_tax_years()` reshapes the result (`185-258`) | No major disagreement, but frontend only shows read-only subset | Safe-ish | `stock_tax_app.engine.summary` |
| Sale review state | `.ui_state.json` via `stock_tax_app.engine.ui_state` | workbook `Review_State` sheet (`783-794`, `3328-3347`) | Backend API uses `.ui_state.json`; workbook export still uses workbook review state | High risk | Backend-owned UI state only |
| Open positions | `build_open_position_rows()` + `extract_position_rows()` (`1759-1787`, `3050-3070`) | engine core transforms lots again (`337-388`) | Backend returns real data, but current dataset yields 20 `unknown` positions and frontend route is placeholder | Incomplete | `stock_tax_app.engine.positions` |
| Audit/export pack | workbook `_write_audit_report()` + `verify_workbook.py` + `engine.core._build_audit_summary()` | Docs/spec promise export endpoints that do not exist | Backend has summary only; frontend has placeholder page | Incomplete | Backend audit/export service + optional export adapters |

## Specific Ownership Problems

### 1. Policy constants are duplicated

Duplicated in:

- `build_stock_tax_workbook.py:84-93`
- `stock_tax_app/engine/policy.py:25-43`

This is not a style nit. It is a correctness risk.

### 2. Review state is split

Current owners:

- API/UI state: `.ui_state.json` through `stock_tax_app/engine/ui_state.py`
- Workbook legacy state: `Review_State` sheet through `build_stock_tax_workbook.load_review_state()`

This is already a source-of-truth violation.

### 3. The frontend has no canonical owner for real operator workflows after import/overview/years

Backend owners exist for:

- sales
- open positions
- FX
- audit

Frontend owners do not. Those routes are placeholders.

### 4. The docs still present workbook persistence as normal

`ui/DESIGN.md:534-536` literally describes persistent state as workbook + cache + `.ui_state.json`.

That is the exact architecture we need to retire.

## Safe / Risky / Incomplete Areas

### Safe

- FIFO/LIFO/MIN_GAIN/MAX_GAIN matching core appears internally consistent and has some coverage (`test_min_gain_optimality.py`)
- Time-test computation is centralized
- API read endpoints mostly return real engine data

### Risky

- FX fallback behavior
- duplicated policy constants
- row-number-based transaction IDs
- split review-state storage
- locked snapshot persistence in workbook sheets

### Incomplete

- frontend sales review
- frontend FX review
- frontend open positions review
- frontend audit/export workflow
- editable year settings/method workflow

## Future Canonical Owners

Recommended target modules:

- `stock_tax_app.engine.imports`
- `stock_tax_app.engine.identity`
- `stock_tax_app.engine.fx`
- `stock_tax_app.engine.matching`
- `stock_tax_app.engine.summary`
- `stock_tax_app.engine.positions`
- `stock_tax_app.engine.checks`
- `stock_tax_app.state.project_store` for editable operator state and snapshots

The workbook writer should become an adapter that consumes those modules, not the place where they live.

# Implementation Notes

Technical notes accompanying `build_stock_tax_workbook.py`. Read these
before modifying the calculation engine or extending the workbook.

## Architecture in one paragraph

Python reads all five Yahoo Portfolio CSVs, normalises rows into
`Transaction` dataclasses, stitches them chronologically with
operator-maintained `Corporate_Actions`, replays the stream to build
and consume `Lot` dataclasses under the selected matching method, and
emits `MatchLine` dataclasses. Computed sheets (`Lot_Matching`,
`Yearly_Tax_Summary`, `Method_Comparison`, `Checks`, `Audit_Report`,
`Lots`, `Split_Audit`, `Operator_Dashboard`) are rebuilt from scratch
every run. User-editable sheets (`Settings`, `Instrument_Map`,
`FX_Daily`, `FX_Yearly`, `Corporate_Actions`, `Method_Selection`,
`Locked_Years`) are read back from the existing workbook so operator
input is preserved across regenerations. `Frozen_Inventory` and
`Frozen_Lot_Matching` are a snapshot mechanism: once written they act
as a "locked" seed for future runs.

## Key decisions

### Python-side computation, Excel as UI

Excel formulas are fragile for multi-sell / multi-lot matching. All
calculations happen in Python; the workbook stores the *results* of
the calculation. Formulas are limited to cosmetic concerns
(conditional-formatting rules).

### One transaction per Yahoo CSV row

A transaction's identity is `source_file#source_row`, so every line on
`Transactions`, `Lots`, and `Lot_Matching` can be traced back to the
exact CSV cell.

### Global matching across brokers

Per Czech rules, the tax return does not distinguish brokers. Lots
enter a single pool keyed by `Instrument_ID`. Broker/account metadata
is preserved on every matched row for audit but has no effect on the
calculation.

### Instrument identity

The operator can map `Yahoo Symbol → Instrument_ID / ISIN` on
`Instrument_Map`. The default is `Instrument_ID = Yahoo Symbol`, so
ticker renames or venue differences need an operator edit. Matching
uses `Instrument_ID`, never the raw symbol.

### FX method per year

Each tax year is calculated against **one** FX method — either
`CNB_YEARLY` (a single average for the year) or `CNB_DAILY` (per
trade-date rate). The resolver falls back up to 10 calendar days
backwards if a specific daily rate is missing, and finally to the
year's yearly rate, emitting a WARN on the Checks sheet so the
operator knows.

The default yearly FX table in `build_stock_tax_workbook.py`
(`DEFAULT_FX_YEARLY`) is *indicative only*. Operator must verify each
year against CNB.

### 3-year time test

A matched lot is time-test exempt when
`sell_date > buy_date + 3 calendar years`. Implemented via
`_add_years`, which handles leap-year 29 Feb buys by falling back to
28 Feb.

### 100 000 CZK exemption

Applied strictly: if the year's total gross sale proceeds (in CZK)
is less than or equal to 100 000 CZK **and** the operator set
`Apply 100k exemption?` = TRUE for that year, the final tax base is
forced to 0. The pre-exemption base is still reported on
`Yearly_Tax_Summary` so the effect is visible.

### Within-year loss offset

`final_base_before_exemption = max(0, taxable_gains - taxable_losses)`
per year. No carryforward to future years. Time-test exempt lots
neither add gains nor offset losses (they are excluded from the
taxable aggregation entirely — their `Taxable gain CZK` column stays
at 0 by design).

### Deterministic MIN_GAIN / MAX_GAIN

For each SELL, every candidate lot is scored with its
**per-share expected CZK contribution to taxable gain**:

- If the lot would be time-test exempt on this sell, contribution = 0.
- Otherwise:
  `(sell_price_usd − sell_comm_per_share_usd) * fx_sell
   − (buy_price_usd + buy_comm_per_share_usd) * fx_buy`

Lots are sorted ascending for MIN_GAIN, descending for MAX_GAIN. Ties
break by `(buy_date, source_file, source_row)` for deterministic
output. FIFO sorts by `(buy_date, source_file, source_row)` only;
LIFO reverses it.

Because the sort key is computed *at sell time*, anything that is
3-year-old relative to the SELL date gets contribution 0 regardless of
its USD arithmetic. Losses (negative contributions) therefore rank
BEFORE exempt lots in MIN_GAIN, correctly preferring a loss-offset
over "wasting" an exempt lot. This is intentional: a loss used now
reduces taxable gains this year, while an exempt lot would have been
tax-free anyway.

### Corporate actions

`SPLIT` and `REVERSE_SPLIT` both run through `apply_split_to_lots`,
which multiplies `quantity_remaining`/`quantity_original` by
`new_ratio/old_ratio` and divides `price_per_share_usd` accordingly.
Cost basis, commission and buy date are unchanged. Only lots with
`buy_date <= action_date` are adjusted.

`TICKER_CHANGE` is a metadata-only concept in the current build: the
operator should instead map both the old and the new ticker to the
same `Instrument_ID` in `Instrument_Map`. A future extension could
rename open-lot `instrument_id` in place as of the change date.

Cash in lieu is recorded but not auto-converted into a SELL. If a
split produced taxable cash, add a manual SELL on the appropriate
broker CSV (or an extension sheet — currently the input is CSV-only).

### Split detection heuristic

`split_audit` flags any two consecutive same-instrument trades whose
price ratio exceeds ~2.8x (or is below ~0.35x). The operator decides
whether this is:

- A genuine split Yahoo **has not** adjusted for → add to
  `Corporate_Actions`.
- A split Yahoo **has** already adjusted → do nothing; double-
  applying would mis-state cost basis.
- Genuine volatility (biotech news, IPO, etc.) → dismiss.

### Locked years and frozen snapshots

When a year is marked `Locked?` = TRUE and the workbook is regenerated
for the first time after that flip:

1. The simulator runs the year normally (from the last seed / from
   scratch).
2. The post-year state of `lots` is stored in
   `year_end_inventory[year]`.
3. Every MatchLine emitted in that year is written to
   `Frozen_Lot_Matching` (with `Tax year = year`).
4. Open lots (`quantity_remaining > 1e-9`) are written to
   `Frozen_Inventory` (`Snapshot year = year`).

On every subsequent run:

1. The most recent year with both `Locked? = TRUE` and existing
   `Frozen_Inventory` rows becomes the **seed year**.
2. Seed inventory is loaded as the starting `lots` pool.
3. Transactions are filtered to `trade_date.year > seed_year`.
4. Locked-year frozen match lines are injected into the output so
   `Yearly_Tax_Summary` and audit sheets still include them, but they
   are NOT recomputed.

A locked year without a snapshot raises
`locked_year_no_snapshot` ERROR on `Checks`; the operator must
regenerate while the year is still locked to materialise the
snapshot.

### Duplicate detection

Transactions are grouped by
`(broker, account, trade_date, symbol, side, quantity, price)` and
any group with more than one member raises a `duplicate_candidate`
WARN. This is a heuristic — legitimate duplicate trades executed on
the same day at identical price/quantity can trigger it; the operator
should review.

### Sub-share residual on SELLs

Fractional-share brokers (Revolut, Trading212) occasionally round
quantities differently between BUY and SELL rows. A residual below
0.001 shares is logged as WARN `insufficient_lots` instead of ERROR
so real shortfalls (mis-import, missing BUY) stand out.

## File responsibilities

- `build_stock_tax_workbook.py` — single-file generator. All types,
  all rules, all sheet layouts.
- `inspect_csvs.py` — one-off dev utility. Run against a fresh CSV
  drop to sanity-check row counts, date ranges, symbols.
- `verify_workbook.py` — dev utility that re-reads the generated
  `.xlsx` and cross-checks `Yearly_Tax_Summary` against
  `Lot_Matching`, unmatched SELL quantities, and Checks severity.
- `test_locked_year_roundtrip.py` — dev utility. Runs a three-pass
  build that locks 2020, creates a snapshot, perturbs the FX rate,
  and asserts the locked tax value is unchanged. Restores state at
  the end.

## Extension points

### New broker

Drop its Yahoo CSV into `.csv/` and add its path to the `--input`
list. Filename stem becomes the broker label. If naming follows
`Broker_Account.csv`, the underscore separates broker from account.

### New matching method

Add the method name to `SUPPORTED_METHODS`, handle it in
`rank_lots_for_sell`, ensure the ranking is deterministic (tie-break
by `(buy_date, source_file, source_row)`), and it will be picked up
automatically by `Method_Comparison`.

### New check

Append to the `rows` list in `_write_checks`. Severity strings are
`ERROR`, `WARN`, `INFO`; conditional-formatting on column A uses
those exact strings.

### Proper per-instrument-per-year `Apply 100k?`

Currently the 100 000 CZK toggle is per-year, matching the law. If
your tax authority changes the interpretation, update
`build_yearly_summary` where `under_100k` is computed.

### Loss carryforward

Not supported. To add: track unused negative tax base per year, apply
before the `max(0, ...)` floor on subsequent years, surface a
`Loss_Carry` sheet.

## Testing approach

Only integration-level smoke tests live in the repo
(`verify_workbook.py`, `test_locked_year_roundtrip.py`). The
calculation layer is intentionally kept in pure Python dataclasses so
that unit tests against `match_sell`, `rank_lots_for_sell`, and
`simulate` would be straightforward to add later. No unit tests ship
with this initial release.

## Excel-level notes

- **Tables**: Every data sheet is wrapped in an Excel table for
  filtering/sorting. Table names match
  `tbl_<SheetName>` where possible.
- **Data validation**: `Settings.FX method`, `Settings.Apply 100k?`,
  `Settings.Locked?`, `Locked_Years.Locked?`,
  `Corporate_Actions.Action type`, `Corporate_Actions.Applied?`,
  `Method_Selection.Method`.
- **Conditional formatting**: `Checks` sheet colour-codes by
  severity. `Lots` highlights negative remaining quantity in red.
  `Lot_Matching` tints exempt rows green, taxable losses yellow.
  `Method_Comparison` highlights any positive
  `Delta selected vs best` in yellow.
- **Editable cells** are fill-coloured light yellow on every sheet.
- **Freeze panes** on every data sheet above the first data row.
- **Auto filter** on high-volume sheets (`Raw_Yahoo`, `Transactions`,
  `Lots`, `Lot_Matching`, `Checks`).

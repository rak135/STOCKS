# Stock Tax Workbook — Operator Guide (Legacy CLI)

> **Status:** legacy / manual workbook export workflow. The canonical
> product runtime is the FastAPI backend plus React frontend (see
> top-level `README.md`). The repo no longer ships or tracks a root
> `stock_tax_system.xlsx`, and the backend does not require one to run.
> This guide documents the manual `build_stock_tax_workbook.py` CLI for
> operators who still want a workbook export. Pass `--output` to a path
> of your choosing — there is no canonical default file in the repo.

This workbook calculates **Czech personal income tax on stock trades**
from Yahoo Portfolio CSV exports. It is a calculation workbook, **not**
official tax advice. Keep your broker statements separately as proof.

## TL;DR

```bash
py -3 build_stock_tax_workbook.py \
  --input .csv/XTB_CZK.csv .csv/XTB_USD.csv .csv/Lynx.csv \
          .csv/Revolut.csv .csv/Trading212.csv \
  --output exports/stock_tax_export.xlsx
```

Pick any `--output` path you want; the example above uses
`exports/stock_tax_export.xlsx` so it is obviously a generated export
and not a tracked product file. Before rebuilding, close that workbook
in Excel. If Excel locks the file, the build fails instead of creating
an alternate final workbook.

Open the workbook export you just generated. Go through the sheets in order:

1. **README** – on-sheet assumptions.
2. **Operator_Dashboard** – headline tax per year, method comparison,
   validation summary.
3. **Settings** – per-year tax rate, FX method, 100k exemption toggle,
   locked flag.
4. **Import_Log** – per-source-file import statistics.
5. **Raw_Yahoo** – every CSV row preserved verbatim.
6. **Ignored_Rows** – rows skipped because they carry no trade (position
   rows) or have invalid fields.
7. **Transactions** – normalised BUY/SELL rows.
8. **Instrument_Map** – map ticker → stable `Instrument_ID` / ISIN.
9. **FX_Daily** / **FX_Yearly** – Czech National Bank USD/CZK rates.
10. **Corporate_Actions** – manually entered splits, reverse splits,
    ticker changes.
11. **Split_Audit** – heuristic price-jump warnings so you can detect
    missing or double-applied splits.
12. **Method_Selection** – pick FIFO / LIFO / MIN_GAIN / MAX_GAIN per
    `(year, instrument)`.
13. **Locked_Years** – flip `Locked?` = TRUE for years already filed.
14. **Frozen_Inventory** / **Frozen_Lot_Matching** – snapshots kept
    for locked years. Never edited by hand.
15. **Lots** – all lots (open + closed history) as of the last unlocked
    action.
16. **Lot_Matching** – full lot-by-lot matching ledger with FX, cost
    basis, proceeds, holding period and time-test flag.
17. **Yearly_Tax_Summary** – headline per-year figures.
18. **Method_Comparison** – same inputs re-run under all four methods.
19. **Checks** – ERROR / WARN / INFO list, colour-coded.
20. **Audit_Report** – per-file and per-year reconciliation.

Yellow cells are **operator-editable**. Everything else is computed or
raw.

## First-run checklist

1. **FX rates.** Defaults in `FX_Yearly` are marked
   `DEFAULT - verify against CNB`. Replace each year with the official
   CNB annual average (Kurzy devizového trhu – průměr roku). If you
   want daily precision, fill `FX_Daily` and set the year's FX method
  to `FX_DAILY_CNB` in Settings.
2. **Instrument mapping.** Open `Instrument_Map`. Fill ISIN and stable
   `Instrument_ID` for each ticker if you care about ticker-change
   robustness. Default is `Instrument_ID = Yahoo Symbol`.
3. **Corporate actions.** The workbook does not know about splits.
   Enter any splits, reverse splits and ticker changes for years in
   scope on `Corporate_Actions`. Consult `Split_Audit` for hints.
4. **Method.** Default is FIFO per `(year, instrument)`. Review
   `Method_Selection` and change where desired. `Method_Comparison`
   shows the tax impact of each method.
5. **Settings.**
   - `Tax rate` – default 15 % per year.
  - `FX method` – `FX_UNIFIED_GFR` or `FX_DAILY_CNB`.
   - `Apply 100k exemption?` – TRUE enables the 100 000 CZK annual
     gross proceeds exemption (§4(1)(w)/(ze) – if the test applies).
     Default FALSE for conservative reporting.
   - `Locked year?` – TRUE after filing. Locked years are frozen on
     the next regeneration.
6. **Re-run.** Close the export workbook in Excel, then rerun the
  generator targeting the same `--output` path. All computed sheets are
  rebuilt; all editable sheets and frozen snapshots are preserved. If
  the workbook is locked, the run fails loudly and no alternate final
  workbook is created.

## Business rules (summary)

| Rule | Value |
|------|-------|
| Tax currency | CZK |
| Source of FX | Czech National Bank (CNB) only |
| FX method | `FX_DAILY_CNB` or `FX_UNIFIED_GFR` (per year) |
| FX fees | **Ignored** |
| Broker fee | Only the `Commission` column from Yahoo |
| Buy commission | Increases acquisition cost |
| Sell commission | Reduces sale proceeds |
| Date used | `Trade Date` column |
| Matching scope | Global across brokers per `Instrument_ID` |
| Time test | Per matched lot. Lot exempt if `sell_date > buy_date + 3 calendar years` |
| 100 000 CZK exemption | Optional per year (Settings) |
| Loss offset | Within the year only; base floored at 0; no carryforward |
| Tax rate | Parameterised (default 15 %) per year |
| Locked year | Frozen snapshot used, never re-computed |
| Splits | Manual. Adjust lot quantity and per-share price; cost basis unchanged |
| Holding period under split | Unchanged (original buy date retained) |

## Lock-a-year workflow

1. Finish the year's filing using the workbook's current output.
2. Set `Locked?` = TRUE on the **Locked_Years** sheet for that year.
3. Re-run the generator. It will:
   - Snapshot the year-end open-lot inventory into **Frozen_Inventory**.
   - Snapshot every matched lot line for the year into
     **Frozen_Lot_Matching**.
4. Any subsequent re-import (new CSVs, more trades, tweaked FX for
   other years) will:
   - Seed future-year calculations from the latest locked snapshot.
   - Never recompute the locked year.
   - Show an ERROR on **Checks** if a year is marked locked but has
     no frozen snapshot yet (force-rebuild after locking).

To **unlock** a year (e.g. after an audit correction): flip `Locked?`
= FALSE. Remove the corresponding rows from **Frozen_Inventory** and
**Frozen_Lot_Matching** manually if you want a full re-compute.

## Matching methods

All four methods operate on the *global* pool of open lots for a given
`Instrument_ID`, regardless of broker. They differ only in ranking
candidate lots for each SELL.

- **FIFO** – oldest buy date first.
- **LIFO** – newest buy date first.
- **MIN_GAIN** – ranks lots by expected CZK taxable contribution *per
  share* ascending. Time-test exempt lots contribute 0. Loss lots have
  negative contribution, so they rank before exempt, then gain lots.
  Total per year is deterministic.
- **MAX_GAIN** – same ranking reversed. Largest taxable gain per share
  first, exempt/losses last.

`Method_Comparison` re-runs the entire matching for the same inputs
under each method and reports the resulting tax, so the operator can
judge the impact without trusting formulas.

## Traceability

Every number on `Yearly_Tax_Summary` can be traced via:

- `Lot_Matching` – one row per `(Sell_ID, Buy Lot_ID)` pair. Columns
  include source broker, source CSV file and source CSV row for both
  the SELL and the BUY.
- `Transactions` – normalised trade row with source file + source row.
- `Raw_Yahoo` – the untouched CSV row.
- `Ignored_Rows` – rows that did **not** enter the calculation, with
  reason.
- `Audit_Report` – totals per source file and per tax year.

## Known assumptions and limitations

- Every Yahoo trade is treated as USD-denominated. Broker account
  currency (e.g. `XTB_CZK` vs `XTB_USD`) is metadata only.
- The workbook does NOT fetch market data. Only FX tables the operator
  maintains are used.
- The 3-year time test uses *calendar years*. A lot is exempt if the
  SELL date is strictly later than buy date + 3 calendar years, i.e.
  the 4th anniversary or later.
- The 100 000 CZK threshold applies to **gross proceeds from securities
  sales in the year**, before any fees or offsets. The toggle is per
  year on Settings.
- Within-year loss offset: taxable losses reduce taxable gains; base
  floored at 0. There is no carry-forward to future years.
- Splits are entered manually. If Yahoo data for an instrument is
  already adjusted, do not also enter the split — double-adjustment
  mis-states cost basis. Inspect **Split_Audit** for hints.
- Cash in lieu (fractional-share cash payment on a split) is recorded
  on `Corporate_Actions` but NOT automatically turned into a sale.
  Add a manual SELL transaction if the event generated a proceeds
  amount.

## Remaining manual inputs required

The workbook ships with reasonable defaults, but for a defensible
filing you should:

1. Populate **FX_Yearly** with official CNB annual averages for every
   year with trades. Replace the default rows.
2. Populate **FX_Daily** if any year uses `FX_DAILY_CNB`.
3. Review **Instrument_Map** and add ISIN / stable IDs where needed.
4. Enter any **Corporate_Actions** (at minimum splits) relevant to the
   instruments you hold.
5. Set **Method_Selection** deliberately — do not rely on the default
   FIFO without reviewing `Method_Comparison`.
6. Set per-year **Settings** (rate, FX method, 100k toggle).
7. Flip **Locked_Years!Locked?** = TRUE as soon as a year is filed.

from datetime import date

from build_stock_tax_workbook import (
    DEFAULT_TAX_RATE,
    FXResolver,
    Lot,
    Transaction,
    build_yearly_summary,
    match_sell,
    simulate,
)


def _tx(
    tx_id: str,
    d: date,
    side: str,
    qty: float,
    price: float,
    instrument_id: str = "TEST_INST",
) -> Transaction:
    return Transaction(
        tx_id=tx_id,
        source_file="synthetic.csv",
        source_row=1,
        source_broker="TEST",
        source_account="TEST",
        symbol="TEST",
        instrument_id=instrument_id,
        trade_date=d,
        side=side,
        quantity=qty,
        price_usd=price,
        commission_usd=0.0,
        comment="",
    )


def _tax_due_for_year(lines, year: int, settings) -> float:
    summary = build_yearly_summary(lines, settings)
    for row in summary:
        if row["Tax year"] == year:
            return float(row["Tax due CZK"])
    return 0.0


def _run_sim(method: str):
    txs = [
        _tx("B1", date(2021, 1, 2), "BUY", 1.0, 50.0),
        _tx("B2", date(2023, 1, 1), "BUY", 1.0, 10.0),
        _tx("S1", date(2024, 1, 1), "SELL", 1.0, 60.0),
        _tx("S2", date(2024, 1, 3), "SELL", 1.0, 60.0),
    ]
    settings = {
        2024: {
            "tax_rate": DEFAULT_TAX_RATE,
            "fx_method": "FX_UNIFIED_GFR",
            "apply_100k": False,
            "locked": False,
        }
    }
    method_selection = {(2024, "TEST_INST"): method}
    fx = FXResolver({2024: 1.0, 2023: 1.0, 2021: 1.0}, {}, settings)

    _, lines, _, _ = simulate(
        txs=txs,
        settings=settings,
        method_selection=method_selection,
        locked_years={2024: False},
        corporate_actions=[],
        frozen_inventory={},
        frozen_matching={},
        frozen_snapshots={},
        fx=fx,
        override_method=method,
    )
    return txs, lines, settings, fx


def _run_per_sell_greedy_min_gain(txs, fx):
    lots = []
    for tx in txs:
        if tx.side == "BUY":
            lots.append(
                Lot(
                    lot_id=f"L_{tx.tx_id}",
                    tx_id=tx.tx_id,
                    instrument_id=tx.instrument_id,
                    source_broker=tx.source_broker,
                    source_account=tx.source_account,
                    source_file=tx.source_file,
                    source_row=tx.source_row,
                    buy_date=tx.trade_date,
                    quantity_original=tx.quantity,
                    quantity_remaining=tx.quantity,
                    price_per_share_usd=tx.price_usd,
                    buy_commission_total_usd=tx.commission_usd,
                )
            )

    lines = []
    match_counter = {"n": 0}
    for tx in txs:
        if tx.side != "SELL":
            continue
        ll, _ = match_sell(tx, lots, "MIN_GAIN", fx, match_counter)
        lines.extend(ll)
    return lines


def test_min_gain_annual_tax_not_worse_than_fifo_lifo():
    _, min_lines, settings, _ = _run_sim("MIN_GAIN")
    _, fifo_lines, _, _ = _run_sim("FIFO")
    _, lifo_lines, _, _ = _run_sim("LIFO")

    min_tax = _tax_due_for_year(min_lines, 2024, settings)
    fifo_tax = _tax_due_for_year(fifo_lines, 2024, settings)
    lifo_tax = _tax_due_for_year(lifo_lines, 2024, settings)

    assert min_tax <= fifo_tax + 1e-9
    assert min_tax <= lifo_tax + 1e-9


def test_global_min_gain_beats_per_sell_greedy_in_boundary_case():
    txs, min_lines, settings, fx = _run_sim("MIN_GAIN")
    greedy_lines = _run_per_sell_greedy_min_gain(txs, fx)

    min_tax = _tax_due_for_year(min_lines, 2024, settings)
    greedy_tax = _tax_due_for_year(greedy_lines, 2024, settings)

    assert min_tax < greedy_tax


if __name__ == "__main__":
    test_min_gain_annual_tax_not_worse_than_fifo_lifo()
    test_global_min_gain_beats_per_sell_greedy_in_boundary_case()
    print("OK")

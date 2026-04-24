#!/usr/bin/env python3
"""One-off: inspect the 5 input CSVs and print statistics.

Usage:
    py -3 inspect_csvs.py .csv/*.csv
"""
from __future__ import annotations

import csv
import glob
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


def parse_trade_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value or len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def inspect_file(path: Path) -> dict:
    stats = {
        "file": path.name,
        "total_rows": 0,
        "buy": 0,
        "sell": 0,
        "ignored": 0,
        "invalid_dates": 0,
        "invalid_qty": 0,
        "invalid_price": 0,
        "missing_commission": 0,
        "symbols": set(),
        "min_date": None,
        "max_date": None,
        "sample_ignored": [],
    }
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            stats["total_rows"] += 1
            tt = (row.get("Transaction Type") or "").strip().upper()
            td_raw = (row.get("Trade Date") or "").strip()
            if not tt or not td_raw:
                stats["ignored"] += 1
                if len(stats["sample_ignored"]) < 2:
                    stats["sample_ignored"].append({"row": i, "symbol": row.get("Symbol")})
                continue
            td = parse_trade_date(td_raw)
            if td is None:
                stats["invalid_dates"] += 1
                continue
            if stats["min_date"] is None or td < stats["min_date"]:
                stats["min_date"] = td
            if stats["max_date"] is None or td > stats["max_date"]:
                stats["max_date"] = td
            sym = (row.get("Symbol") or "").strip()
            if sym:
                stats["symbols"].add(sym)
            if tt == "BUY":
                stats["buy"] += 1
            elif tt == "SELL":
                stats["sell"] += 1
            else:
                stats["ignored"] += 1
                continue
            try:
                float(row.get("Quantity") or "")
            except ValueError:
                stats["invalid_qty"] += 1
            try:
                float(row.get("Purchase Price") or "")
            except ValueError:
                stats["invalid_price"] += 1
            comm = (row.get("Commission") or "").strip()
            if comm == "":
                stats["missing_commission"] += 1
    return stats


def main() -> int:
    args = sys.argv[1:]
    if not args:
        args = sorted(glob.glob(".csv/*.csv"))
    print(f"Inspecting {len(args)} file(s)")
    grand_syms: set[str] = set()
    totals = Counter()
    for p in args:
        s = inspect_file(Path(p))
        print("-" * 72)
        print(f"File:            {s['file']}")
        print(f"  Total rows:        {s['total_rows']}")
        print(f"  BUY rows:          {s['buy']}")
        print(f"  SELL rows:         {s['sell']}")
        print(f"  Ignored rows:      {s['ignored']}")
        print(f"  Invalid dates:     {s['invalid_dates']}")
        print(f"  Invalid quantity:  {s['invalid_qty']}")
        print(f"  Invalid price:     {s['invalid_price']}")
        print(f"  Missing commission:{s['missing_commission']}")
        print(f"  Min trade date:    {s['min_date']}")
        print(f"  Max trade date:    {s['max_date']}")
        print(f"  Unique symbols:    {sorted(s['symbols'])}")
        print(f"  Sample ignored:    {s['sample_ignored']}")
        grand_syms |= s["symbols"]
        for k in ("total_rows", "buy", "sell", "ignored", "invalid_dates",
                 "invalid_qty", "invalid_price", "missing_commission"):
            totals[k] += s[k]
    print("=" * 72)
    print("GRAND TOTAL")
    for k, v in totals.items():
        print(f"  {k:22s}: {v}")
    print(f"  unique symbols (all files): {len(grand_syms)}")
    print(f"  symbols: {sorted(grand_syms)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

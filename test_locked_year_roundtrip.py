#!/usr/bin/env python3
"""End-to-end check: lock 2020 in the workbook, rebuild, confirm the
frozen snapshot survived and 2020 totals did not re-compute."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

WB = "stock_tax_system.xlsx"
INPUTS = [
    ".csv/XTB_CZK.csv", ".csv/XTB_USD.csv", ".csv/Lynx.csv",
    ".csv/Revolut.csv", ".csv/Trading212.csv",
]


def run_build() -> None:
    cmd = [sys.executable, "build_stock_tax_workbook.py",
           "--input", *INPUTS, "--output", WB]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("BUILD FAILED:\n" + res.stdout + res.stderr)
        sys.exit(1)


def set_cell(path: str, sheet: str, row: int, col: int, value) -> None:
    wb = load_workbook(path)
    wb[sheet].cell(row=row, column=col, value=value)
    wb.save(path)


def read_cell(path: str, sheet: str, row: int, col: int):
    return load_workbook(path)[sheet].cell(row=row, column=col).value


def find_row(path: str, sheet: str, header_row: int, key_col: int, key):
    wb = load_workbook(path)
    ws = wb[sheet]
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if i <= header_row:
            continue
        if row[key_col - 1] == key:
            return i
    return None


def main() -> int:
    # Pass 1: baseline build with clean defaults.
    print("== Pass 1: initial build ==")
    run_build()
    summary_row_2020 = find_row(WB, "Yearly_Tax_Summary", 1, 1, 2020)
    assert summary_row_2020, "2020 not in yearly summary after pass 1"
    tax_2020_pass1 = read_cell(WB, "Yearly_Tax_Summary",
                               summary_row_2020, 13)
    print(f"  Yearly_Tax_Summary 2020 tax = {tax_2020_pass1}")

    # Lock 2020 on Locked_Years sheet (header on row 3, 2020 first data row).
    ly_row = find_row(WB, "Locked_Years", 3, 1, 2020)
    assert ly_row, "Locked_Years 2020 not found"
    set_cell(WB, "Locked_Years", ly_row, 2, True)

    # Pass 2: rebuild with lock flag but CORRECT FX. Snapshot is taken.
    print("\n== Pass 2: rebuild with 2020 locked (FX unchanged) ==")
    run_build()
    tax_2020_pass2 = read_cell(WB, "Yearly_Tax_Summary",
                               summary_row_2020, 13)
    print(f"  Yearly_Tax_Summary 2020 tax after first lock = "
          f"{tax_2020_pass2}")

    fi_years = set()
    fi_ws = load_workbook(WB)["Frozen_Inventory"]
    for r in fi_ws.iter_rows(min_row=4, values_only=True):
        if r[0] is not None:
            fi_years.add(r[0])
    fm_years = set()
    fm_ws = load_workbook(WB)["Frozen_Lot_Matching"]
    for r in fm_ws.iter_rows(min_row=4, values_only=True):
        if r[0] is not None:
            fm_years.add(r[0])
    print(f"  Frozen_Inventory years:       {sorted(fi_years)}")
    print(f"  Frozen_Lot_Matching years:    {sorted(fm_years)}")

    if tax_2020_pass1 != tax_2020_pass2:
        print(f"FAIL: 2020 tax drifted after locking "
              f"({tax_2020_pass1} -> {tax_2020_pass2})")
        return 1
    if 2020 not in fi_years or 2020 not in fm_years:
        print("FAIL: 2020 not fully captured in frozen sheets.")
        return 1

    # Pass 3: perturb FX for 2020 — locked snapshot must ignore the change.
    fx_row = find_row(WB, "FX_Yearly", 3, 1, 2020)
    assert fx_row, "FX_Yearly 2020 not found"
    original_fx = read_cell(WB, "FX_Yearly", fx_row, 2)
    set_cell(WB, "FX_Yearly", fx_row, 2, 30.0)  # deliberate bad rate
    print("\n== Pass 3: perturb 2020 FX to 30.0 and rebuild ==")
    run_build()
    tax_2020_pass3 = read_cell(WB, "Yearly_Tax_Summary",
                               summary_row_2020, 13)
    print(f"  Yearly_Tax_Summary 2020 tax after perturbation = "
          f"{tax_2020_pass3}")

    if tax_2020_pass2 != tax_2020_pass3:
        print(f"FAIL: 2020 tax drifted after FX perturbation "
              f"({tax_2020_pass2} -> {tax_2020_pass3})")
        return 1
    print("PASS: locked 2020 tax withstood FX perturbation.")

    # Cleanup: restore FX and unlock 2020.
    print("\n== Cleanup: restore FX and unlock 2020 ==")
    set_cell(WB, "FX_Yearly", fx_row, 2, original_fx)
    set_cell(WB, "Locked_Years", ly_row, 2, False)
    run_build()
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

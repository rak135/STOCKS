#!/usr/bin/env python3
"""Czech Personal Income Tax Workbook Generator for Stock Trades.

Builds an auditable, operator-usable Excel workbook that calculates Czech
personal income tax on stock trades imported from Yahoo Portfolio CSV
exports. See README_OPERATOR.md for the human-facing guide and
IMPLEMENTATION_NOTES.md for assumptions and internal design.

Usage:
    py -3 build_stock_tax_workbook.py \
        --input .csv/XTB_CZK.csv .csv/XTB_USD.csv .csv/Lynx.csv \
                .csv/Revolut.csv .csv/Trading212.csv \
        --output stock_tax_system.xlsx

If the --output workbook already exists, user-maintained sheets are read
back (Settings, FX_Daily, FX_Yearly, Instrument_Map, Corporate_Actions,
Method_Selection, Locked_Years, Frozen_Inventory, Review_State,
Filed_Year_Reconciliation) so operator edits and locked-year snapshots are
preserved.
"""

from __future__ import annotations

import argparse
import copy
import csv
import dataclasses
import datetime as _dt
import hashlib
import os
import shutil
import sys
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import urllib.request as _urlreq
import json as _json

import openpyxl
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

from stock_tax_app.engine import policy, ui_state
from stock_tax_app.engine import matching as _matching_module
from stock_tax_app.state import project_store


# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------

DEFAULT_TAX_RATE = 0.15
DEFAULT_APPLY_100K = False
DEFAULT_100K_THRESHOLD = 100_000.0  # CZK
DEFAULT_FX_METHOD = "FX_UNIFIED_GFR"
SUPPORTED_FX_METHODS = ("FX_DAILY_CNB", "FX_UNIFIED_GFR")
SUPPORTED_METHODS = policy.SUPPORTED_METHODS
DEFAULT_METHOD = policy.DEFAULT_METHOD

# GFŘ unified yearly USD/CZK rates (Czech tax authority official rates).
# Source: GFŘ pokyn (instruction) D-series, published annually by the Czech
# Financial Administration (Generální finanční ředitelství).
# Use FX_UNIFIED_GFR method — this is the correct legal basis for Czech PIT.
# Earlier years use best-available GFŘ / CNB annual averages.
DEFAULT_FX_YEARLY = {
    2015: 24.60, 2016: 24.44, 2017: 23.38, 2018: 21.78,
    2019: 22.93, 2020: 23.14, 2021: 21.68, 2022: 23.36,
    2023: 22.21,
    2024: 23.28,  # GFŘ-D-65  ← authoritative
    2025: 21.84,  # GFŘ-D-75  ← authoritative
    2026: 22.00,  # placeholder — update when GFŘ publishes D-xx for 2026
}

# Official GFŘ unified USD/CZK rates {year: (rate, source_label)}.
GFR_OFFICIAL_RATES = {
    2023: (22.21, "GFŘ-D-57"),
    2024: (23.28, "GFŘ-D-65"),
    2025: (21.84, "GFŘ-D-75"),
}

# Compatibility aliases derived from stock_tax_app.engine.policy.
YEAR_DEFAULT_METHODS = policy.YEAR_DEFAULT_METHODS
FILED_YEARS = policy.FILED_YEARS
# CNB daily FX cache file (written next to the workbook).
CNB_DAILY_CACHE_FILE = "cnb_daily_cache.json"
CANONICAL_OUTPUT_NAME = "stock_tax_system.xlsx"

TX_SIDES = ("BUY", "SELL")
CA_TYPES = ("SPLIT", "REVERSE_SPLIT", "TICKER_CHANGE")


# -----------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------

@dataclass
class RawRow:
    source_file: str
    source_row: int
    source_broker: str
    source_account: str
    data: Dict[str, str]

    @property
    def symbol(self) -> str:
        return (self.data.get("Symbol") or "").strip()


@dataclass
class Transaction:
    tx_id: str
    source_file: str
    source_row: int
    source_broker: str
    source_account: str
    symbol: str
    instrument_id: str
    trade_date: date
    side: str              # BUY or SELL
    quantity: float
    price_usd: float
    commission_usd: float
    comment: str = ""


@dataclass
class Lot:
    lot_id: str
    tx_id: str
    instrument_id: str
    source_broker: str
    source_account: str
    source_file: str
    source_row: int
    buy_date: date
    quantity_original: float
    quantity_remaining: float
    price_per_share_usd: float
    buy_commission_total_usd: float
    adjustments: List[str] = field(default_factory=list)

    @property
    def buy_commission_per_share_usd(self) -> float:
        if self.quantity_original <= 0:
            return 0.0
        return self.buy_commission_total_usd / self.quantity_original


@dataclass
class MatchLine:
    match_id: str
    sell_tx_id: str
    sell_date: date
    sell_source_broker: str
    sell_source_file: str
    sell_source_row: int
    instrument_id: str
    buy_lot_id: str
    buy_tx_id: str
    buy_date: date
    buy_source_broker: str
    buy_source_file: str
    buy_source_row: int
    quantity: float
    buy_price_per_share_usd: float
    sell_price_per_share_usd: float
    allocated_buy_commission_usd: float
    allocated_sell_commission_usd: float
    fx_rate_buy: float
    fx_rate_sell: float
    cost_basis_czk: float
    proceeds_czk: float
    holding_days: int
    time_test_exempt: bool
    taxable: bool
    taxable_gain_czk: float
    method: str
    tax_year: int


@dataclass
class CalculationResult:
    inputs: List[Path]
    output_path: Path
    raw_rows: List[RawRow]
    txs: List[Transaction]
    ignored: List[Dict[str, Any]]
    problems: List[Dict[str, Any]]
    import_log: List[Dict[str, Any]]
    years: List[int]
    instrument_ids: List[str]
    user_state: Dict[str, Any]
    settings: Dict[int, Dict[str, Any]]
    instrument_map: Dict[str, Dict[str, str]]
    fx_yearly: Dict[int, float]
    fx_daily: Dict[date, float]
    fx_yearly_sources: Dict[int, str]
    fx_yearly_manual: Dict[int, bool]
    fx_daily_sources: Dict[date, str]
    locked_years: Dict[int, bool]
    corporate_actions: List[Dict[str, Any]]
    frozen_inventory: Dict[int, List[Dict[str, Any]]]
    frozen_matching: Dict[int, List[Dict[str, Any]]]
    frozen_snapshots: Dict[int, Dict[str, Any]]
    review_state: Dict[str, Dict[str, Any]]
    filed_reconciliation: Dict[int, Dict[str, Any]]
    method_selection: Dict[Tuple[int, str], str]
    fx: "FXResolver"
    lots_final: List[Lot]
    match_lines: List[MatchLine]
    sim_warnings: List[Dict[str, Any]]
    year_end_inventory: Dict[int, List[Lot]]
    yearly_summary: List[Dict[str, Any]]
    method_comparison: List[Dict[str, Any]]
    split_warnings: List[Dict[str, Any]]
    calculation_blocked: bool = False


# -----------------------------------------------------------------------
# CSV parsing
# -----------------------------------------------------------------------

YAHOO_COLUMNS = [
    "Symbol", "Current Price", "Date", "Time", "Change", "Open", "High",
    "Low", "Volume", "Trade Date", "Purchase Price", "Quantity",
    "Commission", "High Limit", "Low Limit", "Comment", "Transaction Type",
]


def parse_trade_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    if len(value) == 8 and value.isdigit():
        try:
            return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        except ValueError:
            return None
    # Fallback: try common formats
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def safe_float(value: str, default: float = 0.0) -> Tuple[Optional[float], bool]:
    """Return (value, ok). If input is blank, return (default, True)."""
    s = (value or "").strip()
    if s == "":
        return default, True
    try:
        return float(s), True
    except ValueError:
        return None, False


def broker_from_filename(path: Path) -> Tuple[str, str]:
    stem = path.stem
    if "_" in stem:
        broker, _, account = stem.partition("_")
        return broker, account
    return stem, ""


def read_csv_file(path: Path) -> Tuple[List[RawRow], List[Dict[str, Any]]]:
    raw_rows: List[RawRow] = []
    problems: List[Dict[str, Any]] = []
    if not path.exists():
        problems.append({
            "source_file": path.name, "source_row": 0,
            "reason": "FILE_NOT_FOUND", "symbol": "", "trade_date": "",
            "transaction_type": "", "detail": str(path),
        })
        return raw_rows, problems
    broker, account = broker_from_filename(path)
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for idx, row in enumerate(reader, start=2):  # data starts at line 2
            cleaned = {k: (v or "").strip() for k, v in (row or {}).items() if k}
            raw_rows.append(RawRow(
                source_file=path.name, source_row=idx,
                source_broker=broker, source_account=account,
                data=cleaned,
            ))
    return raw_rows, problems


def normalize_transactions(
    raw_rows: List[RawRow],
) -> Tuple[List[Transaction], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split raw rows into (transactions, ignored, validation_issues)."""
    txs: List[Transaction] = []
    ignored: List[Dict[str, Any]] = []
    problems: List[Dict[str, Any]] = []

    for raw in raw_rows:
        data = raw.data
        tt = (data.get("Transaction Type") or "").strip().upper()
        td_raw = (data.get("Trade Date") or "").strip()

        if not tt and not td_raw:
            ignored.append({
                "source_file": raw.source_file, "source_row": raw.source_row,
                "symbol": raw.symbol, "reason": "position_row_no_trade",
                "detail": "empty Trade Date and empty Transaction Type",
            })
            continue
        if not tt or not td_raw:
            ignored.append({
                "source_file": raw.source_file, "source_row": raw.source_row,
                "symbol": raw.symbol,
                "reason": "incomplete_transaction",
                "detail": f"trade_date='{td_raw}' tx_type='{tt}'",
            })
            continue

        trade_date = parse_trade_date(td_raw)
        if trade_date is None:
            problems.append({
                "source_file": raw.source_file, "source_row": raw.source_row,
                "check": "invalid_date", "severity": "ERROR",
                "detail": f"Trade Date '{td_raw}' is not parseable",
            })
            ignored.append({
                "source_file": raw.source_file, "source_row": raw.source_row,
                "symbol": raw.symbol, "reason": "invalid_date",
                "detail": f"Trade Date '{td_raw}'",
            })
            continue

        if tt not in TX_SIDES:
            problems.append({
                "source_file": raw.source_file, "source_row": raw.source_row,
                "check": "invalid_transaction_type", "severity": "ERROR",
                "detail": f"Transaction Type '{tt}' not in BUY/SELL",
            })
            ignored.append({
                "source_file": raw.source_file, "source_row": raw.source_row,
                "symbol": raw.symbol, "reason": "invalid_tx_type",
                "detail": f"Transaction Type '{tt}'",
            })
            continue

        qty_val, qty_ok = safe_float(data.get("Quantity") or "", default=None)
        if not qty_ok or qty_val is None or qty_val <= 0:
            problems.append({
                "source_file": raw.source_file, "source_row": raw.source_row,
                "check": "invalid_quantity", "severity": "ERROR",
                "detail": f"Quantity '{data.get('Quantity')}'",
            })
            ignored.append({
                "source_file": raw.source_file, "source_row": raw.source_row,
                "symbol": raw.symbol, "reason": "invalid_qty",
                "detail": data.get("Quantity") or "",
            })
            continue

        price_val, price_ok = safe_float(data.get("Purchase Price") or "",
                                         default=None)
        if not price_ok or price_val is None or price_val < 0:
            problems.append({
                "source_file": raw.source_file, "source_row": raw.source_row,
                "check": "invalid_price", "severity": "ERROR",
                "detail": f"Purchase Price '{data.get('Purchase Price')}'",
            })
            ignored.append({
                "source_file": raw.source_file, "source_row": raw.source_row,
                "symbol": raw.symbol, "reason": "invalid_price",
                "detail": data.get("Purchase Price") or "",
            })
            continue

        commission_val, _ = safe_float(data.get("Commission") or "", default=0.0)
        if commission_val is None:
            commission_val = 0.0

        tx = Transaction(
            tx_id=f"{raw.source_file}#{raw.source_row}",
            source_file=raw.source_file,
            source_row=raw.source_row,
            source_broker=raw.source_broker,
            source_account=raw.source_account,
            symbol=raw.symbol,
            instrument_id=raw.symbol,  # default; user may override via Instrument_Map
            trade_date=trade_date,
            side=tt,
            quantity=qty_val,
            price_usd=price_val,
            commission_usd=commission_val,
            comment=(data.get("Comment") or ""),
        )
        txs.append(tx)

    # Duplicate detection — same broker/date/symbol/side/qty/price.
    seen = defaultdict(list)
    for tx in txs:
        key = (tx.source_broker, tx.source_account, tx.trade_date,
               tx.symbol, tx.side, round(tx.quantity, 6),
               round(tx.price_usd, 6))
        seen[key].append(tx)
    for key, group in seen.items():
        if len(group) > 1:
            for t in group:
                problems.append({
                    "source_file": t.source_file, "source_row": t.source_row,
                    "check": "duplicate_candidate", "severity": "WARN",
                    "detail": (f"{len(group)} identical trades "
                               f"for {t.symbol} on {t.trade_date}"),
                })
    return txs, ignored, problems


# -----------------------------------------------------------------------
# Persistence of user-editable sheets
# -----------------------------------------------------------------------

def _read_table(ws, header_row: int = 1) -> List[Dict[str, Any]]:
    """Read a worksheet table into a list of dicts.

    ``header_row`` is the 1-indexed row containing column headers.
    """
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < header_row:
        return []
    header = rows[header_row - 1]
    out: List[Dict[str, Any]] = []
    for r in rows[header_row:]:
        if r is None:
            continue
        if all(v is None or (isinstance(v, str) and v.strip() == "")
               for v in r):
            continue
        out.append({str(header[i]): r[i] for i in range(len(header))
                    if header[i] is not None})
    return out


# Header-row offsets for sheets load_existing_user_state reads back.
USER_SHEET_HEADER_ROWS = {
    "Settings": 1,
    "Instrument_Map": 1,
    "FX_Daily": 3,
    "FX_Yearly": 3,
    "Corporate_Actions": 3,
    "Method_Selection": 3,
    "Locked_Years": 3,
    "Frozen_Inventory": 3,
    "Frozen_Lot_Matching": 3,
    "Frozen_Snapshots": 3,
    "Review_State": 1,
    "Filed_Year_Reconciliation": 1,
}


def load_existing_user_state(path: Path) -> Dict[str, Any]:
    """Return dict of user-maintained sheet data if workbook exists."""
    state: Dict[str, Any] = {}
    if not path.exists():
        return state
    try:
        wb = load_workbook(path, data_only=False)
    except Exception as exc:  # pragma: no cover
        print(f"WARN: could not read existing workbook {path}: {exc}",
              file=sys.stderr)
        return state
    for sheet, hrow in USER_SHEET_HEADER_ROWS.items():
        if sheet in wb.sheetnames:
            state[sheet] = _read_table(wb[sheet], header_row=hrow)
    return state


# -----------------------------------------------------------------------
# Settings
# -----------------------------------------------------------------------

def build_settings(
    user_state: Dict[str, Any], years: List[int],
) -> Dict[int, Dict[str, Any]]:
    existing: Dict[int, Dict[str, Any]] = {}
    for row in user_state.get("Settings", []):
        try:
            y = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        existing[y] = row
    out: Dict[int, Dict[str, Any]] = {}
    for y in years:
        src = existing.get(y, {})
        out[y] = {
            "tax_rate": _to_float(src.get("Tax rate"), DEFAULT_TAX_RATE),
            "fx_method": str(src.get("FX method") or DEFAULT_FX_METHOD).upper(),
            "method": policy.resolved_method_for(y, src.get("Method")),
            "apply_100k": _to_bool(src.get("Apply 100k exemption?"),
                                   DEFAULT_APPLY_100K),
            "locked": _to_bool(src.get("Locked year?"), False),
            "notes": src.get("Notes") or "",
        }
        if out[y]["fx_method"] not in SUPPORTED_FX_METHODS:
            out[y]["fx_method"] = DEFAULT_FX_METHOD
        if policy.is_locked(y):
            out[y]["locked"] = True
    return out


def _to_float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any) -> Optional[float]:
    """Return float if parseable, else None. Used where None signals 'not present'."""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ("true", "1", "yes", "y", "ano"):
        return True
    if s in ("false", "0", "no", "n", "ne"):
        return False
    return default


def build_fx_tables(user_state: Dict[str, Any], years: List[int]
                    ) -> Tuple[Dict[int, float], Dict[date, float], Dict[int, str], Dict[int, bool], Dict[date, str]]:
    """Return (yearly_rates, daily_rates, yearly_sources, yearly_manual, daily_sources).

    yearly_sources maps year → source label (e.g. "GFŘ-D-65" or "manual" or "default").
    """
    yearly: Dict[int, float] = {}
    yearly_src: Dict[int, str] = {}
    yearly_manual: Dict[int, bool] = {}
    for row in user_state.get("FX_Yearly", []):
        try:
            y = int(row.get("Tax year"))
            r = float(row.get("USD_CZK"))
        except (TypeError, ValueError):
            continue
        yearly[y] = r
        src_note = (row.get("Source / note") or "").strip()
        yearly_src[y] = src_note if src_note else "manual"
        if row.get("__manual__") is None:
            yearly_manual[y] = not src_note or "manual" in src_note.lower()
        else:
            yearly_manual[y] = _to_bool(row.get("__manual__"), False)
    for y in years:
        if y not in yearly:
            if y in GFR_OFFICIAL_RATES:
                official_r, official_label = GFR_OFFICIAL_RATES[y]
                yearly[y] = official_r
                yearly_src[y] = official_label
                yearly_manual[y] = False
            elif y in DEFAULT_FX_YEARLY:
                yearly[y] = DEFAULT_FX_YEARLY[y]
                yearly_src[y] = "default"
                yearly_manual[y] = False

    daily: Dict[date, float] = {}
    daily_src: Dict[date, str] = {}
    for row in user_state.get("FX_Daily", []):
        d = row.get("Date")
        rate = row.get("USD_CZK")
        if isinstance(d, datetime):
            d = d.date()
        elif isinstance(d, str):
            d = parse_trade_date(d)
        if not isinstance(d, date) or rate is None:
            continue
        try:
            daily[d] = float(rate)
            daily_src[d] = str(row.get("Source / note") or "").strip()
        except (TypeError, ValueError):
            continue
    return yearly, daily, yearly_src, yearly_manual, daily_src


def build_instrument_map(user_state: Dict[str, Any],
                         txs: List[Transaction]) -> Dict[str, Dict[str, str]]:
    mp: Dict[str, Dict[str, str]] = {}
    for row in user_state.get("Instrument_Map", []):
        sym = (row.get("Yahoo Symbol") or "").strip()
        if not sym:
            continue
        mp[sym] = {
            "Yahoo Symbol": sym,
            "Instrument_ID": (row.get("Instrument_ID") or sym) or sym,
            "ISIN": row.get("ISIN") or "",
            "Instrument name": row.get("Instrument name") or "",
            "Notes": row.get("Notes") or "",
        }
    for tx in txs:
        if tx.symbol not in mp:
            mp[tx.symbol] = {
                "Yahoo Symbol": tx.symbol,
                "Instrument_ID": tx.symbol,
                "ISIN": "",
                "Instrument name": "",
                "Notes": "",
            }
    return mp


def apply_instrument_map(txs: List[Transaction],
                         mp: Dict[str, Dict[str, str]]) -> None:
    for tx in txs:
        info = mp.get(tx.symbol)
        if info and info.get("Instrument_ID"):
            tx.instrument_id = info["Instrument_ID"]
        else:
            tx.instrument_id = tx.symbol


def build_method_selection(user_state: Dict[str, Any],
                           years: List[int],
                           instrument_ids: Iterable[str]
                           ) -> Dict[Tuple[int, str], str]:
    sel: Dict[Tuple[int, str], str] = {}
    year_defaults: Dict[int, str] = {}
    for row in user_state.get("Settings", []):
        try:
            y = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        year_defaults[y] = policy.resolved_method_for(y, row.get("Method"))
    for row in user_state.get("Method_Selection", []):
        try:
            y = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        inst = (row.get("Instrument_ID") or "").strip()
        method = policy.resolved_method_for(y, row.get("Method"))
        sel[(y, inst)] = method
    for y in years:
        year_default = year_defaults.get(y, policy.resolved_method_for(y))
        for inst in instrument_ids:
            sel.setdefault((y, inst), year_default)
    return sel


def build_locked_years(user_state: Dict[str, Any],
                       years: List[int]) -> Dict[int, bool]:
    out: Dict[int, bool] = {}
    for row in user_state.get("Locked_Years", []):
        try:
            y = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        out[y] = _to_bool(row.get("Locked?"), False)
    for y in years:
        out.setdefault(y, policy.is_locked(y))
    return out


def _is_blank_corporate_action_row(row: Dict[str, Any]) -> bool:
    keys = (
        "Date",
        "effective_date",
        "Instrument_ID",
        "instrument_id",
        "Action type",
        "action_type",
        "Action ID",
        "action_id",
        "Notes",
        "note",
        "Ratio old",
        "ratio_denominator",
        "Ratio new",
        "ratio_numerator",
    )
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return False
    return True


def _corporate_action_issue(
    *,
    category: str,
    detail: str,
    severity: str,
    row_index: int,
) -> Dict[str, Any]:
    return {
        "check": category,
        "detail": detail,
        "severity": severity,
        "source_file": "Corporate_Actions",
        "source_row": row_index,
    }


def _parse_target_from_note(note: str) -> str:
    marker = "target="
    lower = note.lower()
    idx = lower.find(marker)
    if idx == -1:
        return ""
    tail = note[idx + len(marker):].strip()
    if not tail:
        return ""
    return tail.split()[0].strip()


def build_corporate_actions(
    user_state: Dict[str, Any],
    *,
    known_instrument_ids: Optional[set[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    out: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for idx, row in enumerate(user_state.get("Corporate_Actions", []), start=4):
        if not isinstance(row, dict) or _is_blank_corporate_action_row(row):
            continue

        action_id = str(row.get("Action ID") or row.get("action_id") or "").strip()
        action_type = str(row.get("Action type") or row.get("action_type") or "").strip().upper()

        raw_date = row.get("Date")
        if raw_date is None:
            raw_date = row.get("effective_date")
        parsed_date: Optional[date] = None
        if isinstance(raw_date, datetime):
            parsed_date = raw_date.date()
        elif isinstance(raw_date, date):
            parsed_date = raw_date
        elif isinstance(raw_date, str):
            parsed_date = parse_trade_date(raw_date)

        inst = str(
            row.get("Instrument_ID")
            or row.get("instrument_id")
            or row.get("source_symbol")
            or ""
        ).strip()
        target_inst = str(
            row.get("Target Instrument_ID")
            or row.get("target_instrument_id")
            or row.get("target_symbol")
            or row.get("Target symbol")
            or ""
        ).strip()

        note = str(row.get("Notes") or row.get("note") or "").strip()
        source = str(row.get("Source") or row.get("source") or "").strip()
        if not target_inst and action_type == "TICKER_CHANGE":
            target_inst = _parse_target_from_note(note)

        ratio_old = _coerce_float(row.get("Ratio old"))
        if ratio_old is None:
            ratio_old = _coerce_float(row.get("ratio_denominator"))
        ratio_new = _coerce_float(row.get("Ratio new"))
        if ratio_new is None:
            ratio_new = _coerce_float(row.get("ratio_numerator"))
        if ratio_old is None:
            ratio_old = 1.0
        if ratio_new is None:
            ratio_new = 1.0

        enabled = _to_bool(row.get("Applied?") if "Applied?" in row else row.get("enabled"), True)
        cash_in_lieu = _to_float(row.get("Cash in lieu"), 0.0)

        if action_id:
            if action_id in seen_ids:
                issues.append(
                    _corporate_action_issue(
                        category="corporate_action_duplicate_action_id",
                        detail=f"Duplicate action_id '{action_id}' in Corporate_Actions.",
                        severity="ERROR",
                        row_index=idx,
                    )
                )
                continue
            seen_ids.add(action_id)

        if action_type not in CA_TYPES:
            issues.append(
                _corporate_action_issue(
                    category="corporate_action_unknown_action_type",
                    detail=f"Unknown action_type '{action_type or '<blank>'}'.",
                    severity="ERROR",
                    row_index=idx,
                )
            )
            continue

        if parsed_date is None:
            issues.append(
                _corporate_action_issue(
                    category="corporate_action_invalid_date",
                    detail="Corporate action has an invalid or missing effective date.",
                    severity="ERROR",
                    row_index=idx,
                )
            )
            continue

        if not inst:
            issues.append(
                _corporate_action_issue(
                    category="corporate_action_missing_instrument",
                    detail="Corporate action is missing Instrument_ID/source symbol.",
                    severity="ERROR",
                    row_index=idx,
                )
            )
            continue

        if action_type in ("SPLIT", "REVERSE_SPLIT"):
            if ratio_old <= 0 or ratio_new <= 0:
                issues.append(
                    _corporate_action_issue(
                        category="corporate_action_invalid_ratio",
                        detail=(
                            "Split ratio must be positive and non-zero "
                            f"(got old={ratio_old}, new={ratio_new})."
                        ),
                        severity="ERROR",
                        row_index=idx,
                    )
                )
                continue
        if action_type == "TICKER_CHANGE" and not target_inst:
            issues.append(
                _corporate_action_issue(
                    category="corporate_action_missing_target",
                    detail="Ticker change is missing target instrument/symbol.",
                    severity="ERROR",
                    row_index=idx,
                )
            )
            continue

        if enabled and known_instrument_ids and inst not in known_instrument_ids:
            issues.append(
                _corporate_action_issue(
                    category="corporate_action_ambiguous_mapping",
                    detail=(
                        f"Corporate action instrument '{inst}' does not match known instrument IDs "
                        "from transaction data."
                    ),
                    severity="WARN",
                    row_index=idx,
                )
            )

        out.append(
            {
                "Action_ID": action_id,
                "Date": parsed_date,
                "Instrument_ID": inst,
                "Action type": action_type,
                "Ratio old": ratio_old,
                "Ratio new": ratio_new,
                "Cash in lieu": cash_in_lieu,
                "Notes": note,
                "Applied": enabled,
                "Target Instrument_ID": target_inst,
                "Source": source,
            }
        )

    out.sort(key=lambda r: (r["Date"], r["Instrument_ID"], r.get("Action_ID") or ""))
    return out, issues


def load_frozen_inventory(user_state: Dict[str, Any]
                          ) -> Dict[int, List[Dict[str, Any]]]:
    """Return {year: [frozen lot records]}."""
    out: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in user_state.get("Frozen_Inventory", []):
        try:
            y = int(row.get("Snapshot year"))
        except (TypeError, ValueError):
            continue
        out[y].append(row)
    return dict(out)


def load_frozen_matching(user_state: Dict[str, Any]
                         ) -> Dict[int, List[Dict[str, Any]]]:
    out: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in user_state.get("Frozen_Lot_Matching", []):
        try:
            y = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        out[y].append(row)
    return dict(out)


def load_frozen_snapshots(user_state: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for row in user_state.get("Frozen_Snapshots", []):
        try:
            y = int(row.get("Snapshot year"))
        except (TypeError, ValueError):
            continue
        out[y] = dict(row)
    return out


def load_review_state(user_state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return {sell_tx_id: {review_status, operator_note}} from Review_State."""
    out: Dict[str, Dict[str, Any]] = {}
    for row in user_state.get("Review_State", []):
        sid = str(row.get("Sell_ID") or "").strip()
        if not sid:
            continue
        out[sid] = {
            "review_status": row.get("Review status") or "",
            "operator_note": row.get("Operator note") or "",
        }
    return out


def load_filed_reconciliation(user_state: Dict[str, Any]
                              ) -> Dict[int, Dict[str, Any]]:
    """Return {year: {filed_method, filed_tax_base, filed_tax_due}} from Filed_Year_Reconciliation."""
    out: Dict[int, Dict[str, Any]] = {}
    for row in user_state.get("Filed_Year_Reconciliation", []):
        try:
            y = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        expected_method = str(
            row.get("Filed method")
            or row.get("Expected filed method")
            or ""
        ).strip().upper()
        filed_method = policy.filed_method(y)
        if filed_method and expected_method and expected_method != filed_method:
            # Ignore stale filed-year reconciliation rows from the earlier
            # 2024 FIFO policy; the generator now treats 2024 as filed LIFO.
            continue
        out[y] = {
            "filed_method": expected_method,
            "filed_tax_base": row.get("Filed tax base CZK"),
            "filed_tax_due": row.get("Filed tax due CZK"),
        }
    return out


# -----------------------------------------------------------------------
# FX download (best-effort, requires network)
# -----------------------------------------------------------------------

def _cnb_cache_path(workbook_path: Path) -> Path:
    return workbook_path.parent / CNB_DAILY_CACHE_FILE


def _load_cnb_cache(cache_path: Path) -> Dict[str, float]:
    """Load {date_iso: rate} from JSON cache file."""
    if not cache_path.exists():
        return {}
    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            return _json.load(fh)
    except Exception:
        return {}


def _save_cnb_cache(cache_path: Path, data: Dict[str, float]) -> None:
    try:
        with cache_path.open("w", encoding="utf-8") as fh:
            _json.dump(data, fh, indent=2)
    except Exception:
        pass


def download_cnb_daily_rates_year(year: int, timeout: int = 15
                                  ) -> Dict[date, float]:
    """Download CNB daily USD/CZK rates for *year* from cnb.cz.

    Returns {date: rate}. Empty dict on network failure.
    """
    url = (
        "https://www.cnb.cz/en/financial_markets/"
        "foreign_exchange_market/exchange_rate_fixing/"
        f"year.txt?year={year}"
    )
    try:
        req = _urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with _urlreq.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return {}
    out: Dict[date, float] = {}
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 5:
            continue
        # First column is date; find USD in code column (4th or 5th)
        try:
            d = datetime.strptime(parts[0], "%d.%m.%Y").date()
        except ValueError:
            continue
        for ci in (4, 3):
            if ci < len(parts) and parts[ci].upper() == "USD":
                ri = ci + 1
                if ri < len(parts):
                    try:
                        rate = float(parts[ri].replace(",", "."))
                        out[d] = rate
                    except ValueError:
                        pass
                break
    return out


def refresh_fx_daily_for_years(
    fx_daily: Dict[date, float],
    fx_daily_sources: Dict[date, str],
    years_needing_daily: List[int],
    cache_path: Path,
) -> Tuple[Dict[date, float], Dict[date, str], List[str]]:
    """Download missing CNB daily rates for given years.

    Returns (updated_rates, updated_sources, list_of_info_messages).
    """
    msgs: List[str] = []
    cache_raw = _load_cnb_cache(cache_path)
    # Seed fx_daily from cache
    updated = dict(fx_daily)
    updated_sources = dict(fx_daily_sources)
    for iso, rate in cache_raw.items():
        try:
            d = date.fromisoformat(iso)
            updated.setdefault(d, rate)
            updated_sources.setdefault(d, "CNB cache")
        except ValueError:
            continue

    for y in sorted(set(years_needing_daily)):
        if any(d.year == y for d in updated):
            msgs.append(f"FX_DAILY_CNB year {y}: using cached/manual rates.")
            continue
        msgs.append(f"FX_DAILY_CNB year {y}: downloading from CNB …")
        downloaded = download_cnb_daily_rates_year(y)
        if downloaded:
            updated.update(downloaded)
            for d in downloaded:
                updated_sources[d] = "CNB download"
            msgs.append(f"  → {len(downloaded)} dates downloaded for {y}.")
            # Persist to cache
            new_raw = dict(cache_raw)
            for d, r in downloaded.items():
                new_raw[d.isoformat()] = r
            _save_cnb_cache(cache_path, new_raw)
        else:
            msgs.append(f"  → Download failed for {y} — add rates manually to FX_Daily.")
    return updated, updated_sources, msgs


# -----------------------------------------------------------------------
# FX lookup
# -----------------------------------------------------------------------

class FXResolver:
    def __init__(self, yearly: Dict[int, float], daily: Dict[date, float],
                 settings: Dict[int, Dict[str, Any]]):
        self.yearly = yearly
        self.daily = daily
        self.settings = settings
        self.missing_daily: List[date] = []
        self.missing_yearly: List[int] = []

    def _lookup_daily_rate(self, d: date) -> Tuple[float | None, str]:
        if d in self.daily:
            return self.daily[d], "FX_DAILY_CNB_exact"
        for back in range(1, 11):
            alt = d - timedelta(days=back)
            if alt in self.daily:
                return self.daily[alt], f"FX_DAILY_CNB_back{back}d"
        return None, "FX_DAILY_CNB_missing"

    def inspect_date(self, d: date) -> Tuple[float | None, str]:
        y = d.year
        method = self.settings.get(y, {}).get("fx_method", DEFAULT_FX_METHOD)
        if method == "FX_DAILY_CNB":
            return self._lookup_daily_rate(d)
        if y in self.yearly:
            return self.yearly[y], "FX_UNIFIED_GFR"
        return None, "FX_UNIFIED_GFR_missing"

    def rate_for(self, d: date) -> Tuple[float, str]:
        rate, label = self.inspect_date(d)
        if rate is not None:
            return rate, label
        y = d.year
        method = self.settings.get(y, {}).get("fx_method", DEFAULT_FX_METHOD)
        if method == "FX_DAILY_CNB":
            self.missing_daily.append(d)
            raise ValueError(
                "Missing FX_DAILY_CNB rate for "
                f"{d.isoformat()} and no earlier rate within 10 days."
            )
        self.missing_yearly.append(y)
        raise ValueError(
            f"Missing {method} yearly FX rate for tax year {y}."
        )


def collect_required_fx_problems(
    txs: List[Transaction],
    settings: Dict[int, Dict[str, Any]],
    fx: FXResolver,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    missing_daily_by_year: Dict[int, set[date]] = defaultdict(set)
    missing_yearly_by_year: Dict[int, str] = {}
    for tx in txs:
        y = tx.trade_date.year
        method = str(settings.get(y, {}).get("fx_method") or DEFAULT_FX_METHOD)
        rate, _label = fx.inspect_date(tx.trade_date)
        if rate is not None:
            continue
        if method == "FX_DAILY_CNB":
            missing_daily_by_year[y].add(tx.trade_date)
        else:
            missing_yearly_by_year[y] = method

    for y in sorted(missing_yearly_by_year):
        rows.append({
            "severity": "ERROR",
            "check": "missing_fx_yearly",
            "detail": (
                f"{missing_yearly_by_year[y]} has no yearly FX rate for tax year {y}."
            ),
            "source_file": "",
            "source_row": "",
        })

    for y in sorted(missing_daily_by_year):
        missing = sorted(missing_daily_by_year[y])
        preview = ", ".join(d.isoformat() for d in missing[:3])
        if len(missing) > 3:
            preview += ", ..."
        rows.append({
            "severity": "ERROR",
            "check": "missing_fx_daily",
            "detail": (
                f"{len(missing)} transaction date(s) in {y} lack FX_DAILY_CNB "
                f"coverage within the 10-day lookback window: {preview}"
            ),
            "source_file": "",
            "source_row": "",
        })

    if rows:
        rows.append({
            "severity": "ERROR",
            "check": "fx_calculation_blocked",
            "detail": (
                "Trusted calculation is blocked until required FX rates are available. "
                "No silent yearly or 22.0 fallback was used."
            ),
            "source_file": "",
            "source_row": "",
        })
    return rows


# -----------------------------------------------------------------------
# Corporate actions application
# -----------------------------------------------------------------------

def apply_corporate_action_to_lots(lots: List[Lot], action: Dict[str, Any]) -> None:
    """Apply a supported corporate action to open lots in place."""
    inst = action["Instrument_ID"]
    action_date = action["Date"]
    action_type = str(action.get("Action type") or "").strip().upper()

    if action_type == "TICKER_CHANGE":
        target_inst = str(action.get("Target Instrument_ID") or "").strip()
        if not target_inst:
            return
        for lot in lots:
            if lot.instrument_id != inst:
                continue
            if lot.buy_date > action_date:
                continue
            if lot.quantity_remaining <= 0:
                continue
            lot.instrument_id = target_inst
            lot.adjustments.append(f"TICKER_CHANGE {inst}->{target_inst} on {action_date}")
        return

    ratio_old = action["Ratio old"]
    ratio_new = action["Ratio new"]
    if ratio_old <= 0 or ratio_new <= 0:
        return

    # e.g. 2-for-1 split: ratio_old=1, ratio_new=2 -> factor=2
    factor = ratio_new / ratio_old
    if factor == 1.0:
        return
    for lot in lots:
        if lot.instrument_id != inst:
            continue
        if lot.buy_date > action_date:
            continue
        if lot.quantity_remaining <= 0:
            continue
        lot.quantity_remaining *= factor
        lot.quantity_original *= factor
        lot.price_per_share_usd /= factor
        lot.adjustments.append(
            f"{action_type} {ratio_old}:{ratio_new} on {action_date}")


# -----------------------------------------------------------------------
# Lot matching core
# -----------------------------------------------------------------------

def _expected_contribution_per_share_czk(
    lot, sell, sell_commission_per_share_usd, fx,
):
    return _matching_module._expected_contribution_per_share_czk(
        lot, sell, sell_commission_per_share_usd, fx)


def _add_years(d, years):
    return _matching_module._add_years(d, years)


def rank_lots_for_sell(lots, sell, method, fx):
    return _matching_module.rank_lots_for_sell(lots, sell, method, fx)


def _make_match_line(sell, lot, take, fx, match_counter, method):
    return _matching_module._make_match_line(
        sell, lot, take, fx, match_counter, method,
        match_line_factory=MatchLine)


def _match_global_optimized(sells, lots, method, fx, match_counter):
    return _matching_module._match_global_optimized(
        sells, lots, method, fx, match_counter,
        match_line_factory=MatchLine)


def match_sell(sell, lots, method, fx, match_counter):
    return _matching_module.match_sell(
        sell, lots, method, fx, match_counter,
        match_line_factory=MatchLine)


def _lots_from_frozen(inventory_rows):
    return _matching_module._lots_from_frozen(
        inventory_rows,
        lot_factory=Lot,
        parse_trade_date=parse_trade_date)


def simulate(
    txs, settings, method_selection, locked_years, corporate_actions,
    frozen_inventory, frozen_matching, frozen_snapshots, fx,
    override_method=None,
):
    """Run full lot-matching over transactions.

    Returns (final lots, match lines, warnings, per-year end inventories).
    """
    return _matching_module.simulate(
        txs, settings, method_selection, locked_years, corporate_actions,
        frozen_inventory, frozen_matching, frozen_snapshots, fx,
        override_method,
        lot_factory=Lot,
        match_line_factory=MatchLine,
        default_method=DEFAULT_METHOD,
        to_bool=_to_bool,
        parse_trade_date=parse_trade_date,
    )


def _clone_lots(lots):
    return _matching_module._clone_lots(lots)


def _coerce_date(v):
    return _matching_module._coerce_date(v, parse_trade_date)

def build_yearly_summary(
    match_lines, settings,
):
    from stock_tax_app.engine.tax_summary import (
        build_yearly_summary as _build_yearly_summary,
    )
    return _build_yearly_summary(
        match_lines, settings,
        default_tax_rate=DEFAULT_TAX_RATE,
        default_apply_100k=DEFAULT_APPLY_100K,
        default_100k_threshold=DEFAULT_100K_THRESHOLD,
        default_fx_method=DEFAULT_FX_METHOD,
    )


# -----------------------------------------------------------------------
# Method comparison
# -----------------------------------------------------------------------

def run_method_comparison(
    txs, settings, method_selection, locked_years, corporate_actions,
    frozen_inventory, frozen_matching, frozen_snapshots, fx,
):
    from stock_tax_app.engine.tax_summary import (
        run_method_comparison as _run_method_comparison,
    )
    return _run_method_comparison(
        txs, settings, method_selection, locked_years, corporate_actions,
        frozen_inventory, frozen_matching, frozen_snapshots, fx,
        lot_factory=Lot,
        match_line_factory=MatchLine,
        default_method=DEFAULT_METHOD,
        to_bool=_to_bool,
        parse_trade_date=parse_trade_date,
        supported_methods=SUPPORTED_METHODS,
    )


# -----------------------------------------------------------------------
# Split-adjust audit heuristic
# -----------------------------------------------------------------------

def split_audit(txs):
    from stock_tax_app.engine.tax_summary import split_audit as _split_audit
    return _split_audit(txs)


def extract_position_rows_with_provenance(raw_rows, instrument_map):
    from stock_tax_app.engine.open_positions import (
        extract_position_rows_with_provenance as _extract_with_provenance,
    )

    return _extract_with_provenance(
        raw_rows,
        instrument_map,
        safe_float=safe_float,
        parse_trade_date=parse_trade_date,
    )


def extract_position_rows(raw_rows, instrument_map):
    from stock_tax_app.engine.open_positions import extract_position_rows as _extract_rows

    return _extract_rows(
        raw_rows,
        instrument_map,
        safe_float=safe_float,
        parse_trade_date=parse_trade_date,
    )

def build_open_position_rows(
    raw_rows, instrument_map, lots, *,
    ok_tolerance: float = 1e-4,
    warn_tolerance: float = 1e-2,
):
    from stock_tax_app.engine.open_positions import build_open_position_rows as _bop

    return _bop(
        raw_rows,
        instrument_map,
        lots,
        safe_float=safe_float,
        parse_trade_date=parse_trade_date,
        ok_tolerance=ok_tolerance,
        warn_tolerance=warn_tolerance,
    )

def build_check_rows(
    *,
    sim_warnings: List[Dict[str, Any]],
    problems: List[Dict[str, Any]],
    fx_yearly: Dict[int, float],
    fx_daily: Dict[date, float],
    settings: Dict[int, Dict[str, Any]],
    locked_years: Dict[int, bool],
    frozen_inventory: Dict[int, List[Dict[str, Any]]],
    split_warnings: List[Dict[str, Any]],
    method_selection: Dict[Tuple[int, str], str],
    yearly_summary: List[Dict[str, Any]],
    match_lines: List[MatchLine],
    lots_final: List[Lot],
    year_end_inventory: Dict[int, List[Lot]],
    frozen_snapshots: Dict[int, Dict[str, Any]],
    fx: "FXResolver",
) -> List[Dict[str, Any]]:
    from stock_tax_app.engine.checks import build_check_rows as _build_check_rows

    return _build_check_rows(
        sim_warnings=sim_warnings,
        problems=problems,
        fx_yearly=fx_yearly,
        fx_daily=fx_daily,
        settings=settings,
        locked_years=locked_years,
        frozen_inventory=frozen_inventory,
        split_warnings=split_warnings,
        method_selection=method_selection,
        yearly_summary=yearly_summary,
        match_lines=match_lines,
        lots_final=lots_final,
        year_end_inventory=year_end_inventory,
        frozen_snapshots=frozen_snapshots,
        fx=fx,
        supported_methods=SUPPORTED_METHODS,
    )


def calculate_workbook_data(
    inputs: List[Path],
    out_path: Path,
    *,
    fetch_missing_fx: bool = True,
) -> CalculationResult:
    legacy_user_state = load_existing_user_state(out_path)
    project_state = project_store.load_project_state(out_path.parent)
    user_state = project_store.merge_project_state_with_legacy_fallback(
        project_state,
        legacy_user_state,
    )

    raw_rows: List[RawRow] = []
    import_log: List[Dict[str, Any]] = []
    problems: List[Dict[str, Any]] = []

    for ipath in inputs:
        rows, probs = read_csv_file(ipath)
        raw_rows.extend(rows)
        problems.extend(probs)
        if rows:
            broker, account = broker_from_filename(ipath)
        else:
            broker, account = ("", "")
        dates = [parse_trade_date(r.data.get("Trade Date") or "") for r in rows]
        dates = [d for d in dates if d is not None]
        syms = sorted({r.symbol for r in rows if r.symbol})
        import_log.append({
            "Source file": ipath.name,
            "Broker": broker,
            "Account": account,
            "Raw rows": len(rows),
            "Transactions": 0,
            "Ignored": 0,
            "Min Trade Date": min(dates) if dates else None,
            "Max Trade Date": max(dates) if dates else None,
            "Unique symbols": ", ".join(syms),
            "Import timestamp": datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        })

    txs, ignored, norm_problems = normalize_transactions(raw_rows)
    problems.extend(norm_problems)

    tx_by_file = defaultdict(int)
    ig_by_file = defaultdict(int)
    for t in txs:
        tx_by_file[t.source_file] += 1
    for ig in ignored:
        ig_by_file[ig["source_file"]] += 1
    for row in import_log:
        row["Transactions"] = tx_by_file.get(row["Source file"], 0)
        row["Ignored"] = ig_by_file.get(row["Source file"], 0)

    years = sorted({t.trade_date.year for t in txs})
    for row in user_state.get("Settings", []) + user_state.get("Locked_Years", []):
        try:
            y = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        if y not in years:
            years.append(y)
    years = sorted(set(years))

    settings = build_settings(user_state, years)
    instrument_map = build_instrument_map(user_state, txs)
    apply_instrument_map(txs, instrument_map)
    fx_yearly, fx_daily, fx_yearly_sources, fx_yearly_manual, fx_daily_sources = build_fx_tables(user_state, years)
    locked_years = build_locked_years(user_state, years)
    corporate_actions, corporate_action_issues = build_corporate_actions(
        user_state,
        known_instrument_ids={t.instrument_id for t in txs if t.instrument_id},
    )
    problems.extend(corporate_action_issues)
    frozen_inventory = load_frozen_inventory(user_state)
    frozen_matching = load_frozen_matching(user_state)
    frozen_snapshots = load_frozen_snapshots(user_state)
    legacy_review_state = load_review_state(user_state)
    canonical_ui_state, adopted_review_count, review_conflict_count = (
        ui_state.load_with_legacy_review_fallback(out_path, legacy_review_state)
    )
    if review_conflict_count:
        print(
            (
                "WARN: ignoring legacy workbook Review_State for "
                f"{review_conflict_count} sell(s) because .ui_state.json is canonical."
            ),
            file=sys.stderr,
        )
    if adopted_review_count:
        print(
            (
                "INFO: migrated legacy workbook Review_State into .ui_state.json for "
                f"{adopted_review_count} sell(s)."
            ),
            file=sys.stderr,
        )
    review_state = ui_state.export_review_state(canonical_ui_state)
    filed_reconciliation = load_filed_reconciliation(user_state)
    instrument_ids = sorted({t.instrument_id for t in txs})
    method_selection = build_method_selection(user_state, years, instrument_ids)

    fx = FXResolver(fx_yearly, fx_daily, settings)

    if fetch_missing_fx:
        daily_years_needed = [
            y for y in years if settings.get(y, {}).get("fx_method") == "FX_DAILY_CNB"
        ]
        if daily_years_needed:
            cache_path = _cnb_cache_path(Path(out_path))
            fx_daily, fx_daily_sources, _dl_msgs = refresh_fx_daily_for_years(
                fx_daily, fx_daily_sources, daily_years_needed, cache_path
            )
            fx = FXResolver(fx_yearly, fx_daily, settings)

    fx_problems = collect_required_fx_problems(txs, settings, fx)
    problems.extend(fx_problems)
    calculation_blocked = bool(fx_problems)

    if calculation_blocked:
        lots_final = []
        match_lines = []
        sim_warnings = []
        year_end_inventory = {}
        yearly_summary = []
        method_comparison = []
    else:
        lots_final, match_lines, sim_warnings, year_end_inventory = simulate(
            txs,
            settings,
            method_selection,
            locked_years,
            corporate_actions,
            frozen_inventory,
            frozen_matching,
            frozen_snapshots,
            fx,
        )

        yearly_summary = build_yearly_summary(match_lines, settings)
        method_comparison = run_method_comparison(
            txs,
            settings,
            method_selection,
            locked_years,
            corporate_actions,
            frozen_inventory,
            frozen_matching,
            frozen_snapshots,
            fx,
        )
    split_warnings = split_audit(txs)

    return CalculationResult(
        inputs=inputs,
        output_path=out_path,
        raw_rows=raw_rows,
        txs=txs,
        ignored=ignored,
        problems=problems,
        import_log=import_log,
        years=years,
        instrument_ids=instrument_ids,
        user_state=user_state,
        settings=settings,
        instrument_map=instrument_map,
        fx_yearly=fx_yearly,
        fx_daily=fx_daily,
        fx_yearly_sources=fx_yearly_sources,
        fx_yearly_manual=fx_yearly_manual,
        fx_daily_sources=fx_daily_sources,
        locked_years=locked_years,
        corporate_actions=corporate_actions,
        frozen_inventory=frozen_inventory,
        frozen_matching=frozen_matching,
        frozen_snapshots=frozen_snapshots,
        review_state=review_state,
        filed_reconciliation=filed_reconciliation,
        method_selection=method_selection,
        fx=fx,
        lots_final=lots_final,
        match_lines=match_lines,
        sim_warnings=sim_warnings,
        year_end_inventory=year_end_inventory,
        yearly_summary=yearly_summary,
        method_comparison=method_comparison,
        split_warnings=split_warnings,
        calculation_blocked=calculation_blocked,
    )


def write_calculation_result(
    result,
    *,
    backup_existing: bool = False,
) -> Path:
    from stock_tax_app.engine.workbook_export import (
        write_calculation_result as _write_calculation_result,
    )
    return _write_calculation_result(
        result,
        backup_existing=backup_existing,
        safe_float=safe_float,
        parse_trade_date=parse_trade_date,
        supported_methods=SUPPORTED_METHODS,
    )


def write_workbook(
    out_path, raw_rows, txs, ignored, problems, instrument_map,
    fx_yearly, fx_daily, fx_daily_sources, corporate_actions,
    method_selection, locked_years, settings, frozen_inventory,
    frozen_matching, frozen_snapshots, fx, lots_final, match_lines,
    sim_warnings, yearly_summary, method_comparison, split_warnings,
    year_end_inventory, import_log, review_state, filed_reconciliation,
    fx_yearly_sources=None,
) -> None:
    from stock_tax_app.engine.workbook_export import write_workbook as _write_workbook
    _write_workbook(
        out_path, raw_rows, txs, ignored, problems, instrument_map,
        fx_yearly, fx_daily, fx_daily_sources, corporate_actions,
        method_selection, locked_years, settings, frozen_inventory,
        frozen_matching, frozen_snapshots, fx, lots_final, match_lines,
        sim_warnings, yearly_summary, method_comparison, split_warnings,
        year_end_inventory, import_log, review_state, filed_reconciliation,
        fx_yearly_sources=fx_yearly_sources,
        safe_float=safe_float,
        parse_trade_date=parse_trade_date,
        supported_methods=SUPPORTED_METHODS,
    )


# Expose individual write helpers for backward compatibility
def _tmp_output_path(out_path):
    from stock_tax_app.engine.workbook_export import _tmp_output_path as _top
    return _top(out_path)


def _backup_existing_output(out_path):
    from stock_tax_app.engine.workbook_export import _backup_existing_output as _beo
    return _beo(out_path)


def _replace_output_or_fail(temp_path, out_path):
    from stock_tax_app.engine.workbook_export import _replace_output_or_fail as _roof
    return _roof(temp_path, out_path)


def autosize_columns(ws, min_width=10, max_width=42):
    from stock_tax_app.engine.workbook_export import autosize_columns as _ac
    return _ac(ws, min_width=min_width, max_width=max_width)


def write_header(ws, headers, row=1):
    from stock_tax_app.engine.workbook_export import write_header as _wh
    return _wh(ws, headers, row=row)


def add_table(ws, name, ref, style="TableStyleMedium2"):
    from stock_tax_app.engine.workbook_export import add_table as _at
    return _at(ws, name, ref, style=style)

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Build Czech stock-trade tax workbook from Yahoo CSVs")
    p.add_argument("--input", nargs="+", required=True,
                   help="CSV input file paths")
    p.add_argument("--output", default="stock_tax_system.xlsx",
                   help="Output .xlsx path")
    p.add_argument(
        "--backup-existing",
        action="store_true",
        help=("Backup existing output to backups/<name>_YYYY-MM-DD_HHMMSS.xlsx "
              "before replace"),
    )
    p.add_argument(
        "--allow-alternate-output",
        action="store_true",
        help=("Allow writing to output names other than "
              f"{CANONICAL_OUTPUT_NAME}"),
    )
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    out_path = Path(args.output)
    if not args.allow_alternate_output and out_path.name != CANONICAL_OUTPUT_NAME:
        print(
            ("Refusing alternate output name while --allow-alternate-output is "
             f"false. Use --output {CANONICAL_OUTPUT_NAME} or pass "
             "--allow-alternate-output."),
            file=sys.stderr,
        )
        return 1
    inputs = [Path(i) for i in args.input]
    result = calculate_workbook_data(inputs, out_path, fetch_missing_fx=True)
    try:
        existing = out_path.exists()
        write_calculation_result(result, backup_existing=args.backup_existing)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Console summary.
    print(f"Workbook written: {out_path}")
    if args.backup_existing and existing:
        print(f"Backup written: {out_path.parent / 'backups'}")
    print(f"  Raw rows:        {len(result.raw_rows)}")
    print(f"  Transactions:    {len(result.txs)}")
    print(f"  Ignored:         {len(result.ignored)}")
    print(f"  Lots (final):    {len(result.lots_final)}")
    print(f"  Match lines:     {len(result.match_lines)}")
    print(f"  Years:           {result.years}")
    print("Per year:")
    for row in result.yearly_summary:
        print(f"  {row['Tax year']}: "
              f"gross CZK {row['Gross proceeds CZK (all sells)']:,.2f}  "
              f"base CZK {row['Final tax base CZK']:,.2f}  "
              f"tax CZK {row['Tax due CZK']:,.2f}  "
              f"({row['FX method']}, "
              f"locked={bool(row['Locked?'])})")
    errs = sum(
        1
        for p in result.problems + result.sim_warnings
        if p.get("severity") == "ERROR"
    )
    if errs:
        print(f"WARN: {errs} errors detected. See Checks sheet.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

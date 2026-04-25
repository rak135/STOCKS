"""FX resolution, loading, CNB download, and preflight logic.

Behavior-preserving extraction from build_stock_tax_workbook.py.
No tax formula logic, no matching, no open-position logic.

Callable utilities that are defined in the monolith (parse_trade_date,
to_bool) are injected by the monolith wrapper so this module has no
imports from build_stock_tax_workbook.
"""

from __future__ import annotations

import json
import urllib.request as _urlreq
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# -----------------------------------------------------------------------
# FX constants
# -----------------------------------------------------------------------

DEFAULT_FX_METHOD = "FX_UNIFIED_GFR"
SUPPORTED_FX_METHODS = ("FX_DAILY_CNB", "FX_UNIFIED_GFR")

# GFŘ unified yearly USD/CZK rates (Czech tax authority official rates).
# Source: GFŘ pokyn (instruction) D-series, published annually by the Czech
# Financial Administration (Generální finanční ředitelství).
# Use FX_UNIFIED_GFR method — this is the correct legal basis for Czech PIT.
# Earlier years use best-available GFŘ / CNB annual averages.
DEFAULT_FX_YEARLY: Dict[int, float] = {
    2015: 24.60, 2016: 24.44, 2017: 23.38, 2018: 21.78,
    2019: 22.93, 2020: 23.14, 2021: 21.68, 2022: 23.36,
    2023: 22.21,
    2024: 23.28,  # GFŘ-D-65  ← authoritative
    2025: 21.84,  # GFŘ-D-75  ← authoritative
    2026: 22.00,  # placeholder — update when GFŘ publishes D-xx for 2026
}

# Official GFŘ unified USD/CZK rates {year: (rate, source_label)}.
GFR_OFFICIAL_RATES: Dict[int, Tuple[float, str]] = {
    2023: (22.21, "GFŘ-D-57"),
    2024: (23.28, "GFŘ-D-65"),
    2025: (21.84, "GFŘ-D-75"),
}

CNB_DAILY_CACHE_FILE = "cnb_daily_cache.json"


# -----------------------------------------------------------------------
# FX table builder
# -----------------------------------------------------------------------

def build_fx_tables(
    user_state: Dict[str, Any],
    years: List[int],
    *,
    parse_trade_date: Callable[[str], Optional[date]],
    to_bool: Callable[[Any, bool], bool],
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
            yearly_manual[y] = to_bool(row.get("__manual__"), False)
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


# -----------------------------------------------------------------------
# CNB cache helpers
# -----------------------------------------------------------------------

def cnb_cache_path(workbook_path: Path) -> Path:
    return workbook_path.parent / CNB_DAILY_CACHE_FILE


def load_cnb_cache(cache_path: Path) -> Dict[str, float]:
    """Load {date_iso: rate} from JSON cache file."""
    if not cache_path.exists():
        return {}
    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_cnb_cache(cache_path: Path, data: Dict[str, float]) -> None:
    try:
        with cache_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


def download_cnb_daily_rates_year(year: int, timeout: int = 15) -> Dict[date, float]:
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
    *,
    load_cnb_cache_func: Optional[Callable[[Path], Dict[str, float]]] = None,
    save_cnb_cache_func: Optional[Callable[[Path, Dict[str, float]], None]] = None,
    download_cnb_daily_rates_year_func: Optional[Callable[..., Dict[date, float]]] = None,
) -> Tuple[Dict[date, float], Dict[date, str], List[str]]:
    """Download missing CNB daily rates for given years.

    Returns (updated_rates, updated_sources, list_of_info_messages).
    """
    msgs: List[str] = []
    if load_cnb_cache_func is None:
        load_cnb_cache_func = load_cnb_cache
    if save_cnb_cache_func is None:
        save_cnb_cache_func = save_cnb_cache
    if download_cnb_daily_rates_year_func is None:
        download_cnb_daily_rates_year_func = download_cnb_daily_rates_year

    cache_raw = load_cnb_cache_func(cache_path)
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
        downloaded = download_cnb_daily_rates_year_func(y)
        if downloaded:
            updated.update(downloaded)
            for d in downloaded:
                updated_sources[d] = "CNB download"
            msgs.append(f"  → {len(downloaded)} dates downloaded for {y}.")
            new_raw = dict(cache_raw)
            for d, r in downloaded.items():
                new_raw[d.isoformat()] = r
            save_cnb_cache_func(cache_path, new_raw)
        else:
            msgs.append(f"  → Download failed for {y} — add rates manually to FX_Daily.")
    return updated, updated_sources, msgs


# -----------------------------------------------------------------------
# FX resolver
# -----------------------------------------------------------------------

class FXResolver:
    def __init__(
        self,
        yearly: Dict[int, float],
        daily: Dict[date, float],
        settings: Dict[int, Dict[str, Any]],
    ) -> None:
        self.yearly = yearly
        self.daily = daily
        self.settings = settings
        self.missing_daily: List[date] = []
        self.missing_yearly: List[int] = []

    def _lookup_daily_rate(self, d: date) -> Tuple[Optional[float], str]:
        if d in self.daily:
            return self.daily[d], "FX_DAILY_CNB_exact"
        for back in range(1, 11):
            alt = d - timedelta(days=back)
            if alt in self.daily:
                return self.daily[alt], f"FX_DAILY_CNB_back{back}d"
        return None, "FX_DAILY_CNB_missing"

    def inspect_date(self, d: date) -> Tuple[Optional[float], str]:
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


# -----------------------------------------------------------------------
# FX preflight
# -----------------------------------------------------------------------

def collect_required_fx_problems(
    txs: List[Any],
    settings: Dict[int, Dict[str, Any]],
    fx: FXResolver,
) -> List[Dict[str, Any]]:
    """Inspect all transactions for missing FX coverage.

    Returns a list of problem dicts.  Missing FX blocks trusted
    calculation — no silent yearly or 22.0 fallback.

    Parameters
    ----------
    txs:
        List of Transaction objects; accessed via .trade_date attribute.
    """
    rows: List[Dict[str, Any]] = []
    missing_daily_by_year: Dict[int, set] = defaultdict(set)
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

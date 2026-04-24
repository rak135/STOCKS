"""Typed API response models.

These are the *only* shapes the frontend ever sees. They are pydantic v2
``BaseModel``s so FastAPI can serialise them and emit an OpenAPI schema
for the frontend to generate types from later.

Monetary values are plain floats in **CZK** or **USD**; unit is always
indicated in the field name (``..._czk``, ``..._usd``) or documented on
the field. ISO date strings are ``YYYY-MM-DD``. Timestamps are ISO 8601
in UTC with ``Z`` suffix.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------

class ApiModel(BaseModel):
    """Base for all API models — forbids extra fields so type drift is
    caught server-side before it bleeds into client types."""

    model_config = ConfigDict(extra="forbid")


class SourceRef(ApiModel):
    """Points to a row in an input CSV file."""
    file: str
    row: int


# ---------------------------------------------------------------------
# Status / checks
# ---------------------------------------------------------------------

class Check(ApiModel):
    id: str
    level: Literal["error", "warn", "info"]
    message: str
    year: Optional[int] = None
    sell_id: Optional[str] = None
    href: str = ""  # deep-link target; frontend interprets


class NextAction(ApiModel):
    label: str
    href: str


class AppStatus(ApiModel):
    project_path: str
    csv_folder: str
    output_path: str
    last_calculated_at: Optional[datetime] = None
    global_status: Literal["ready", "needs_review", "blocked"]
    next_action: Optional[NextAction] = None
    unresolved_checks: List[Check] = Field(default_factory=list)


# ---------------------------------------------------------------------
# Import summary
# ---------------------------------------------------------------------

class ImportFile(ApiModel):
    name: str
    broker: str
    account: str = ""
    account_currency: Optional[str] = None
    total_rows: int
    trade_rows: int
    ignored_rows: int
    position_rows: int
    min_trade_date: Optional[date] = None
    max_trade_date: Optional[date] = None
    unique_symbols: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    status: Literal["ok", "warnings", "error"]


class ImportSummary(ApiModel):
    folder: str
    files: List[ImportFile]
    total_trade_rows: int
    total_ignored_rows: int
    total_warnings: int


# ---------------------------------------------------------------------
# Tax years
# ---------------------------------------------------------------------

Method = Literal["FIFO", "LIFO", "MIN_GAIN", "MAX_GAIN", "MIXED"]
FxMethod = Literal["FX_DAILY_CNB", "FX_UNIFIED_GFR"]
ReconciliationStatus = Literal[
    "not_filed", "reconciled", "needs_attention", "accepted_with_note",
]


class MethodComparison(ApiModel):
    """Informational only — never shown for locked/filed years."""
    FIFO: float
    LIFO: float
    MIN_GAIN: float
    MAX_GAIN: float


class TaxYear(ApiModel):
    year: int
    method: Method
    filed_method: Optional[Method] = None
    fx_method: FxMethod
    tax_rate: float
    exemption_100k: bool

    gross_proceeds_czk: float
    exempt_proceeds_czk: float
    taxable_gains_czk: float
    taxable_losses_czk: float
    taxable_base_czk: float
    tax_due_czk: float
    match_line_count: int

    filed: bool
    locked: bool
    show_method_comparison: bool
    filed_tax_input_czk: Optional[float] = None
    reconciliation_status: ReconciliationStatus
    reconciliation_note: Optional[str] = None
    method_comparison: Optional[MethodComparison] = None


# ---------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------

SellClassification = Literal["taxable", "exempt", "mixed"]
ReviewStatus = Literal["unreviewed", "reviewed", "flagged"]


class MatchedLot(ApiModel):
    lot_id: str
    buy_date: date
    broker: str
    source: SourceRef
    quantity: float
    buy_price_usd: float
    sell_price_usd: float
    fx_buy: float
    fx_sell: float
    cost_basis_czk: float
    proceeds_czk: float
    holding_days: int
    time_test_exempt: bool
    gain_loss_czk: float


class SellSummary(ApiModel):
    """Compact shape returned from GET /api/sales (list)."""
    id: str
    year: int
    date: date
    ticker: str
    instrument_id: str
    broker: str
    quantity: float
    price_usd: float
    proceeds_czk: float
    method: Method
    matched_quantity: float
    unmatched_quantity: float
    classification: SellClassification
    review_status: ReviewStatus


class Sell(SellSummary):
    """Full shape returned from GET /api/sales/{id}."""
    source: SourceRef
    note: str = ""
    total_gain_loss_czk: float
    total_cost_basis_czk: float
    matched_lots: List[MatchedLot]


# ---------------------------------------------------------------------
# Open positions
# ---------------------------------------------------------------------

OpenPositionStatus = Literal["ok", "warn", "error", "unknown"]


class OpenLot(ApiModel):
    lot_id: str
    buy_date: date
    broker: str
    quantity: float
    cost_basis_czk: float
    unrealised_pl_czk: Optional[float] = None


class OpenPosition(ApiModel):
    ticker: str
    instrument_id: str
    calculated_qty: float
    yahoo_qty: Optional[float] = None
    difference: Optional[float] = None
    status: OpenPositionStatus
    lots: List[OpenLot] = Field(default_factory=list)


# ---------------------------------------------------------------------
# FX
# ---------------------------------------------------------------------

FxRateSource = Literal[
    "gfr_official", "cnb_daily", "cache", "manual", "default",
]


class FxYear(ApiModel):
    year: int
    method: FxMethod
    unified_rate: Optional[float] = None
    daily_cached: int = 0
    daily_expected: int = 0
    missing_dates: List[date] = Field(default_factory=list)
    source_label: str
    source_url: Optional[str] = None
    verified_at: Optional[datetime] = None
    manual_override: bool = False
    locked: bool


# ---------------------------------------------------------------------
# Audit / settings
# ---------------------------------------------------------------------

class AuditSummary(ApiModel):
    year_rows: List[TaxYear]
    trace_counts: Dict[str, int]
    locked_snapshots: List[int]


class AppSettings(ApiModel):
    project_folder: str
    csv_folder: str
    output_path: str
    cache_folder: str
    default_tax_rate: float
    default_fx_method: FxMethod
    default_100k: bool
    unmatched_qty_tolerance: float
    position_reconciliation_tolerance: float
    backup_on_recalc: bool
    require_confirm_unlock: bool
    keep_n_snapshots: int
    excel_validation: Literal["strict", "warn", "off"]


# ---------------------------------------------------------------------
# Run input/output
# ---------------------------------------------------------------------

class RunOptions(ApiModel):
    write_excel: bool = False
    fetch_missing_fx: bool = True


class EngineResult(ApiModel):
    """Everything the API needs, in one object."""
    app_status: AppStatus
    import_summary: ImportSummary
    tax_years: List[TaxYear]
    unresolved_checks: List[Check]
    sales: List[Sell]
    open_positions: List[OpenPosition]
    fx_years: List[FxYear]
    audit_summary: AuditSummary
    settings: AppSettings

"""Calculation engine — pure Python, no FastAPI imports here.

The backend calls :func:`run` to get a fully-populated
:class:`EngineResult` (also re-exported here). Excel is an optional
export artifact, never a data source for the API.
"""

from .core import run
from .models import (
    AppSettings,
    AppStatus,
    AuditSummary,
    Check,
    EngineResult,
    FxYear,
    ImportFile,
    ImportSummary,
    MatchedLot,
    OpenLot,
    OpenPosition,
    RunOptions,
    Sell,
    SellSummary,
    SourceRef,
    TaxYear,
)

__all__ = [
    "run",
    "RunOptions",
    "EngineResult",
    "AppStatus",
    "AppSettings",
    "AuditSummary",
    "Check",
    "FxYear",
    "ImportFile",
    "ImportSummary",
    "MatchedLot",
    "OpenLot",
    "OpenPosition",
    "Sell",
    "SellSummary",
    "SourceRef",
    "TaxYear",
]

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
    CollectionTruth,
    EngineResult,
    FxYear,
    FxYearList,
    ImportFile,
    ImportSummary,
    MatchedLot,
    OpenLot,
    OpenPosition,
    OpenPositionList,
    RunOptions,
    Sell,
    SellList,
    SellSummary,
    SettingFieldTruth,
    SourceRef,
    TaxYear,
    TaxYearList,
    TruthMeta,
    TruthReason,
)

__all__ = [
    "run",
    "RunOptions",
    "EngineResult",
    "AppStatus",
    "AppSettings",
    "AuditSummary",
    "Check",
    "CollectionTruth",
    "FxYear",
    "FxYearList",
    "ImportFile",
    "ImportSummary",
    "MatchedLot",
    "OpenLot",
    "OpenPosition",
    "OpenPositionList",
    "Sell",
    "SellList",
    "SellSummary",
    "SettingFieldTruth",
    "SourceRef",
    "TaxYear",
    "TaxYearList",
    "TruthMeta",
    "TruthReason",
]

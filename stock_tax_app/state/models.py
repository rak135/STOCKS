from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


SCHEMA_VERSION = 1


class ProjectStateFxEntry(TypedDict, total=False):
    currency_pair: str
    rate: float
    source_note: str
    manual: bool


class ProjectStateInstrumentMapEntry(TypedDict, total=False):
    yahoo_symbol: str
    instrument_id: str
    isin: str
    instrument_name: str
    notes: str


class ProjectStateCorporateActionEntry(TypedDict, total=False):
    action_id: str
    action_type: str
    effective_date: str
    instrument_id: str
    source_symbol: str
    target_instrument_id: str
    target_symbol: str
    ratio_numerator: float
    ratio_denominator: float
    source: str
    note: str
    enabled: bool


@dataclass(eq=True)
class ProjectStateMetadata:
    schema_version: int = SCHEMA_VERSION


@dataclass(eq=True)
class ProjectState:
    metadata: ProjectStateMetadata = field(default_factory=ProjectStateMetadata)
    year_settings: dict[int, dict[str, Any]] = field(default_factory=dict)
    method_selection: dict[int, dict[str, str]] = field(default_factory=dict)
    fx_yearly: dict[int, ProjectStateFxEntry] = field(default_factory=dict)
    fx_daily: dict[str, ProjectStateFxEntry] = field(default_factory=dict)
    instrument_map: dict[str, ProjectStateInstrumentMapEntry] = field(default_factory=dict)
    corporate_actions: list[ProjectStateCorporateActionEntry] = field(default_factory=list)
    locked_years: dict[int, bool] = field(default_factory=dict)
    frozen_inventory: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    frozen_lot_matching: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    frozen_snapshots: dict[int, dict[str, Any]] = field(default_factory=dict)
    filed_year_reconciliation: dict[int, dict[str, Any]] = field(default_factory=dict)

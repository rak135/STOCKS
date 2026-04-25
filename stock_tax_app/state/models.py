from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = 1


@dataclass(eq=True)
class ProjectStateMetadata:
    schema_version: int = SCHEMA_VERSION


@dataclass(eq=True)
class ProjectState:
    metadata: ProjectStateMetadata = field(default_factory=ProjectStateMetadata)
    year_settings: dict[int, dict[str, Any]] = field(default_factory=dict)
    method_selection: dict[int, dict[str, str]] = field(default_factory=dict)
    fx_yearly: dict[int, dict[str, Any]] = field(default_factory=dict)
    fx_daily: dict[str, dict[str, Any]] = field(default_factory=dict)
    instrument_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    corporate_actions: list[dict[str, Any]] = field(default_factory=list)
    locked_years: dict[int, bool] = field(default_factory=dict)
    frozen_inventory: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    frozen_lot_matching: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    frozen_snapshots: dict[int, dict[str, Any]] = field(default_factory=dict)
    filed_year_reconciliation: dict[int, dict[str, Any]] = field(default_factory=dict)

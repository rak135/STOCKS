from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .models import ProjectState, ProjectStateMetadata, SCHEMA_VERSION

STATE_FILENAME = ".stock_tax_state.json"
_MIGRATED_DOMAINS = frozenset({"year_settings", "method_selection"})


class ProjectStateError(RuntimeError):
    """Base error for project state store failures."""


class UnsupportedProjectStateVersionError(ProjectStateError):
    """Raised when a state file uses an unknown schema version."""


def state_path_for(project_dir: Path | str) -> Path:
    return Path(project_dir).resolve() / STATE_FILENAME


def load_project_state(project_dir: Path | str) -> ProjectState:
    path = state_path_for(project_dir)
    if not path.exists():
        return ProjectState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectStateError(f"Could not read project state {path}: {exc}") from exc

    metadata_raw = raw.get("metadata") or {}
    version = int(metadata_raw.get("schema_version") or 0)
    if version != SCHEMA_VERSION:
        raise UnsupportedProjectStateVersionError(
            f"Unsupported project state schema version {version}; expected {SCHEMA_VERSION}."
        )

    return ProjectState(
        metadata=ProjectStateMetadata(schema_version=version),
        year_settings=_int_keyed_dict(raw.get("year_settings")),
        method_selection=_int_nested_str_dict(raw.get("method_selection")),
        fx_yearly=_int_keyed_dict(raw.get("fx_yearly")),
        fx_daily=_str_keyed_dict(raw.get("fx_daily")),
        instrument_map=_str_keyed_dict(raw.get("instrument_map")),
        corporate_actions=_list_of_dicts(raw.get("corporate_actions")),
        locked_years=_int_bool_dict(raw.get("locked_years")),
        frozen_inventory=_int_keyed_list_dict(raw.get("frozen_inventory")),
        frozen_lot_matching=_int_keyed_list_dict(raw.get("frozen_lot_matching")),
        frozen_snapshots=_int_keyed_dict(raw.get("frozen_snapshots")),
        filed_year_reconciliation=_int_keyed_dict(raw.get("filed_year_reconciliation")),
    )


def save_project_state(project_dir: Path | str, state: ProjectState) -> None:
    path = state_path_for(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _to_json_dict(state)
    encoded = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    fd, tmp_path = tempfile.mkstemp(prefix=".stock_tax_state.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(encoded)
            fh.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def adopt_legacy_workbook_state(
    project_dir: Path | str,
    legacy_state: dict[str, Any],
) -> ProjectState:
    state = load_project_state(project_dir)
    changed = False

    for year, settings_row in _extract_year_settings_from_legacy(legacy_state).items():
        if year not in state.year_settings:
            state.year_settings[year] = settings_row
            changed = True

    for year, method_rows in _extract_method_selection_from_legacy(legacy_state).items():
        current = state.method_selection.setdefault(year, {})
        for instrument_id, method in method_rows.items():
            if instrument_id not in current:
                current[instrument_id] = method
                changed = True

    if changed:
        save_project_state(project_dir, state)
    return state


def merge_project_state_with_legacy_fallback(
    project_state: ProjectState,
    legacy_state: dict[str, Any],
) -> dict[str, Any]:
    merged = {key: list(value) if isinstance(value, list) else value for key, value in legacy_state.items()}
    merged["Settings"] = _merge_settings_rows(project_state, legacy_state.get("Settings") or [])
    merged["Method_Selection"] = _merge_method_selection_rows(
        project_state,
        legacy_state.get("Method_Selection") or [],
    )
    return merged


def migrated_domains() -> set[str]:
    return set(_MIGRATED_DOMAINS)


def _extract_year_settings_from_legacy(legacy_state: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in legacy_state.get("Settings", []):
        try:
            year = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        out[year] = {
            "tax_rate": row.get("Tax rate"),
            "fx_method": row.get("FX method"),
            "apply_100k": row.get("Apply 100k exemption?"),
            "notes": row.get("Notes") or "",
        }
    return out


def _extract_method_selection_from_legacy(
    legacy_state: dict[str, Any],
) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    for row in legacy_state.get("Method_Selection", []):
        try:
            year = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        instrument_id = str(row.get("Instrument_ID") or "").strip()
        method = str(row.get("Method") or "").strip().upper()
        if not instrument_id or not method:
            continue
        out.setdefault(year, {})[instrument_id] = method
    return out


def _merge_settings_rows(
    project_state: ProjectState,
    legacy_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_year: dict[int, dict[str, Any]] = {}
    for row in legacy_rows:
        try:
            year = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        rows_by_year[year] = dict(row)

    for year, state_row in project_state.year_settings.items():
        merged = dict(rows_by_year.get(year, {"Tax year": year, "Locked year?": False}))
        merged["Tax year"] = year
        if "tax_rate" in state_row:
            merged["Tax rate"] = state_row.get("tax_rate")
        if "fx_method" in state_row:
            merged["FX method"] = state_row.get("fx_method")
        if "apply_100k" in state_row:
            merged["Apply 100k exemption?"] = state_row.get("apply_100k")
        if "notes" in state_row:
            merged["Notes"] = state_row.get("notes") or ""
        rows_by_year[year] = merged

    return [rows_by_year[year] for year in sorted(rows_by_year)]


def _merge_method_selection_rows(
    project_state: ProjectState,
    legacy_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[int, str], dict[str, Any]] = {}
    for row in legacy_rows:
        try:
            year = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        instrument_id = str(row.get("Instrument_ID") or "").strip()
        if not instrument_id:
            continue
        rows_by_key[(year, instrument_id)] = dict(row)

    for year, selections in project_state.method_selection.items():
        for instrument_id, method in selections.items():
            key = (year, instrument_id)
            merged = dict(rows_by_key.get(key, {}))
            merged["Tax year"] = year
            merged["Instrument_ID"] = instrument_id
            merged["Method"] = method
            merged.setdefault("Notes", "")
            rows_by_key[key] = merged

    return [
        rows_by_key[key]
        for key in sorted(rows_by_key, key=lambda item: (item[0], item[1]))
    ]


def _to_json_dict(state: ProjectState) -> dict[str, Any]:
    return {
        "metadata": {"schema_version": state.metadata.schema_version},
        "year_settings": {str(k): v for k, v in sorted(state.year_settings.items())},
        "method_selection": {
            str(k): dict(sorted(v.items()))
            for k, v in sorted(state.method_selection.items())
        },
        "fx_yearly": {str(k): v for k, v in sorted(state.fx_yearly.items())},
        "fx_daily": dict(sorted(state.fx_daily.items())),
        "instrument_map": dict(sorted(state.instrument_map.items())),
        "corporate_actions": state.corporate_actions,
        "locked_years": {str(k): v for k, v in sorted(state.locked_years.items())},
        "frozen_inventory": {str(k): v for k, v in sorted(state.frozen_inventory.items())},
        "frozen_lot_matching": {
            str(k): v for k, v in sorted(state.frozen_lot_matching.items())
        },
        "frozen_snapshots": {str(k): v for k, v in sorted(state.frozen_snapshots.items())},
        "filed_year_reconciliation": {
            str(k): v for k, v in sorted(state.filed_year_reconciliation.items())
        },
    }


def _int_keyed_dict(raw: Any) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for key, value in (raw or {}).items():
        try:
            year = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            out[year] = dict(value)
    return out


def _int_nested_str_dict(raw: Any) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    for key, value in (raw or {}).items():
        try:
            year = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        out[year] = {
            str(inner_key): str(inner_value)
            for inner_key, inner_value in value.items()
            if str(inner_key).strip()
        }
    return out


def _int_keyed_list_dict(raw: Any) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for key, value in (raw or {}).items():
        try:
            year = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, list):
            out[year] = [dict(item) for item in value if isinstance(item, dict)]
    return out


def _int_bool_dict(raw: Any) -> dict[int, bool]:
    out: dict[int, bool] = {}
    for key, value in (raw or {}).items():
        try:
            year = int(key)
        except (TypeError, ValueError):
            continue
        out[year] = bool(value)
    return out


def _str_keyed_dict(raw: Any) -> dict[str, dict[str, Any]]:
    return {
        str(key): dict(value)
        for key, value in (raw or {}).items()
        if str(key).strip() and isinstance(value, dict)
    }


def _list_of_dicts(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]

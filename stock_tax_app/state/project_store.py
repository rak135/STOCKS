from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from .models import ProjectState, ProjectStateMetadata, SCHEMA_VERSION

STATE_FILENAME = ".stock_tax_state.json"
_MIGRATED_DOMAINS = frozenset(
    {
        "year_settings",
        "method_selection",
        "fx_yearly",
        "fx_daily",
        "instrument_map",
        "corporate_actions",
    }
)
_FX_CURRENCY_PAIR = "USD/CZK"
_SUPPORTED_CORPORATE_ACTION_TYPES = frozenset({"split", "reverse_split", "ticker_change"})
_SUPPORTED_METHODS = frozenset({"FIFO", "LIFO", "MIN_GAIN", "MAX_GAIN"})


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
        fx_yearly=_int_fx_dict(raw.get("fx_yearly"), default_manual=True),
        fx_daily=_str_fx_dict(raw.get("fx_daily")),
        instrument_map=_str_instrument_map_dict(raw.get("instrument_map")),
        corporate_actions=_normalize_corporate_actions_payload(raw.get("corporate_actions")),
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
    *,
    overwrite: bool = False,
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
            if overwrite or instrument_id not in current:
                current[instrument_id] = method
                changed = True

    for year, fx_row in _extract_fx_yearly_from_legacy(legacy_state).items():
        if overwrite or year not in state.fx_yearly:
            state.fx_yearly[year] = fx_row
            changed = True

    for day, fx_row in _extract_fx_daily_from_legacy(legacy_state).items():
        if overwrite or day not in state.fx_daily:
            state.fx_daily[day] = fx_row
            changed = True

    for symbol, mapping in _extract_instrument_map_from_legacy(legacy_state).items():
        if overwrite or symbol not in state.instrument_map:
            state.instrument_map[symbol] = mapping
            changed = True

    extracted_actions = _extract_corporate_actions_from_legacy(legacy_state)
    if extracted_actions:
        existing_by_key = {
            _corporate_action_identity_key(action): index
            for index, action in enumerate(state.corporate_actions)
        }
        for action in extracted_actions:
            identity = _corporate_action_identity_key(action)
            existing_index = existing_by_key.get(identity)
            if existing_index is None:
                state.corporate_actions.append(action)
                existing_by_key[identity] = len(state.corporate_actions) - 1
                changed = True
                continue
            if overwrite:
                state.corporate_actions[existing_index] = action
                changed = True

    if changed:
        save_project_state(project_dir, state)
    return state


def adopt_legacy_workbook_method_selection(
    project_dir: Path | str,
    legacy_state: dict[str, Any],
    *,
    overwrite: bool = False,
) -> dict[str, int]:
    """Explicitly migrate workbook ``Method_Selection`` rows into ProjectState.

    Normal runtime ignores workbook ``Method_Selection`` (P3.1). This helper is
    the single supported path for adopting legacy per-instrument method
    selections. It also adopts the legacy per-year default method when the
    Settings sheet carries one and ProjectState has none.

    Returns a summary dict with counts:

    - ``legacy_rows`` — total Method_Selection rows seen (after dedupe by key)
    - ``adopted`` — per-instrument rows written into ProjectState
    - ``overwritten`` — rows that replaced an existing ProjectState entry
    - ``skipped_conflicts`` — rows skipped because ProjectState already had a
      value and ``overwrite=False``
    - ``skipped_invalid`` — rows skipped because of unparseable year, missing
      instrument, or unsupported method
    - ``year_defaults_adopted`` — Settings.Method values written into
      ``ProjectState.year_settings[year]['method']``
    - ``year_defaults_overwritten`` — year defaults that replaced an existing
      ProjectState ``year_settings[year]['method']``
    - ``year_defaults_skipped_conflicts`` — year defaults skipped because
      ProjectState already had one and ``overwrite=False``
    """

    state = load_project_state(project_dir)
    summary = {
        "legacy_rows": 0,
        "adopted": 0,
        "overwritten": 0,
        "skipped_conflicts": 0,
        "skipped_invalid": 0,
        "year_defaults_adopted": 0,
        "year_defaults_overwritten": 0,
        "year_defaults_skipped_conflicts": 0,
    }

    raw_rows = legacy_state.get("Method_Selection") or []
    valid_rows: dict[tuple[int, str], str] = {}
    for row in raw_rows:
        if not isinstance(row, dict):
            summary["skipped_invalid"] += 1
            continue
        try:
            year = int(row.get("Tax year"))
        except (TypeError, ValueError):
            summary["skipped_invalid"] += 1
            continue
        instrument_id = str(row.get("Instrument_ID") or "").strip()
        method = str(row.get("Method") or "").strip().upper()
        if not instrument_id or method not in _SUPPORTED_METHODS:
            summary["skipped_invalid"] += 1
            continue
        valid_rows[(year, instrument_id)] = method

    summary["legacy_rows"] = len(valid_rows)

    changed = False
    for (year, instrument_id), method in valid_rows.items():
        current = state.method_selection.setdefault(year, {})
        existing = current.get(instrument_id)
        if existing is None:
            current[instrument_id] = method
            summary["adopted"] += 1
            changed = True
        elif overwrite and existing != method:
            current[instrument_id] = method
            summary["overwritten"] += 1
            changed = True
        elif not overwrite and existing != method:
            summary["skipped_conflicts"] += 1

    for row in legacy_state.get("Settings") or []:
        if not isinstance(row, dict):
            continue
        try:
            year = int(row.get("Tax year"))
        except (TypeError, ValueError):
            continue
        method = str(row.get("Method") or "").strip().upper()
        if method not in _SUPPORTED_METHODS:
            continue
        settings = state.year_settings.setdefault(year, {})
        existing = settings.get("method")
        if existing in (None, ""):
            settings["method"] = method
            summary["year_defaults_adopted"] += 1
            changed = True
        elif overwrite and existing != method:
            settings["method"] = method
            summary["year_defaults_overwritten"] += 1
            changed = True
        elif not overwrite and existing != method:
            summary["year_defaults_skipped_conflicts"] += 1

    if changed:
        save_project_state(project_dir, state)

    return summary


def adopt_legacy_workbook_year_settings(
    project_dir: Path | str,
    workbook_path: Path | str,
    *,
    overwrite: bool = False,
) -> dict[str, int]:
    """Explicitly migrate Settings rows from a legacy workbook into ProjectState.

    Normal runtime ignores workbook ``Settings.Tax rate``, ``Settings.FX method``,
    ``Settings.Apply 100k exemption?``, and ``Settings.Notes`` (P3.2).  This
    helper is the single supported path for adopting those values.

    Field validation/normalization:
    - ``tax_rate``           — must be a float in [0.0, 1.0]; invalid values skipped.
    - ``fx_method``          — must be in SUPPORTED_FX_METHODS; invalid values skipped.
    - ``apply_100k``         — coerced to bool; ``None`` skipped.
    - ``notes``              — preserved as stripped string; blank/missing skipped.

    With ``overwrite=False`` (default) only fields absent in ProjectState are
    written (field-level fill-in).  With ``overwrite=True`` existing fields are
    replaced.

    Returns a summary dict:
    - ``legacy_rows``         — valid Settings rows (parseable year) seen
    - ``skipped_invalid``     — rows with unparseable year (skipped entirely)
    - ``fields_adopted``      — fields written for the first time
    - ``fields_overwritten``  — fields replaced (only when ``overwrite=True``)
    - ``fields_skipped``      — fields skipped because ProjectState already owned
                                the value and ``overwrite=False``
    """
    import build_stock_tax_workbook as _workbook  # local import to avoid circular

    from stock_tax_app.engine.fx import SUPPORTED_FX_METHODS as _SUPPORTED_FX_METHODS

    legacy_state = _workbook.load_existing_user_state(Path(workbook_path))
    raw_rows = legacy_state.get("Settings") or []

    state = load_project_state(project_dir)
    summary: dict[str, int] = {
        "legacy_rows": 0,
        "skipped_invalid": 0,
        "fields_adopted": 0,
        "fields_overwritten": 0,
        "fields_skipped": 0,
    }

    changed = False

    for row in raw_rows:
        if not isinstance(row, dict):
            summary["skipped_invalid"] += 1
            continue
        try:
            year = int(row.get("Tax year"))
        except (TypeError, ValueError):
            summary["skipped_invalid"] += 1
            continue

        summary["legacy_rows"] += 1

        # Normalise / validate each field independently.
        fields: dict[str, Any] = {}

        raw_tax_rate = row.get("Tax rate")
        if raw_tax_rate is not None and raw_tax_rate != "":
            try:
                tax_rate_val = float(raw_tax_rate)
                if 0.0 <= tax_rate_val <= 1.0:
                    fields["tax_rate"] = tax_rate_val
            except (TypeError, ValueError):
                pass

        raw_fx = str(row.get("FX method") or "").strip().upper()
        if raw_fx in _SUPPORTED_FX_METHODS:
            fields["fx_method"] = raw_fx

        raw_100k = row.get("Apply 100k exemption?")
        if raw_100k is not None:
            fields["apply_100k"] = bool(raw_100k)

        raw_notes = row.get("Notes")
        if raw_notes is not None and str(raw_notes).strip():
            fields["notes"] = str(raw_notes).strip()

        if not fields:
            continue

        year_row = state.year_settings.setdefault(year, {})
        for field_name, field_value in fields.items():
            if field_name not in year_row:
                year_row[field_name] = field_value
                summary["fields_adopted"] += 1
                changed = True
            elif overwrite and year_row[field_name] != field_value:
                year_row[field_name] = field_value
                summary["fields_overwritten"] += 1
                changed = True
            elif not overwrite and year_row.get(field_name) != field_value:
                summary["fields_skipped"] += 1

    if changed:
        save_project_state(project_dir, state)

    return summary


def adopt_legacy_workbook_instrument_map(
    project_dir: Path | str,
    workbook_path: Path | str,
    *,
    overwrite: bool = False,
) -> dict[str, int]:
    """Explicitly migrate Instrument_Map rows from a legacy workbook into ProjectState.

    Normal runtime ignores workbook ``Instrument_Map`` (P3.3).  This helper is
    the single supported path for adopting legacy instrument mappings.

    Field validation/normalization:
    - ``Yahoo Symbol`` — required (row key); rows without it are skipped.
    - ``Instrument_ID`` — used as-is; defaults to symbol if blank.
    - ``ISIN`` — preserved as stripped string.
    - ``Instrument name`` — preserved as stripped string.
    - ``Notes`` — preserved as stripped string.

    With ``overwrite=False`` (default) only entries absent in ProjectState are
    written (whole-entry fill-in).  With ``overwrite=True`` existing entries are
    replaced.

    Returns a summary dict:
    - ``legacy_rows``       — valid Instrument_Map rows (non-blank Yahoo Symbol) seen
    - ``skipped_invalid``   — rows skipped because Yahoo Symbol is missing or blank
    - ``adopted``           — entries written for the first time
    - ``overwritten``       — entries replaced (only when ``overwrite=True``)
    - ``skipped_conflicts`` — entries skipped because ProjectState already owned them
                              and ``overwrite=False``
    """
    import build_stock_tax_workbook as _workbook  # local import to avoid circular

    legacy_state = _workbook.load_existing_user_state(Path(workbook_path))
    raw_rows = legacy_state.get("Instrument_Map") or []

    state = load_project_state(project_dir)
    summary: dict[str, int] = {
        "legacy_rows": 0,
        "skipped_invalid": 0,
        "adopted": 0,
        "overwritten": 0,
        "skipped_conflicts": 0,
    }

    changed = False

    for row in raw_rows:
        if not isinstance(row, dict):
            summary["skipped_invalid"] += 1
            continue
        symbol = str(row.get("Yahoo Symbol") or "").strip()
        if not symbol:
            summary["skipped_invalid"] += 1
            continue

        summary["legacy_rows"] += 1
        normalized = _normalize_instrument_map_entry(symbol, row)

        existing = state.instrument_map.get(symbol)
        if existing is None:
            state.instrument_map[symbol] = normalized
            summary["adopted"] += 1
            changed = True
        elif overwrite:
            state.instrument_map[symbol] = normalized
            summary["overwritten"] += 1
            changed = True
        else:
            summary["skipped_conflicts"] += 1

    if changed:
        save_project_state(project_dir, state)

    return summary


def adopt_legacy_workbook_fx(
    project_dir: Path | str,
    workbook_path: Path | str,
    *,
    overwrite: bool = False,
) -> dict[str, dict[str, int]]:
    """Explicitly migrate workbook FX sheets into ProjectState.

    Normal runtime ignores workbook ``FX_Yearly`` and ``FX_Daily`` (P3.4).
    This helper is the supported migration path for importing legacy FX rows.

    Returns per-sheet summary counters under ``yearly`` and ``daily``.
    """
    import build_stock_tax_workbook as _workbook  # local import to avoid circular

    legacy_state = _workbook.load_existing_user_state(Path(workbook_path))
    state = load_project_state(project_dir)

    yearly_summary: dict[str, int] = {
        "legacy_rows": 0,
        "skipped_invalid": 0,
        "adopted": 0,
        "overwritten": 0,
        "skipped_conflicts": 0,
    }
    daily_summary: dict[str, int] = {
        "legacy_rows": 0,
        "skipped_invalid": 0,
        "adopted": 0,
        "overwritten": 0,
        "skipped_conflicts": 0,
    }

    yearly_rows: dict[int, dict[str, Any]] = {}
    for row in legacy_state.get("FX_Yearly") or []:
        if not isinstance(row, dict):
            yearly_summary["skipped_invalid"] += 1
            continue
        try:
            year = int(row.get("Tax year"))
        except (TypeError, ValueError):
            yearly_summary["skipped_invalid"] += 1
            continue
        currency_pair = _normalized_currency_pair(row.get("Currency pair"))
        rate = _coerce_float(row.get("USD_CZK"))
        if currency_pair != _FX_CURRENCY_PAIR or rate is None or rate <= 0.0:
            yearly_summary["skipped_invalid"] += 1
            continue
        source_note = str(row.get("Source / note") or "").strip()
        yearly_rows[year] = {
            "currency_pair": _FX_CURRENCY_PAIR,
            "rate": rate,
            "source_note": source_note,
            "manual": True if not source_note else "manual" in source_note.lower(),
        }

    daily_rows: dict[str, dict[str, Any]] = {}
    for row in legacy_state.get("FX_Daily") or []:
        if not isinstance(row, dict):
            daily_summary["skipped_invalid"] += 1
            continue
        date_key = _coerce_iso_date(row.get("Date"))
        currency_pair = _normalized_currency_pair(row.get("Currency pair"))
        rate = _coerce_float(row.get("USD_CZK"))
        if date_key is None or currency_pair != _FX_CURRENCY_PAIR or rate is None or rate <= 0.0:
            daily_summary["skipped_invalid"] += 1
            continue
        source_note = str(row.get("Source / note") or "").strip()
        daily_rows[date_key] = {
            "currency_pair": _FX_CURRENCY_PAIR,
            "rate": rate,
            "source_note": source_note,
            "manual": "manual" in source_note.lower(),
        }

    yearly_summary["legacy_rows"] = len(yearly_rows)
    daily_summary["legacy_rows"] = len(daily_rows)

    changed = False

    for year, fx_row in yearly_rows.items():
        existing = _normalize_fx_entry(state.fx_yearly.get(year), default_manual=True)
        if existing is None:
            state.fx_yearly[year] = fx_row
            yearly_summary["adopted"] += 1
            changed = True
            continue
        if overwrite:
            if existing != fx_row:
                state.fx_yearly[year] = fx_row
                yearly_summary["overwritten"] += 1
                changed = True
            continue
        yearly_summary["skipped_conflicts"] += 1

    for date_key, fx_row in daily_rows.items():
        existing = _normalize_fx_entry(state.fx_daily.get(date_key))
        if existing is None:
            state.fx_daily[date_key] = fx_row
            daily_summary["adopted"] += 1
            changed = True
            continue
        if overwrite:
            if existing != fx_row:
                state.fx_daily[date_key] = fx_row
                daily_summary["overwritten"] += 1
                changed = True
            continue
        daily_summary["skipped_conflicts"] += 1

    if changed:
        save_project_state(project_dir, state)

    return {
        "yearly": yearly_summary,
        "daily": daily_summary,
    }


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
    merged["FX_Yearly"] = _merge_fx_yearly_rows(
        project_state,
        legacy_state.get("FX_Yearly") or [],
    )
    merged["FX_Daily"] = _merge_fx_daily_rows(
        project_state,
        legacy_state.get("FX_Daily") or [],
    )
    merged["Instrument_Map"] = _merge_instrument_map_rows(
        project_state,
        legacy_state.get("Instrument_Map") or [],
    )
    merged["Corporate_Actions"] = _merge_corporate_actions_rows(
        project_state,
        legacy_state.get("Corporate_Actions") or [],
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
            "method": row.get("Method"),
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


def _extract_fx_yearly_from_legacy(legacy_state: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in legacy_state.get("FX_Yearly", []):
        try:
            year = int(row.get("Tax year"))
            rate = float(row.get("USD_CZK"))
        except (TypeError, ValueError):
            continue
        source_note = str(row.get("Source / note") or "").strip()
        out[year] = {
            "currency_pair": _FX_CURRENCY_PAIR,
            "rate": rate,
            "source_note": source_note,
            "manual": True if not source_note else "manual" in source_note.lower(),
        }
    return out


def _extract_fx_daily_from_legacy(legacy_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in legacy_state.get("FX_Daily", []):
        date_key = _coerce_iso_date(row.get("Date"))
        rate = _coerce_float(row.get("USD_CZK"))
        if date_key is None or rate is None:
            continue
        source_note = str(row.get("Source / note") or "").strip()
        out[date_key] = {
            "currency_pair": _FX_CURRENCY_PAIR,
            "rate": rate,
            "source_note": source_note,
            "manual": "manual" in source_note.lower(),
        }
    return out


def _extract_instrument_map_from_legacy(
    legacy_state: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in legacy_state.get("Instrument_Map", []):
        symbol = str(row.get("Yahoo Symbol") or "").strip()
        if not symbol:
            continue
        out[symbol] = _normalize_instrument_map_entry(symbol, row)
    return out


def _extract_corporate_actions_from_legacy(legacy_state: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for row in legacy_state.get("Corporate_Actions", []):
        if not isinstance(row, dict):
            continue
        date_key = _coerce_iso_date(row.get("Date"))
        instrument_id = str(row.get("Instrument_ID") or "").strip()
        action_type = str(row.get("Action type") or "").strip().lower()
        ratio_old = _coerce_float(row.get("Ratio old"))
        ratio_new = _coerce_float(row.get("Ratio new"))
        note = str(row.get("Notes") or "").strip()
        if not (date_key or instrument_id or action_type or note or ratio_old is not None or ratio_new is not None):
            continue

        # Legacy workbook rows do not carry an action ID, so dedupe by stable identity.
        dedupe_key = (
            date_key or "",
            instrument_id,
            action_type,
            str(ratio_old if ratio_old is not None else ""),
            str(ratio_new if ratio_new is not None else ""),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        out.append(
            {
                "action_id": "",
                "action_type": action_type,
                "effective_date": date_key or "",
                "instrument_id": instrument_id,
                "source_symbol": "",
                "target_instrument_id": "",
                "target_symbol": "",
                "ratio_numerator": 1.0 if ratio_new is None else ratio_new,
                "ratio_denominator": 1.0 if ratio_old is None else ratio_old,
                "source": "workbook_adoption",
                "note": note,
                "enabled": bool(row.get("Applied?", True)),
            }
        )
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
        merged = dict(row)
        # P3.1: workbook Method_Selection retired from runtime; the per-year
        # default method must come from ProjectState or policy/default, never
        # silently from a legacy Settings.Method column.
        merged.pop("Method", None)
        # P3.2: Retire legacy Settings fallback for Tax rate, FX method,
        # Apply 100k exemption?, Notes.  These must come from ProjectState or
        # policy/generated defaults — workbook values are never used silently.
        merged.pop("Tax rate", None)
        merged.pop("FX method", None)
        merged.pop("Apply 100k exemption?", None)
        merged.pop("Notes", None)
        rows_by_year[year] = merged

    for year, state_row in project_state.year_settings.items():
        merged = dict(rows_by_year.get(year, {"Tax year": year, "Locked year?": False}))
        merged["Tax year"] = year
        if "tax_rate" in state_row:
            merged["Tax rate"] = state_row.get("tax_rate")
        if "fx_method" in state_row:
            merged["FX method"] = state_row.get("fx_method")
        if "method" in state_row:
            merged["Method"] = state_row.get("method")
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
    # P3.1: legacy_rows are intentionally ignored. Workbook Method_Selection
    # is no longer a silent runtime fallback — only ProjectState entries
    # contribute, and missing entries fall back to policy/default downstream.
    del legacy_rows
    rows_by_key: dict[tuple[int, str], dict[str, Any]] = {}

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


def _merge_fx_yearly_rows(
    project_state: ProjectState,
    legacy_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # P3.4: legacy_rows are intentionally ignored. Workbook FX_Yearly
    # is no longer a silent runtime fallback — only ProjectState entries
    # contribute, and missing entries use existing default/static behavior
    # downstream.
    del legacy_rows
    rows_by_year: dict[int, dict[str, Any]] = {}

    for year, entry in project_state.fx_yearly.items():
        normalized = _normalize_fx_entry(entry, default_manual=True)
        if normalized is None:
            continue
        merged = dict(rows_by_year.get(year, {}))
        merged["Tax year"] = year
        merged["USD_CZK"] = normalized["rate"]
        merged["Source / note"] = _fx_sheet_source_value(normalized)
        merged["__manual__"] = bool(normalized.get("manual"))
        rows_by_year[year] = merged

    return [rows_by_year[year] for year in sorted(rows_by_year)]


def _merge_fx_daily_rows(
    project_state: ProjectState,
    legacy_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # P3.4: legacy_rows are intentionally ignored. Workbook FX_Daily
    # is no longer a silent runtime fallback — only ProjectState entries
    # contribute, and strict daily mode reports missing coverage as-is.
    del legacy_rows
    rows_by_day: dict[str, dict[str, Any]] = {}

    for date_key, entry in project_state.fx_daily.items():
        normalized = _normalize_fx_entry(entry)
        if normalized is None:
            continue
        merged = dict(rows_by_day.get(date_key, {}))
        merged["Date"] = date_key
        merged["USD_CZK"] = normalized["rate"]
        merged["Source / note"] = _fx_sheet_source_value(normalized)
        rows_by_day[date_key] = merged

    return [rows_by_day[key] for key in sorted(rows_by_day)]


def _merge_instrument_map_rows(
    project_state: ProjectState,
    legacy_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # P3.3: legacy_rows are intentionally ignored. Workbook Instrument_Map
    # is no longer a silent runtime fallback — only ProjectState entries
    # contribute, and missing entries fall back to generated/default instrument
    # identity downstream.
    del legacy_rows
    rows_by_symbol: dict[str, dict[str, Any]] = {}

    for symbol, mapping in project_state.instrument_map.items():
        normalized = _normalize_instrument_map_entry(symbol, mapping)
        merged: dict[str, Any] = {}
        merged["Yahoo Symbol"] = symbol
        merged["Instrument_ID"] = normalized["instrument_id"]
        merged["ISIN"] = normalized["isin"]
        merged["Instrument name"] = normalized["instrument_name"]
        merged["Notes"] = normalized["notes"]
        rows_by_symbol[symbol] = merged

    return [rows_by_symbol[symbol] for symbol in sorted(rows_by_symbol)]


def _merge_corporate_actions_rows(
    project_state: ProjectState,
    legacy_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not project_state.corporate_actions:
        return [dict(row) for row in legacy_rows if isinstance(row, dict)]

    normalized = _normalize_corporate_actions_payload(project_state.corporate_actions)
    return [_project_state_action_to_legacy_row(action) for action in normalized]


def _to_json_dict(state: ProjectState) -> dict[str, Any]:
    return {
        "metadata": {"schema_version": state.metadata.schema_version},
        "year_settings": {str(k): v for k, v in sorted(state.year_settings.items())},
        "method_selection": {
            str(k): dict(sorted(v.items()))
            for k, v in sorted(state.method_selection.items())
        },
        "fx_yearly": {
            str(k): v
            for k, v in sorted(_normalize_fx_yearly_payload(state.fx_yearly).items())
        },
        "fx_daily": dict(sorted(_normalize_fx_daily_payload(state.fx_daily).items())),
        "instrument_map": {
            symbol: entry
            for symbol, entry in sorted(_normalize_instrument_map_payload(state.instrument_map).items())
        },
        "corporate_actions": _normalize_corporate_actions_payload(state.corporate_actions),
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


def _int_fx_dict(raw: Any, *, default_manual: bool = False) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for key, value in (raw or {}).items():
        try:
            year = int(key)
        except (TypeError, ValueError):
            continue
        normalized = _normalize_fx_entry(value, default_manual=default_manual)
        if normalized is not None:
            out[year] = normalized
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


def _normalize_fx_yearly_payload(raw: dict[int, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return _int_fx_dict(raw, default_manual=True)


def _normalize_fx_daily_payload(raw: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return _str_fx_dict(raw)


def _normalize_instrument_map_payload(raw: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return _str_instrument_map_dict(raw)


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


def _str_fx_dict(raw: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, value in (raw or {}).items():
        date_key = _coerce_iso_date(key)
        normalized = _normalize_fx_entry(value)
        if date_key and normalized is not None:
            out[date_key] = normalized
    return out


def _str_instrument_map_dict(raw: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, value in (raw or {}).items():
        symbol = str(key).strip()
        if not symbol or not isinstance(value, dict):
            continue
        out[symbol] = _normalize_instrument_map_entry(symbol, value)
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


def _normalize_corporate_actions_payload(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for item in raw:
        action = _normalize_corporate_action_entry(item)
        if action is None:
            continue
        out.append(action)
    return out


def _normalize_corporate_action_entry(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    action_type = str(raw.get("action_type") or raw.get("Action type") or "").strip().lower()
    if action_type not in _SUPPORTED_CORPORATE_ACTION_TYPES:
        # Keep unknown values to preserve operator data for diagnostics.
        action_type = action_type or ""

    effective_date = _coerce_iso_date(raw.get("effective_date") or raw.get("Date"))
    instrument_id = str(raw.get("instrument_id") or raw.get("Instrument_ID") or "").strip()
    source_symbol = str(raw.get("source_symbol") or raw.get("Yahoo Symbol") or raw.get("Symbol") or "").strip()
    target_instrument_id = str(
        raw.get("target_instrument_id")
        or raw.get("Target instrument")
        or raw.get("Target Instrument_ID")
        or ""
    ).strip()
    target_symbol = str(raw.get("target_symbol") or raw.get("Target symbol") or "").strip()

    ratio_numerator = _coerce_float(raw.get("ratio_numerator"))
    if ratio_numerator is None:
        ratio_numerator = _coerce_float(raw.get("Ratio new"))
    ratio_denominator = _coerce_float(raw.get("ratio_denominator"))
    if ratio_denominator is None:
        ratio_denominator = _coerce_float(raw.get("Ratio old"))

    if ratio_numerator is None:
        ratio_numerator = 1.0
    if ratio_denominator is None:
        ratio_denominator = 1.0

    action_id = str(raw.get("action_id") or "").strip()
    source = str(raw.get("source") or "").strip()
    note = str(raw.get("note") or raw.get("Notes") or "").strip()
    enabled = bool(raw.get("enabled", raw.get("Applied?", True)))

    if not (
        action_id
        or action_type
        or effective_date
        or instrument_id
        or source_symbol
        or target_instrument_id
        or target_symbol
        or note
    ):
        return None

    return {
        "action_id": action_id,
        "action_type": action_type,
        "effective_date": effective_date or "",
        "instrument_id": instrument_id,
        "source_symbol": source_symbol,
        "target_instrument_id": target_instrument_id,
        "target_symbol": target_symbol,
        "ratio_numerator": ratio_numerator,
        "ratio_denominator": ratio_denominator,
        "source": source,
        "note": note,
        "enabled": enabled,
    }


def _corporate_action_identity_key(action: dict[str, Any]) -> tuple[str, str, str, str, str]:
    action_id = str(action.get("action_id") or "").strip()
    if action_id:
        return ("id", action_id, "", "", "")
    return (
        "row",
        str(action.get("effective_date") or "").strip(),
        str(action.get("action_type") or "").strip().lower(),
        str(action.get("instrument_id") or "").strip(),
        str(action.get("target_instrument_id") or action.get("target_symbol") or "").strip(),
    )


def _project_state_action_to_legacy_row(action: dict[str, Any]) -> dict[str, Any]:
    action_id = str(action.get("action_id") or "").strip()
    action_type = str(action.get("action_type") or "").strip().upper()
    note = str(action.get("note") or "").strip()
    if action_type == "TICKER_CHANGE":
        target = str(action.get("target_instrument_id") or action.get("target_symbol") or "").strip()
        if target and f"target={target}" not in note:
            note = f"{note} target={target}".strip()

    ratio_old = _coerce_float(action.get("ratio_denominator"))
    ratio_new = _coerce_float(action.get("ratio_numerator"))
    if ratio_old is None:
        ratio_old = 1.0
    if ratio_new is None:
        ratio_new = 1.0
    enabled = bool(action.get("enabled", True))

    return {
        "Action ID": action_id,
        "Date": str(action.get("effective_date") or "").strip(),
        "Instrument_ID": str(action.get("instrument_id") or action.get("source_symbol") or "").strip(),
        "Action type": action_type,
        "Ratio old": ratio_old,
        "Ratio new": ratio_new,
        "Cash in lieu": 0.0,
        "Notes": note,
        "Applied?": enabled,
        "Audit status": "applied" if enabled else "not applied",
    }


def _normalize_fx_entry(
    raw: Any,
    *,
    default_manual: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    rate = _coerce_float(raw.get("rate"))
    if rate is None:
        rate = _coerce_float(raw.get("usd_czk"))
    if rate is None:
        return None

    source_note = str(
        raw.get("source_note")
        or raw.get("source")
        or raw.get("source_label")
        or ""
    ).strip()
    manual_raw = raw.get("manual")
    if manual_raw is None:
        manual = default_manual if not source_note else "manual" in source_note.lower()
    else:
        manual = bool(manual_raw)

    return {
        "currency_pair": str(raw.get("currency_pair") or raw.get("currency") or _FX_CURRENCY_PAIR),
        "rate": rate,
        "source_note": source_note,
        "manual": manual,
    }


def _normalize_instrument_map_entry(symbol: str, raw: dict[str, Any]) -> dict[str, Any]:
    instrument_id = str(
        raw.get("instrument_id")
        or raw.get("Instrument_ID")
        or raw.get("instrument")
        or symbol
    ).strip() or symbol

    return {
        "yahoo_symbol": str(raw.get("yahoo_symbol") or raw.get("Yahoo Symbol") or symbol).strip() or symbol,
        "instrument_id": instrument_id,
        "isin": str(raw.get("isin") or raw.get("ISIN") or "").strip(),
        "instrument_name": str(raw.get("instrument_name") or raw.get("Instrument name") or "").strip(),
        "notes": str(raw.get("notes") or raw.get("Notes") or "").strip(),
    }


def _fx_sheet_source_value(entry: dict[str, Any]) -> str:
    source_note = str(entry.get("source_note") or "").strip()
    if source_note:
        return source_note
    if bool(entry.get("manual")):
        return "manual"
    return ""


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalized_currency_pair(value: Any) -> str:
    text = str(value or "").strip().upper().replace(" ", "")
    if not text:
        return _FX_CURRENCY_PAIR
    if text == "USDCZK":
        return _FX_CURRENCY_PAIR
    return text


def _coerce_iso_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None

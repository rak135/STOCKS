from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook
import pytest

import build_stock_tax_workbook as workbook_module
from stock_tax_app.backend.main import create_app
from stock_tax_app.engine.core import run
from stock_tax_app.state import project_store
from stock_tax_app.state.models import ProjectState, ProjectStateMetadata, SCHEMA_VERSION


ROOT = Path(__file__).resolve().parent


def _items(payload: dict) -> list[dict]:
    return payload["items"]


def _copy_project_fixture(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    shutil.copytree(ROOT / ".csv", project / ".csv")
    shutil.copy2(ROOT / "stock_tax_system.xlsx", project / "stock_tax_system.xlsx")
    return project


def _set_workbook_tax_rate(project: Path, year: int, tax_rate: float) -> None:
    workbook_path = project / "stock_tax_system.xlsx"
    wb = load_workbook(workbook_path)
    ws = wb["Settings"]
    for row in range(2, ws.max_row + 1):
        if ws.cell(row=row, column=1).value == year:
            ws.cell(row=row, column=2, value=tax_rate)
            wb.save(workbook_path)
            return
    raise AssertionError(f"Year {year} not found in Settings")


def _set_workbook_method_selection(project: Path, year: int, instrument_id: str, method: str) -> None:
    workbook_path = project / "stock_tax_system.xlsx"
    wb = load_workbook(workbook_path)
    ws = wb["Method_Selection"]
    for row in range(4, ws.max_row + 1):
        if (
            ws.cell(row=row, column=1).value == year
            and ws.cell(row=row, column=2).value == instrument_id
        ):
            ws.cell(row=row, column=3, value=method)
            wb.save(workbook_path)
            return
    raise AssertionError(f"Method_Selection row not found for {(year, instrument_id)}")


def _set_workbook_fx_yearly(project: Path, year: int, rate: float, source_note: str = "") -> None:
    workbook_path = project / "stock_tax_system.xlsx"
    wb = load_workbook(workbook_path)
    ws = wb["FX_Yearly"]
    for row in range(4, ws.max_row + 1):
        if ws.cell(row=row, column=1).value == year:
            ws.cell(row=row, column=2, value=rate)
            ws.cell(row=row, column=3, value=source_note)
            wb.save(workbook_path)
            return
    row = ws.max_row + 1
    ws.cell(row=row, column=1, value=year)
    ws.cell(row=row, column=2, value=rate)
    ws.cell(row=row, column=3, value=source_note)
    wb.save(workbook_path)


def _set_workbook_fx_daily(project: Path, day: str, rate: float, source_note: str = "") -> None:
    workbook_path = project / "stock_tax_system.xlsx"
    wb = load_workbook(workbook_path)
    ws = wb["FX_Daily"]
    for row in range(4, ws.max_row + 1):
        value = ws.cell(row=row, column=1).value
        current = value.date().isoformat() if hasattr(value, "date") else str(value or "")
        if current == day:
            ws.cell(row=row, column=1, value=day)
            ws.cell(row=row, column=2, value=rate)
            ws.cell(row=row, column=3, value=source_note)
            wb.save(workbook_path)
            return
    row = ws.max_row + 1
    ws.cell(row=row, column=1, value=day)
    ws.cell(row=row, column=2, value=rate)
    ws.cell(row=row, column=3, value=source_note)
    wb.save(workbook_path)


def _set_workbook_instrument_map(
    project: Path,
    symbol: str,
    *,
    instrument_id: str,
    isin: str = "",
    instrument_name: str = "",
    notes: str = "",
) -> None:
    workbook_path = project / "stock_tax_system.xlsx"
    wb = load_workbook(workbook_path)
    ws = wb["Instrument_Map"]
    for row in range(2, ws.max_row + 1):
        if ws.cell(row=row, column=1).value == symbol:
            ws.cell(row=row, column=2, value=instrument_id)
            ws.cell(row=row, column=3, value=isin)
            ws.cell(row=row, column=4, value=instrument_name)
            ws.cell(row=row, column=5, value=notes)
            wb.save(workbook_path)
            return
    row = ws.max_row + 1
    ws.cell(row=row, column=1, value=symbol)
    ws.cell(row=row, column=2, value=instrument_id)
    ws.cell(row=row, column=3, value=isin)
    ws.cell(row=row, column=4, value=instrument_name)
    ws.cell(row=row, column=5, value=notes)
    wb.save(workbook_path)


def _remove_workbook_instrument_map(project: Path, symbol: str) -> None:
    workbook_path = project / "stock_tax_system.xlsx"
    wb = load_workbook(workbook_path)
    ws = wb["Instrument_Map"]
    for row in range(2, ws.max_row + 1):
        if ws.cell(row=row, column=1).value == symbol:
            for col in range(1, 6):
                ws.cell(row=row, column=col, value=None)
            break
    wb.save(workbook_path)


def _find_settings_row(project: Path, year: int) -> int | None:
    wb = load_workbook(project / "stock_tax_system.xlsx")
    ws = wb["Settings"]
    for row in range(2, ws.max_row + 1):
        if ws.cell(row=row, column=1).value == year:
            return row
    return None


def _find_method_selection_row(project: Path, year: int, instrument_id: str) -> int | None:
    wb = load_workbook(project / "stock_tax_system.xlsx")
    ws = wb["Method_Selection"]
    for row in range(4, ws.max_row + 1):
        if (
            ws.cell(row=row, column=1).value == year
            and ws.cell(row=row, column=2).value == instrument_id
        ):
            return row
    return None


def _find_instrument_map_row(project: Path, symbol: str) -> int | None:
    wb = load_workbook(project / "stock_tax_system.xlsx")
    ws = wb["Instrument_Map"]
    for row in range(2, ws.max_row + 1):
        if ws.cell(row=row, column=1).value == symbol:
            return row
    return None


def test_project_state_missing_file_load_returns_default_state(tmp_path):
    state = project_store.load_project_state(tmp_path)

    assert state == ProjectState()
    assert not project_store.state_path_for(tmp_path).exists()


def test_project_state_roundtrip(tmp_path):
    state = ProjectState(
        metadata=ProjectStateMetadata(schema_version=SCHEMA_VERSION),
        year_settings={
            2025: {
                "method": "MIN_GAIN",
                "tax_rate": 0.2,
                "fx_method": "FX_UNIFIED_GFR",
                "apply_100k": True,
                "notes": "from state",
            }
        },
        method_selection={2025: {"AAPL": "MAX_GAIN"}},
        fx_yearly={2025: {"currency_pair": "USD/CZK", "rate": 21.84, "source_note": "manual", "manual": True}},
        fx_daily={"2025-01-02": {"currency_pair": "USD/CZK", "rate": 21.0, "source_note": "manual", "manual": True}},
        instrument_map={
            "AAPL": {
                "yahoo_symbol": "AAPL",
                "instrument_id": "AAPL",
                "isin": "US0378331005",
                "instrument_name": "Apple Inc.",
                "notes": "state map",
            }
        },
        corporate_actions=[{"Date": "2025-01-01", "Instrument_ID": "AAPL", "Action type": "SPLIT"}],
        locked_years={2024: True},
        frozen_inventory={2024: [{"Lot_ID": "L1"}]},
        frozen_lot_matching={2024: [{"Match_ID": "M1"}]},
        frozen_snapshots={2024: {"Snapshot year": 2024}},
        filed_year_reconciliation={2024: {"filed_tax_due": 123.45}},
    )

    project_store.save_project_state(tmp_path, state)
    reloaded = project_store.load_project_state(tmp_path)

    assert reloaded == state
    payload = json.loads(project_store.state_path_for(tmp_path).read_text(encoding="utf-8"))
    assert payload["metadata"]["schema_version"] == SCHEMA_VERSION
    assert sorted(payload.keys()) == [
        "corporate_actions",
        "filed_year_reconciliation",
        "frozen_inventory",
        "frozen_lot_matching",
        "frozen_snapshots",
        "fx_daily",
        "fx_yearly",
        "instrument_map",
        "locked_years",
        "metadata",
        "method_selection",
        "year_settings",
    ]


def test_project_state_unsupported_version_errors(tmp_path):
    path = project_store.state_path_for(tmp_path)
    path.write_text(
        json.dumps({"metadata": {"schema_version": 999}}, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(project_store.UnsupportedProjectStateVersionError):
        project_store.load_project_state(tmp_path)


def test_project_state_beats_workbook_fallback_for_wired_domains(tmp_path):
    project = _copy_project_fixture(tmp_path)
    baseline = run(project_dir=project, write_workbook=False)
    first_sale = baseline.sales.items[0]

    _set_workbook_tax_rate(project, 2025, 0.19)
    _set_workbook_method_selection(project, first_sale.year, first_sale.instrument_id, "LIFO")

    state = ProjectState(
        year_settings={
            2025: {
                "method": "MAX_GAIN",
                "tax_rate": 0.2,
                "fx_method": "FX_UNIFIED_GFR",
                "apply_100k": False,
                "notes": "state-owned",
            }
        },
        method_selection={first_sale.year: {first_sale.instrument_id: "FIFO"}},
    )
    project_store.save_project_state(project, state)

    result = run(project_dir=project, write_workbook=False)
    sale_after = next(sale for sale in result.sales.items if sale.id == first_sale.id)
    year_2025 = next(year for year in result.tax_years.items if year.year == 2025)

    assert sale_after.method == "FIFO"
    assert year_2025.method == "MAX_GAIN"
    assert year_2025.tax_rate == 0.2


def test_year_method_default_applies_without_known_instruments(tmp_path):
    project = _copy_project_fixture(tmp_path)
    project_store.save_project_state(
        project,
        ProjectState(
            year_settings={
                2030: {
                    "method": "LIFO",
                    "tax_rate": 0.15,
                    "fx_method": "FX_UNIFIED_GFR",
                    "apply_100k": False,
                }
            }
        ),
    )

    result = run(project_dir=project, write_workbook=False)
    year_2030 = next(year for year in result.tax_years.items if year.year == 2030)

    assert year_2030.method == "LIFO"
    assert year_2030.tax_rate == pytest.approx(0.15)


def test_per_instrument_method_override_beats_year_method_default(tmp_path):
    project = _copy_project_fixture(tmp_path)
    baseline = run(project_dir=project, write_workbook=False)
    first_sale = baseline.sales.items[0]

    project_store.save_project_state(
        project,
        ProjectState(
            year_settings={
                first_sale.year: {
                    "method": "MIN_GAIN",
                }
            },
            method_selection={first_sale.year: {first_sale.instrument_id: "FIFO"}},
        ),
    )

    result = run(project_dir=project, write_workbook=False)
    sale_after = next(sale for sale in result.sales.items if sale.id == first_sale.id)
    year_row = next(year for year in result.tax_years.items if year.year == first_sale.year)

    assert sale_after.method == "FIFO"
    assert year_row.method == "MIN_GAIN"


def test_legacy_workbook_fallback_works_and_can_be_adopted(tmp_path):
    project = _copy_project_fixture(tmp_path)
    baseline = run(project_dir=project, write_workbook=False)
    first_sale = baseline.sales.items[0]

    _set_workbook_tax_rate(project, 2025, 0.21)
    _set_workbook_method_selection(project, first_sale.year, first_sale.instrument_id, "MAX_GAIN")

    result = run(project_dir=project, write_workbook=False)
    sale_after = next(sale for sale in result.sales.items if sale.id == first_sale.id)
    year_2025 = next(year for year in result.tax_years.items if year.year == 2025)
    assert sale_after.method == "MAX_GAIN"
    assert year_2025.tax_rate == 0.21

    legacy_state = workbook_module.load_existing_user_state(project / "stock_tax_system.xlsx")
    adopted = project_store.adopt_legacy_workbook_state(project, legacy_state)
    assert project_store.state_path_for(project).exists()
    assert adopted.year_settings[2025]["tax_rate"] == 0.21
    assert adopted.method_selection[first_sale.year][first_sale.instrument_id] == "MAX_GAIN"


def test_project_state_yearly_fx_beats_workbook_fallback(tmp_path):
    project = _copy_project_fixture(tmp_path)
    _set_workbook_fx_yearly(project, 2025, 19.99, "workbook yearly")
    project_store.save_project_state(
        project,
        ProjectState(
            fx_yearly={
                2025: {
                    "currency_pair": "USD/CZK",
                    "rate": 24.44,
                    "source_note": "state yearly",
                    "manual": True,
                }
            }
        ),
    )

    result = run(project_dir=project, write_workbook=False)
    year_2025 = next(year for year in result.fx_years.items if year.year == 2025)

    assert year_2025.unified_rate == 24.44
    assert year_2025.source_label == "state yearly"
    assert year_2025.manual_override is True


def test_project_state_daily_fx_beats_workbook_fallback(tmp_path):
    project = _copy_project_fixture(tmp_path)
    target_day = "2020-02-03"
    _set_workbook_fx_daily(project, target_day, 19.11, "workbook daily")
    project_store.save_project_state(
        project,
        ProjectState(
            fx_daily={
                target_day: {
                    "currency_pair": "USD/CZK",
                    "rate": 24.88,
                    "source_note": "state daily",
                    "manual": True,
                }
            }
        ),
    )

    calc = workbook_module.calculate_workbook_data(
        inputs=sorted((project / ".csv").glob("*.csv")),
        out_path=project / "stock_tax_system.xlsx",
        fetch_missing_fx=False,
    )

    assert calc.fx_daily[date.fromisoformat(target_day)] == 24.88
    assert calc.fx_daily_sources[date.fromisoformat(target_day)] == "state daily"


def test_workbook_fx_fallback_still_works_when_project_state_missing(tmp_path):
    project = _copy_project_fixture(tmp_path)
    _set_workbook_fx_yearly(project, 2025, 20.75, "workbook fallback")

    result = run(project_dir=project, write_workbook=False)
    year_2025 = next(year for year in result.fx_years.items if year.year == 2025)

    assert year_2025.unified_rate == 20.75
    assert year_2025.source_label == "workbook fallback"


def test_explicit_legacy_adoption_migrates_fx_without_overwriting_existing_entries(tmp_path):
    project = _copy_project_fixture(tmp_path)
    _set_workbook_fx_yearly(project, 2025, 20.31, "workbook yearly")
    _set_workbook_fx_daily(project, "2020-02-03", 23.45, "workbook daily")
    project_store.save_project_state(
        project,
        ProjectState(
            fx_yearly={
                2025: {
                    "currency_pair": "USD/CZK",
                    "rate": 26.01,
                    "source_note": "keep state yearly",
                    "manual": True,
                }
            }
        ),
    )

    legacy_state = workbook_module.load_existing_user_state(project / "stock_tax_system.xlsx")
    adopted = project_store.adopt_legacy_workbook_state(project, legacy_state)
    reloaded = project_store.load_project_state(project)

    assert adopted.fx_yearly[2025]["rate"] == 26.01
    assert adopted.fx_yearly[2025]["source_note"] == "keep state yearly"
    assert adopted.fx_daily["2020-02-03"]["rate"] == 23.45
    assert reloaded.fx_yearly[2025]["rate"] == 26.01
    assert reloaded.fx_daily["2020-02-03"]["source_note"] == "workbook daily"


def test_project_state_instrument_map_beats_workbook_fallback(tmp_path):
    project = _copy_project_fixture(tmp_path)
    symbol = "SHOP"
    _set_workbook_instrument_map(
        project,
        symbol,
        instrument_id="SHOP_WORKBOOK",
        isin="WB000SHOP",
        instrument_name="Workbook SHOP",
        notes="workbook map",
    )
    project_store.save_project_state(
        project,
        ProjectState(
            instrument_map={
                symbol: {
                    "yahoo_symbol": symbol,
                    "instrument_id": "SHOP_STATE",
                    "isin": "STATE000SHOP",
                    "instrument_name": "State SHOP",
                    "notes": "state map",
                }
            }
        ),
    )

    result = run(project_dir=project, write_workbook=False)
    sale = next(sale for sale in result.sales.items if sale.ticker == symbol)

    assert sale.instrument_id == "SHOP_STATE"

    calc = workbook_module.calculate_workbook_data(
        inputs=sorted((project / ".csv").glob("*.csv")),
        out_path=project / "stock_tax_system.xlsx",
        fetch_missing_fx=False,
    )
    assert calc.instrument_map[symbol]["Instrument_ID"] == "SHOP_STATE"
    assert calc.instrument_map[symbol]["ISIN"] == "STATE000SHOP"


def test_workbook_instrument_map_fallback_still_works(tmp_path):
    project = _copy_project_fixture(tmp_path)
    symbol = "SHOP"
    _set_workbook_instrument_map(
        project,
        symbol,
        instrument_id="SHOP_WORKBOOK",
        isin="WB000SHOP",
        instrument_name="Workbook SHOP",
        notes="workbook map",
    )

    result = run(project_dir=project, write_workbook=False)
    sale = next(sale for sale in result.sales.items if sale.ticker == symbol)
    assert sale.instrument_id == "SHOP_WORKBOOK"


def test_default_generated_instrument_map_still_works(tmp_path):
    project = _copy_project_fixture(tmp_path)
    symbol = "SHOP"
    _remove_workbook_instrument_map(project, symbol)

    calc = workbook_module.calculate_workbook_data(
        inputs=sorted((project / ".csv").glob("*.csv")),
        out_path=project / "stock_tax_system.xlsx",
        fetch_missing_fx=False,
    )

    assert calc.instrument_map[symbol]["Yahoo Symbol"] == symbol
    assert calc.instrument_map[symbol]["Instrument_ID"] == symbol
    assert calc.instrument_map[symbol]["ISIN"] == ""


def test_explicit_legacy_adoption_migrates_instrument_map_without_overwriting_by_default(tmp_path):
    project = _copy_project_fixture(tmp_path)
    symbol = "SHOP"
    copied_symbol = "AMD"
    _set_workbook_instrument_map(
        project,
        symbol,
        instrument_id="SHOP_WORKBOOK",
        isin="WB000SHOP",
        instrument_name="Workbook SHOP",
        notes="workbook map",
    )
    project_store.save_project_state(
        project,
        ProjectState(
            instrument_map={
                symbol: {
                    "yahoo_symbol": symbol,
                    "instrument_id": "SHOP_STATE",
                    "isin": "STATE000SHOP",
                    "instrument_name": "State SHOP",
                    "notes": "state map",
                }
            }
        ),
    )

    legacy_state = workbook_module.load_existing_user_state(project / "stock_tax_system.xlsx")
    adopted = project_store.adopt_legacy_workbook_state(project, legacy_state)
    assert copied_symbol in adopted.instrument_map
    assert adopted.instrument_map[copied_symbol]["instrument_id"] == copied_symbol
    assert adopted.instrument_map[symbol]["instrument_id"] == "SHOP_STATE"
    assert adopted.instrument_map[symbol]["notes"] == "state map"

    overwritten = project_store.adopt_legacy_workbook_state(project, legacy_state, overwrite=True)
    assert overwritten.instrument_map[symbol]["instrument_id"] == "SHOP_WORKBOOK"
    assert overwritten.instrument_map[symbol]["isin"] == "WB000SHOP"


def test_workbook_export_reflects_project_state_for_migrated_domains(tmp_path):
    project = _copy_project_fixture(tmp_path)
    baseline = run(project_dir=project, write_workbook=False)
    first_sale = baseline.sales.items[0]

    _set_workbook_tax_rate(project, 2025, 0.19)
    _set_workbook_method_selection(project, first_sale.year, first_sale.instrument_id, "LIFO")

    project_store.save_project_state(
        project,
        ProjectState(
            year_settings={
                2025: {
                    "tax_rate": 0.2,
                    "fx_method": "FX_UNIFIED_GFR",
                    "apply_100k": False,
                    "notes": "exported from state",
                }
            },
            method_selection={first_sale.year: {first_sale.instrument_id: "FIFO"}},
        ),
    )

    client = TestClient(create_app(project_dir=project))
    result = client.app.state.runtime.calculate(write_workbook=True)
    assert result.tax_years.items

    settings_row = _find_settings_row(project, 2025)
    method_row = _find_method_selection_row(project, first_sale.year, first_sale.instrument_id)
    assert settings_row is not None
    assert method_row is not None

    wb = load_workbook(project / "stock_tax_system.xlsx")
    assert wb["Settings"].cell(row=settings_row, column=2).value == 0.2
    assert wb["Method_Selection"].cell(row=method_row, column=3).value == "FIFO"


def test_workbook_export_reflects_project_state_instrument_map(tmp_path):
    project = _copy_project_fixture(tmp_path)
    symbol = "SHOP"
    _set_workbook_instrument_map(
        project,
        symbol,
        instrument_id="SHOP_WORKBOOK",
        isin="WB000SHOP",
        instrument_name="Workbook SHOP",
        notes="workbook map",
    )
    project_store.save_project_state(
        project,
        ProjectState(
            instrument_map={
                symbol: {
                    "yahoo_symbol": symbol,
                    "instrument_id": "SHOP_STATE",
                    "isin": "STATE000SHOP",
                    "instrument_name": "State SHOP",
                    "notes": "state map",
                }
            }
        ),
    )

    client = TestClient(create_app(project_dir=project))
    result = client.app.state.runtime.calculate(write_workbook=True)
    assert result.sales.items

    row = _find_instrument_map_row(project, symbol)
    assert row is not None

    wb = load_workbook(project / "stock_tax_system.xlsx")
    ws = wb["Instrument_Map"]
    assert ws.cell(row=row, column=2).value == "SHOP_STATE"
    assert ws.cell(row=row, column=3).value == "STATE000SHOP"
    assert ws.cell(row=row, column=4).value == "State SHOP"
    assert ws.cell(row=row, column=5).value == "state map"

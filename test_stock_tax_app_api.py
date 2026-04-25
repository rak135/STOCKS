from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

import build_stock_tax_workbook as workbook_module
from stock_tax_app.backend.main import create_app
from stock_tax_app.engine import policy
from stock_tax_app.engine import core as engine_core
from stock_tax_app.engine.core import run


ROOT = Path(__file__).resolve().parent


def _copy_project_fixture(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    shutil.copytree(ROOT / ".csv", project / ".csv")
    shutil.copy2(ROOT / "stock_tax_system.xlsx", project / "stock_tax_system.xlsx")
    return project


def test_engine_run_returns_engine_result(tmp_path):
    project = _copy_project_fixture(tmp_path)
    result = run(project_dir=project, write_workbook=False)

    assert result.__class__.__name__ == "EngineResult"
    assert result.tax_years
    assert result.sales
    year_2024 = next(year for year in result.tax_years if year.year == 2024)
    assert year_2024.method == "LIFO"
    assert year_2024.filed is True
    assert year_2024.locked is True
    year_2025 = next(year for year in result.tax_years if year.year == 2025)
    assert year_2025.method == "FIFO"
    assert year_2025.filed is False
    assert year_2025.locked is False


def test_api_status_import_years_and_sales(tmp_path):
    project = _copy_project_fixture(tmp_path)
    client = TestClient(create_app(project_dir=project))

    status = client.get("/api/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["next_action"] is not None
    assert status_body["next_action"]["href"] in engine_core.FRONTEND_READY_HREFS

    import_summary = client.get("/api/import")
    assert import_summary.status_code == 200
    assert len(import_summary.json()["files"]) == 5

    years = client.get("/api/years")
    assert years.status_code == 200
    year_2024 = next(year for year in years.json() if year["year"] == 2024)
    assert year_2024["method"] == "LIFO"
    assert year_2024["filed"] is True
    assert year_2024["locked"] is True
    assert year_2024["show_method_comparison"] is False

    sales = client.get("/api/sales")
    assert sales.status_code == 200
    assert len(sales.json()) > 0


def test_policy_module_is_canonical_year_source_of_truth():
    assert policy.is_filed(2024) is True
    assert policy.is_locked(2024) is True
    assert policy.filed_method(2024) == "LIFO"
    assert policy.default_method_for(2024) == "LIFO"
    assert policy.resolved_method_for(2024, "FIFO") == "LIFO"

    assert policy.is_filed(2025) is False
    assert policy.is_locked(2025) is False
    assert policy.default_method_for(2025) == "FIFO"
    assert policy.resolved_method_for(2025) == "FIFO"
    assert policy.resolved_method_for(2025, None) == "FIFO"


def test_workbook_policy_aliases_cannot_drift_from_engine_policy():
    assert workbook_module.FILED_YEARS is policy.FILED_YEARS
    assert workbook_module.YEAR_DEFAULT_METHODS is policy.YEAR_DEFAULT_METHODS
    assert workbook_module.DEFAULT_METHOD == policy.DEFAULT_METHOD
    assert workbook_module.SUPPORTED_METHODS == policy.SUPPORTED_METHODS

    selection = workbook_module.build_method_selection(
        user_state={},
        years=[2024, 2025],
        instrument_ids=["AAPL"],
    )
    assert selection[(2024, "AAPL")] == "LIFO"
    assert selection[(2025, "AAPL")] == "FIFO"


def test_status_routing_only_uses_live_frontend_hrefs(tmp_path):
    project = _copy_project_fixture(tmp_path)
    client = TestClient(create_app(project_dir=project))

    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()

    placeholder_hrefs = {
        "/audit",
        "/fx",
        "/open-positions",
        "/settings",
        "/sales-review",
    }
    allowed_hrefs = set(engine_core.FRONTEND_READY_HREFS)

    assert body["next_action"] is not None
    assert body["next_action"]["href"] in allowed_hrefs
    assert body["next_action"]["href"] not in placeholder_hrefs

    unresolved_checks = body["unresolved_checks"]
    assert unresolved_checks
    assert {check["href"] for check in unresolved_checks}.issubset(allowed_hrefs)
    assert not ({check["href"] for check in unresolved_checks} & placeholder_hrefs)


@pytest.mark.parametrize(
    ("category", "expected_href"),
    [
        ("fx_missing", "/"),
        ("remaining_position_mismatch", "/"),
        ("import_warning", "/import"),
        ("method_policy", "/tax-years"),
        ("filed_reconciliation", "/tax-years"),
        ("generic_check", "/"),
    ],
)
def test_check_href_remaps_placeholder_destinations(category, expected_href):
    assert engine_core._check_href(category) == expected_href
    assert engine_core._check_href(category) in engine_core.FRONTEND_READY_HREFS


def test_unresolved_checks_still_appear_when_href_is_remapped(tmp_path):
    project = _copy_project_fixture(tmp_path)
    client = TestClient(create_app(project_dir=project))

    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()

    assert body["global_status"] == "needs_review"
    assert body["next_action"] == {"label": "Review checks", "href": "/"}
    assert body["unresolved_checks"]
    assert all(check["message"] for check in body["unresolved_checks"])
    assert all(check["href"] == "/" for check in body["unresolved_checks"])


def test_patch_sale_review_updates_ui_state_only(tmp_path):
    project = _copy_project_fixture(tmp_path)
    client = TestClient(create_app(project_dir=project))

    sales_before = client.get("/api/sales").json()
    sell_id = sales_before[0]["id"]
    detail_before = client.get(f"/api/sales/{sell_id}").json()
    years_before = client.get("/api/years").json()

    patched = client.patch(
        f"/api/sales/{sell_id}/review",
        json={"review_status": "reviewed", "note": "Checked in UI"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["review_status"] == "reviewed"
    assert body["note"] == "Checked in UI"

    ui_state_path = project / ".ui_state.json"
    assert ui_state_path.exists()
    ui_state_text = ui_state_path.read_text(encoding="utf-8")
    assert sell_id in ui_state_text
    assert "Checked in UI" in ui_state_text

    detail_after = client.get(f"/api/sales/{sell_id}").json()
    years_after = client.get("/api/years").json()
    assert detail_before["total_gain_loss_czk"] == detail_after["total_gain_loss_czk"]
    assert detail_before["total_cost_basis_czk"] == detail_after["total_cost_basis_czk"]
    assert years_before == years_after


def test_api_rejects_2024_method_change(tmp_path):
    project = _copy_project_fixture(tmp_path)
    client = TestClient(create_app(project_dir=project))

    response = client.patch("/api/years/2024", json={"method": "FIFO"})
    assert response.status_code == 409
    assert "2024 is locked" in response.json()["detail"]


def test_locked_output_fails_without_alternate_workbook(tmp_path, monkeypatch):
    out_path = tmp_path / "stock_tax_system.xlsx"
    temp_path = tmp_path / ".stock_tax_system.tmp.xlsx"
    temp_path.write_text("temp", encoding="utf-8")

    def raise_permission_error(src, dst):
        raise PermissionError("locked")

    monkeypatch.setattr(workbook_module.os, "replace", raise_permission_error)

    with pytest.raises(RuntimeError) as excinfo:
        workbook_module._replace_output_or_fail(temp_path, out_path)

    assert str(excinfo.value) == (
        "Cannot write stock_tax_system.xlsx because it is open or locked. "
        "Close Excel and rerun."
    )
    assert not temp_path.exists()
    assert not any(tmp_path.glob("stock_tax_system_new*.xlsx"))

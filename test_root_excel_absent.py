"""Invariants for the Excel-retirement product decision.

These tests guard the rule that the repo-root `stock_tax_system.xlsx`
is no longer required, expected, or implied as a runtime artifact:

- The file must not exist at the repository root.
- The backend / API must come up and serve core endpoints without it.
- `POST /api/recalculate` must not create it.
- The default backend output_path must not point at the legacy name.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from stock_tax_app.backend.main import create_app


REPO_ROOT = Path(__file__).resolve().parent
LEGACY_NAME = "stock_tax_system.xlsx"


def _copy_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    shutil.copytree(REPO_ROOT / ".csv", project / ".csv")
    return project


def test_repo_root_legacy_workbook_is_absent() -> None:
    assert not (REPO_ROOT / LEGACY_NAME).exists(), (
        f"{LEGACY_NAME} must not exist at the repo root; Excel is no longer "
        "the runtime truth or a tracked product artifact."
    )


def test_backend_default_output_path_is_not_legacy_name(tmp_path: Path) -> None:
    project = _copy_project(tmp_path)
    app = create_app(project_dir=project, csv_dir=project / ".csv")
    runtime = app.state.runtime
    assert runtime.output_path.name != LEGACY_NAME, (
        "Backend default output_path must not point at the retired "
        f"{LEGACY_NAME}."
    )
    assert not (project / LEGACY_NAME).exists()


def test_backend_api_runs_without_legacy_workbook(tmp_path: Path) -> None:
    project = _copy_project(tmp_path)
    assert not (project / LEGACY_NAME).exists()

    app = create_app(project_dir=project, csv_dir=project / ".csv")
    client = TestClient(app)

    for path in ("/api/status", "/api/years", "/api/sales"):
        resp = client.get(path)
        assert resp.status_code == 200, (path, resp.status_code, resp.text[:300])

    # API call should not have caused a legacy-named workbook to appear.
    assert not (project / LEGACY_NAME).exists()


def test_recalculate_does_not_create_legacy_workbook(tmp_path: Path) -> None:
    project = _copy_project(tmp_path)
    app = create_app(project_dir=project, csv_dir=project / ".csv")
    client = TestClient(app)

    resp = client.post("/api/recalculate")
    assert resp.status_code == 200, resp.text[:300]

    assert not (project / LEGACY_NAME).exists(), (
        "POST /api/recalculate must remain state-only and must not write "
        f"{LEGACY_NAME}."
    )
    # Also confirm no .xlsx was written next to the configured output.
    runtime = app.state.runtime
    assert not runtime.output_path.exists(), (
        f"Recalculate must not write the export file at {runtime.output_path}."
    )

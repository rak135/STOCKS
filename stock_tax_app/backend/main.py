from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, Request

from stock_tax_app.engine import EngineResult

from .runtime import BackendRuntime
from .routes import audit, fx, import_summary, positions, sales, settings, status, years


def create_app(
    *,
    project_dir: Path | None = None,
    csv_dir: Path | None = None,
    output_path: Path | None = None,
) -> FastAPI:
    project = Path(project_dir or Path.cwd()).resolve()
    csv = Path(csv_dir or (project / ".csv")).resolve()
    output = Path(output_path or (project / "stock_tax_system.xlsx")).resolve()

    app = FastAPI(title="Stock Tax App", version="0.1.0")
    app.state.runtime = BackendRuntime(project_dir=project, csv_dir=csv, output_path=output)

    app.include_router(status.router)
    app.include_router(import_summary.router)
    app.include_router(years.router)
    app.include_router(sales.router)
    app.include_router(positions.router)
    app.include_router(fx.router)
    app.include_router(audit.router)
    app.include_router(settings.router)

    recalc_router = APIRouter()

    @recalc_router.post("/api/recalculate", response_model=EngineResult)
    def recalculate(request: Request) -> EngineResult:
        return request.app.state.runtime.calculate(write_workbook=True)

    app.include_router(recalc_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "stock_tax_app.backend.main:app",
        host="127.0.0.1",
        port=8787,
        reload=False,
    )

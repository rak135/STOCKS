from __future__ import annotations

from pathlib import Path

from stock_tax_app.engine import EngineResult, run
from stock_tax_app.engine import ui_state


class BackendRuntime:
    def __init__(
        self,
        *,
        project_dir: Path,
        csv_dir: Path,
        output_path: Path,
    ) -> None:
        self.project_dir = project_dir
        self.csv_dir = csv_dir
        self.output_path = output_path
        self._last_result: EngineResult | None = None

    def calculate(self, *, write_workbook: bool) -> EngineResult:
        result = run(
            project_dir=self.project_dir,
            csv_dir=self.csv_dir,
            output_path=self.output_path,
            write_workbook=write_workbook,
        )
        self._last_result = result
        return result

    def current(self) -> EngineResult:
        if self._last_result is None:
            return self.calculate(write_workbook=False)
        return self._last_result

    def update_sell_review(
        self,
        sell_id: str,
        *,
        review_status: str | None = None,
        note: str | None = None,
    ) -> EngineResult:
        state = ui_state.load(self.project_dir, legacy_workbook_path=self.output_path)
        state.set_review(sell_id, review_status=review_status, note=note)
        ui_state.save(self.project_dir, state)
        return self.calculate(write_workbook=False)

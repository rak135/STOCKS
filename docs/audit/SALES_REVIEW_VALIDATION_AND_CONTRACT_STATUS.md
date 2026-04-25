# Sales Review Validation And Contract Status

Date: 2026-04-25

## Scope

P1.4a only:

- validation environment hardening for backend/Python
- rerun backend/frontend validation commands
- harden Sales Review list contract for list-level financial fields

No other screen or migration slice was changed.

## Dependency And Setup Changes

### Findings

- No Python dependency manifest existed (`requirements.txt`, `pyproject.toml`, `setup.py`, `setup.cfg` were absent).
- Backend/tests import external packages including:
  - `fastapi`
  - `pydantic`
  - `openpyxl`
  - `pytest`
  - `uvicorn`
  - `httpx` (needed by TestClient stack in practice)
- Prior test failures (`ModuleNotFoundError: fastapi/openpyxl`) were caused by environment drift plus missing declared dependencies. Without a manifest, `py -3` may target an interpreter where required packages are not installed.

### Manifest Added

Added `requirements.txt` with pinned versions used for reproducible Windows setup.

### Setup Docs Added

Updated `README.md` with backend dependency install command and exact pytest commands.

## Backend Sales List Contract Hardening

### Problem

Sales list rows (`GET /api/sales`) did not expose list-level `cost basis` and `gain/loss`, so frontend had to render placeholders despite data existing in detail responses.

### Contract Changes

`SellSummary` now includes:

- `total_cost_basis_czk`
- `total_gain_loss_czk`

These values are sourced from existing backend sale data (same source used by detail response), not recomputed in frontend.

### Compatibility Fix

Added `sell_id` field in `SellSummary`/`Sell` and populated from canonical sale id to support smoke scripts and clients using `sell_id` key in list payloads.

## Frontend Changes

Sales Review list now renders backend-provided list-level values for:

- cost basis (`total_cost_basis_czk`)
- gain/loss (`total_gain_loss_czk`)

The previous "not available from backend" labels were removed for these two fields only.

## Tests Added/Extended

In `test_stock_tax_app_api.py`:

- `test_sales_list_includes_financial_fields_and_matches_detail`
  - verifies list includes `total_cost_basis_czk` and `total_gain_loss_czk`
  - verifies list values equal detail values for same sale
- `test_sales_list_blocked_empty_has_no_financial_rows`
  - verifies blocked sales list remains empty and truthful (`empty_meaning = blocked`)
  - verifies no fake list rows are emitted under blocked state

## Commands Run And Results

### Dependency install

- `py -3 -m pip install -r requirements.txt`
- Result: Pass

### Full test suite

- `py -3 -m pytest -q`
- Result: Pass (`51 passed`)

### Focused suites

- `py -3 -m pytest -q test_stock_tax_app_api.py`
- Result: Pass (`34 passed`)

- `py -3 -m pytest -q test_project_state_store.py`
- Result: Pass (`15 passed`)

### Backend smoke

Equivalent PowerShell-safe execution of requested script logic:

- `/api/status` -> `200`
- `/api/sales` -> `200`
- `/api/sales/{sell_id from list item}` -> `200`

### Frontend build

- `cd ui/frontend`
- `npm run build`
- Result: Pass

## Files Changed

- `requirements.txt`
- `README.md`
- `stock_tax_app/engine/models.py`
- `stock_tax_app/engine/core.py`
- `stock_tax_app/backend/routes/sales.py`
- `ui/frontend/src/types/api.ts`
- `ui/frontend/src/screens/sales-review-screen.tsx`
- `test_stock_tax_app_api.py`
- `docs/audit/SALES_REVIEW_VALIDATION_AND_CONTRACT_STATUS.md`

## Remaining Sales Review Gaps

- No additional Sales Review UX expansion (filters/search/etc.) was added in this slice by design.
- Truth/provenance semantics remain unchanged.

## Acceptance Status

Sales Review is accepted as validated for P1.4a:

- environment is reproducible via declared backend dependencies
- required backend/frontend validation commands pass
- list contract now truthfully exposes list-level cost basis and gain/loss

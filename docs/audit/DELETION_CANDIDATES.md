# Deletion Candidates

This file is intentionally conservative.

If evidence is not strong enough, the item is not marked “definitely safe”.

## Definitely Safe Deletion Candidates

| Path | Why it looks safe | Evidence | Command/test before deletion |
|---|---|---|---|
| `backend_server.out.log` | Generated runtime log only | No code references found; root `.gitignore` ignores `*.log`; file contents are Uvicorn request logs | `rg -n "backend_server\\.out\\.log" -S .` then `Remove-Item backend_server.out.log` |
| `backend_server.err.log` | Generated runtime log only | No code references found; root `.gitignore` ignores `*.log`; file contents are Uvicorn startup logs | `rg -n "backend_server\\.err\\.log" -S .` then `Remove-Item backend_server.err.log` |
| `build/` (empty) | Empty ignored directory | `Get-ChildItem build` returned nothing; `.gitignore` ignores `build/` | `Get-ChildItem -Force build` |

## Probably Dead, But Confirm Before Deletion

| Path | Why it looks dead | Evidence | Confirmation command/test |
|---|---|---|---|
| `ui/prototype.html` | Not part of Vite app or backend; only referenced by design doc | No imports or runtime references. Only `ui/DESIGN.md` points to it. | `rg -n "prototype.html" -S ui docs README*.md` |
| `docs/api_samples/*.json` | Unreferenced API snapshots | No repo code imports or links them. `status.json` contains a local machine path. | `rg -n "api_samples" -S .` |
| `temp/stock_tax_system.xlsx` | Unreferenced temp workbook under ignored folder | No code references to `temp\\stock_tax_system.xlsx`; folder is ignored | `rg -n "temp\\\\stock_tax_system.xlsx|temp/" -S .` |
| `README_OPERATOR.md` | Entirely workbook-first operator manual | Accurate for old workflow, wrong for target product direction. Still referenced from `build_stock_tax_workbook.py` docstring. | Replace references, then `rg -n "README_OPERATOR\\.md" -S .` |
| `IMPLEMENTATION_NOTES.md` | Workbook-era internal design doc | Still referenced by `build_stock_tax_workbook.py` docstring and useful during migration. | Replace references, then `rg -n "IMPLEMENTATION_NOTES\\.md" -S .` |

## Must Not Delete Yet

| Path | Why it must stay | Evidence |
|---|---|---|
| `build_stock_tax_workbook.py` | Still owns core calculation, workbook state loading, workbook writing, and export validation flow | `stock_tax_app/engine/core.py:9,489-496`; `build_stock_tax_workbook.py:520-534,1924-2068,2071-2124` |
| `stock_tax_system.xlsx` | Still default output path and test fixture | `stock_tax_app/backend/main.py:21`; `test_stock_tax_app_api.py:17-22` |
| `verify_workbook.py` | Imported by workbook write path | `build_stock_tax_workbook.py:2111-2118` |
| `test_locked_year_roundtrip.py` | Manual but still useful legacy regression for locked-year snapshots | `IMPLEMENTATION_NOTES.md:193-196` and script content itself |
| `docs/openapi.json` | Generated artifact, but current and useful as a contract snapshot | Verified equal to `create_app().openapi()` during audit |

## Unknowns

| Path | Why unknown | What to check |
|---|---|---|
| `docs/API_CONTRACT.md` | Some parts match code, but it still overstates backend authority by hiding workbook dependence | Compare against `REPO_TRUTH_MAP.md` and decide whether to rewrite or archive |
| `ui/DESIGN.md` | Not runtime code, but mixes good product direction with stale endpoint/spec claims | Decide whether to split into `vision` and `archive` docs |
| Root `stock_tax_system.xlsx` after backend-state migration | Today it is required. After migration it might become deleteable or replaceable by a smaller fixture. | Replace test fixture first, then run `py -3 -m pytest -q` without it |

## Commands To Prove A Candidate Is Safe

### Reference scan

```powershell
rg -n "prototype.html|api_samples|README_OPERATOR\.md|IMPLEMENTATION_NOTES\.md|backend_server\.(out|err)\.log|temp\\stock_tax_system.xlsx" -S .
```

### Runtime regression

```powershell
py -3 -m pytest -q
```

### Frontend regression

```powershell
Set-Location ui/frontend
npm run build
```

### Backend/OpenAPI smoke

```powershell
@'
from stock_tax_app.backend.main import create_app
print(sorted(create_app().openapi()["paths"].keys()))
'@ | py -3 -
```

## Recommended Order

1. Delete logs and empty ignored folders whenever convenient.
2. Archive `ui/prototype.html` and stale API sample JSON after docs are rewritten.
3. Do not touch workbook core files or the root workbook fixture until backend-owned state exists and tests are rewritten.

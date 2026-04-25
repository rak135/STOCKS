# Stock Tax Project

Local-first Czech stock tax workflow with a Python calculation engine,
FastAPI backend, and a Vite/React frontend shell.

## One-Click Windows Launcher

Double-click `run_app.bat` in the repository root.

What it does:

- checks required Python/Node tooling
- starts backend (`py -3 -m stock_tax_app.backend.main`)
- starts frontend (Vite dev server with `/api` proxy)
- opens the app in your default browser
- writes logs to `.logs/`

Launcher logs:

- `.logs/launcher.log`
- `.logs/backend.log`
- `.logs/backend.err.log`
- `.logs/frontend.log`
- `.logs/frontend.err.log`

To stop services started by launcher, close the launcher PowerShell window or press `Ctrl+C` in that window.

### Prerequisites (first setup)

```powershell
py -3 -m pip install -r requirements.txt
Set-Location ui/frontend
npm install
```

### Troubleshooting

- If launcher reports missing Python dependencies, run:
	- `py -3 -m pip install -r requirements.txt`
- If backend port `8787` is in use by a non-Stock-Tax process, stop that process and relaunch.
- If frontend fails to start, check `.logs/frontend.log` and `.logs/frontend.err.log`.
- If backend fails health checks, check `.logs/backend.log` and `.logs/backend.err.log`.

## Run in Development

Backend dependency setup (Windows):

```powershell
py -3 -m pip install -r requirements.txt
```

Backend tests:

```powershell
py -3 -m pytest -q
py -3 -m pytest -q test_stock_tax_app_api.py
py -3 -m pytest -q test_project_state_store.py
```

Backend:

```powershell
py -3 -m stock_tax_app.backend.main
```

Frontend:

```powershell
Set-Location ui/frontend
npm install
npm run dev
```

Expected URLs:

- Backend API: `http://127.0.0.1:8787`
- Frontend UI: `http://127.0.0.1:5173`
- OpenAPI schema: `http://127.0.0.1:8787/openapi.json`

See [docs/API_CONTRACT.md](/C:/DATA/PROJECTS/STOCKS/docs/API_CONTRACT.md)
for the frontend/backend contract and [ui/DESIGN.md](/C:/DATA/PROJECTS/STOCKS/ui/DESIGN.md)
for the intended product direction.

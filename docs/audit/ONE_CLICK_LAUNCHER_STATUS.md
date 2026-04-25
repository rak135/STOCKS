# One-Click Launcher Status

Date: 2026-04-25

## Scope

P1.5 only:

- Windows one-click launcher for local frontend-first stack
- backend + frontend startup orchestration
- logging, readiness checks, and child-process cleanup attempts

No Tauri/Electron implementation in this slice.

## Launcher Behavior

Files added:

- `run_app.ps1`
- `run_app.bat`

Main behavior:

- Validates prerequisites (`py`, `node`, `npm`) and Python module availability (`fastapi`, `openpyxl`, `pydantic`).
- Uses backend default host/port `127.0.0.1:8787`.
- If backend port is already in use:
  - reuses service only if `/api/status` responds.
  - otherwise fails clearly with remediation.
- Starts backend with:
  - `py -3 -m stock_tax_app.backend.main`
- Frontend strategy:
  - runs `npm install` only when `ui/frontend/node_modules` is missing.
  - checks whether `dist` is stale and runs `npm run build` only when needed.
  - runs Vite dev server for runtime (`node node_modules/vite/bin/vite.js ...`) because app relies on `/api` proxy in Vite config.
- Chooses a free frontend port when `5173` is occupied.
- Waits for backend and frontend readiness before opening browser.
- Opens default browser to frontend URL (unless `-NoBrowser` is passed).
- Writes logs to `.logs/`.
- Tracks launched child processes and stops them on launcher exit in `finally` block.

## Why Dev Server Runtime Is Used

Current frontend API client calls relative `/api/...` paths.

- Vite dev server has configured proxy for `/api` to backend `8787`.
- Static dist serving would require additional reverse proxy/backend static wiring not in this slice.

So runtime uses Vite dev intentionally, while still building dist opportunistically for production-ish readiness checks.

## Files Changed

- `run_app.ps1`
- `run_app.bat`
- `README.md`
- `docs/audit/ONE_CLICK_LAUNCHER_STATUS.md`

## Commands Run

- `py -3 -m pytest -q`
- `cd ui/frontend && npm run build`
- `./run_app.ps1 -NoBrowser -AutoStopAfterSeconds 8`
- readiness spot checks during launcher run:
  - `http://127.0.0.1:8787/api/status`
  - `http://127.0.0.1:5173/`
  - `http://127.0.0.1:5173/sales-review`

## Results

- Full backend tests: pass
- Frontend build: pass
- Launcher start: pass
- Backend readiness: pass
- Frontend readiness: pass
- `/sales-review` route reachability on frontend host: pass
- Launcher auto-stop cleanup path: executed (child processes stopped by tracked PID)

## Known Limitations

- This is a one-click web launcher, not a true desktop app shell.
- Backend port is fixed to `8787` in backend module run mode; launcher fails clearly if occupied by unrelated process.
- Frontend runtime uses Vite dev server due `/api` proxy dependency.
- Closing the launcher window forcibly may reduce graceful cleanup reliability compared with Ctrl+C/normal exit.

## Status

P1.5 is implemented as a practical one-click Windows launcher for local use.

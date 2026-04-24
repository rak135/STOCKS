# Stock Tax Project

Local-first Czech stock tax workflow with a Python calculation engine,
FastAPI backend, and a Vite/React frontend shell.

## Run in Development

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

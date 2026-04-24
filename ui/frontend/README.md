# Stock Tax Frontend

Vite + React + TypeScript frontend shell for the local stock-tax
workflow.

## Development

```powershell
npm install
npm run dev
```

The Vite dev server runs on `http://127.0.0.1:5173` and proxies `/api`
to the backend at `http://127.0.0.1:8787`.

## Current Scope

- Implemented with real API data:
  - Overview
  - Import
  - Tax Years
- Placeholder routes with stable layout:
  - Sales Review
  - Open Positions
  - FX Rates
  - Audit Pack
  - Settings

The frontend must not parse `stock_tax_system.xlsx`; all business data
comes from the FastAPI backend.

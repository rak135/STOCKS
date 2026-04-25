# Recalculate frontend wiring status

## Endpoint used

- `POST /api/recalculate` via frontend React Query mutation hook `useRecalculateMutation`.
- This action is treated as an explicit operator command, not a passive refresh.

## UI behavior

Top bar action now wires to backend recalculation:

- Button label is `Recalculate` when idle.
- Button tooltip: `Recalculate from current project data. Runs backend calculation and refreshes app data.`
- While request is running:
  - button is disabled
  - icon switches to spinner
  - label becomes `Recalculating...`
- On success:
  - visible top-bar success message: `Recalculation completed. App data refreshed.`
- On error:
  - visible top-bar error message with HTTP status/detail when available
  - existing data remains in place
  - no route/navigation change

## Loading / success / error handling

- Mutation hook: `useRecalculateMutation` in `ui/frontend/src/lib/api.ts`.
- Loading state: driven by `recalculate.isPending`.
- Success state: driven by `recalculate.isSuccess` and success banner text in top bar.
- Error state: driven by `recalculate.isError`; for `ApiError`, message renders as:
  - `Recalculation failed (HTTP <status>: <detail>)` when detail exists
  - `Recalculation failed (HTTP <status>)` otherwise
- Backend error payload parsing was made more robust (`detail`, `message`, or `error`) to avoid dropping useful backend context.

## Query invalidation/refetch list after success

The mutation invalidates these query keys (read endpoints):

- `['status']` → `/api/status`
- `['import']` → `/api/import`
- `['years']` → `/api/years`
- `['sales']` → `/api/sales`
- `['open-positions']` → `/api/open-positions`
- `['fx']` → `/api/fx`
- `['audit']` → `/api/audit`
- `['settings']` → `/api/settings`

No frontend manual tax data mutation is performed.

## Truth semantics

- Successful `POST /api/recalculate` is treated as completion of backend recalculation, not proof that tax state is clean.
- The UI does not fabricate "all good" state.
- Any blocked/needs-review truth continues to surface via existing room queries and truth rendering after refetch.
- No synthetic timestamps or trace counts are invented in frontend.

## Files changed

- `ui/frontend/src/lib/api.ts`
  - Added `toErrorDetail` helper.
  - Added `useRecalculateMutation` (`POST /api/recalculate`) with read-query invalidations.
- `ui/frontend/src/App.tsx`
  - Wired top-bar Recalculate button to mutation.
  - Added pending/success/error UI states and explicit operator-action messaging.
- `docs/audit/RECALCULATE_FRONTEND_STATUS.md`
  - Added this status report.

## Commands run

1. Frontend build

```powershell
cd ui/frontend
npm run build
```

Result: PASS

- `tsc -b && vite build` completed
- Build artifacts generated successfully

2. Optional launcher smoke

```powershell
./run_app.ps1 -NoBrowser -AutoStopAfterSeconds 20
```

Result: PASS

- Backend and frontend started
- App reported ready
- Auto-stop completed cleanly

3. Backend tests

- Not run (backend files were not modified).

## Pass/fail summary

- Recalculate API hook: PASS
- Top-bar wiring: PASS
- Loading/success/error visibility: PASS
- Required query invalidations: PASS
- Truth-preservation semantics: PASS
- Frontend build validation: PASS
- Optional launcher smoke: PASS

## Remaining gaps

- No dedicated toast system was introduced; feedback is shown inline in top bar (still visible and explicit per requirement).
- No request-cancellation UX was added for long-running recalculations (not requested).
- Final UX copy is currently tooltip + inline text only; if desired later, a small confirmation modal could be added before triggering workbook-writing recalculation.

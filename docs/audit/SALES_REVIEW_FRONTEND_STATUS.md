# Sales Review Frontend Status

Date: 2026-04-25

## Implemented

Implemented a real Sales Review operator screen and replaced the placeholder route for `/sales-review`.

The screen is backed by:

- `GET /api/sales`
- `GET /api/sales/{sell_id}`
- `PATCH /api/sales/{sell_id}/review`

## Route Change

Updated frontend routing so `/sales-review` now renders `SalesReviewScreen` instead of `ComingNextScreen`.

No other placeholder routes were changed.

## API Endpoints Used

- Sales list query: `GET /api/sales`
- Sale detail query: `GET /api/sales/{sell_id}`
- Review mutation: `PATCH /api/sales/{sell_id}/review`

## Truth Metadata Displayed

### Collection truth (top banner)

Displays `SellList.truth` with:

- `status` as visual state (`ready`, `needs_review`, `partial`, `blocked`, `unknown`, `not_implemented`)
- `summary`
- `reasons`
- `sources`
- `empty_meaning`

### Empty state handling

Uses backend `truth.empty_meaning` to distinguish:

- `no_data`
- `blocked`
- `unknown`
- `not_implemented`

The UI does not treat blocked/unknown/not_implemented empties as ordinary no-data.

### Per-row and per-detail provenance

Visible chips/badges are rendered for:

- `truth_status`
- `instrument_map_source`
- `review_state_source`

This includes explicit visibility of values such as `workbook_fallback` and `generated_default`.

## Review Mutation Behavior

Review controls in detail panel:

- status selector using backend-supported statuses (`unreviewed`, `reviewed`, `flagged`)
- note textarea
- save button

Save behavior:

- sends PATCH to `/api/sales/{sell_id}/review`
- updates selected detail cache from mutation response
- invalidates/refetches sales list query for consistency
- shows visible success/failure message

Error handling includes:

- list loading failure (`/api/sales`)
- detail loading failure (`/api/sales/{sell_id}`)
- 404 detail/mutation cases (unknown sale id)
- review PATCH failure with HTTP detail when available

## Files Changed

- `ui/frontend/src/screens/sales-review-screen.tsx`
- `ui/frontend/src/App.tsx`
- `ui/frontend/src/lib/api.ts`
- `ui/frontend/src/types/api.ts`
- `docs/audit/SALES_REVIEW_FRONTEND_STATUS.md`

## Validation Run

### 1) Frontend TypeScript build

Command:

`cd ui/frontend && npm run build`

Result:

- Pass
- `tsc -b` completed
- `vite build` completed

### 2) Python suite

Command:

`py -3 -m pytest -q`

Result:

- Fails during collection in current environment
- Missing dependencies: `openpyxl`, `fastapi`

### 3) Backend smoke

Target command intent:

- create app via `stock_tax_app.backend.main.create_app`
- call `/api/status` and `/api/sales`

Result in current environment:

- Fails before requests due to missing `fastapi`

## Remaining Gaps

- No frontend automated tests were added because no frontend test tooling/files currently exist in `ui/frontend/src`.
- Validation of Python suite and backend smoke requires Python dependencies (`fastapi`, `openpyxl`) installed in the active interpreter.
- Sales list currently cannot show cost basis/gain-loss directly in list rows because backend list model (`SellSummary`) does not expose those fields; UI marks these as not available from backend and shows full values in detail.

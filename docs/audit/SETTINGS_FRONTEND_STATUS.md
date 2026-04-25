# Settings frontend wiring (display-only)

## Endpoint used

- `GET /api/settings` → `AppSettings` (`{ project_folder, csv_folder, output_path, cache_folder, default_tax_rate, default_fx_method, default_100k, unmatched_qty_tolerance, position_reconciliation_tolerance, backup_on_recalc, require_confirm_unlock, keep_n_snapshots, excel_validation, truth_status, status_reasons, field_meta, domain_sources }`).

No mutation endpoint is consumed. No PATCH/POST/PUT request is issued.

## What was implemented

Replaced the `/settings` `ComingNextScreen` placeholder with a real, **display-only** cockpit room backed by `GET /api/settings`.

Layout (top → bottom):

1. `SectionHeader` — title `Settings`, subtitle "Local app configuration. This view is display-only — no settings mutation endpoint exists.", with a disabled `Save not wired` action button on the right.
2. **Display-only truth banner** — `truth_status` chip + dot, `Display-only` chip, `Editing not implemented` chip, plain-language explanation, structured reasons list when present.
3. **Paths fieldset** — `project_folder`, `csv_folder`, `output_path`, `cache_folder` (mono inputs).
4. **Calculation defaults fieldset** — `default_tax_rate` (rendered as a percentage), `default_fx_method` (humanised to `CNB daily` / `GFŘ yearly`), `default_100k`.
5. **Tolerances fieldset** — `unmatched_qty_tolerance`, `position_reconciliation_tolerance`.
6. **Backup & lock policy fieldset** — `backup_on_recalc`, `require_confirm_unlock`, `keep_n_snapshots`.
7. **Validation fieldset** — `excel_validation`.
8. **Domain ownership section** — non-canonical-source warning card (when applicable) plus a full domain → source table.

Every field input is rendered with `readOnly disabled` and a tooltip explaining "Settings are display-only. No mutation endpoint is wired." There is no local dirty state, no `onChange` handler, and no submit path.

## Display-only / editability handling

- The header right-side action is a disabled button labeled `Save not wired`. There is no enabled save state in any code path.
- The truth banner shows two filed-tone chips next to the truth-status chip: `Display-only` and `Editing not implemented`.
- Every field input is `disabled readOnly` and visually de-emphasised (`bg-bg`, `text-ink2`, `cursor-not-allowed`).
- The screen never constructs an editable element. No checkboxes, no dropdowns, no number spinners.
- Field labels are rendered above their inputs together with a row of metadata chips drawn from `field_meta`:
  - `editability` chip — `Editable` (ok), `Read-only` (neutral), `Display-only` (filed), `Not implemented` (filed).
  - `source` chip — color-coded per `TruthSource`, with `workbook_fallback` and `generated_default` rendered as warn and `unavailable` as err.
  - `status` chip + dot — only shown when the field's status is non-`ready`, to keep the row tight without hiding any non-trivial truth.
  - `reason` rendered as italic ink3 text under the input when set.
- When the backend does not provide `field_meta` for a given key, a filed `no field metadata` chip is shown instead so the operator never sees a row whose provenance is silently absent.

## `field_meta` display

Every key in the prototype's settings layout is wired to its corresponding `field_meta[name]` entry by name (e.g. `project_folder`, `default_tax_rate`, `excel_validation`). Per-field, the chips and reason render from the live backend metadata — there is no client-side fallback that pretends a field is editable when the backend says it is not.

## `domain_sources` display

Two layers, deliberately not buried:

1. **Non-canonical domains card** (warn-toned, `border-warn-bg bg-warn-bg/30`) — only rendered when at least one domain reports `workbook_fallback`, `generated_default`, or `unavailable`. Each flagged domain is shown as a warn/err chip with the form `<domain> · <source label>`. The card body explains that "they must remain visible until they are migrated."
2. **Domain → source table** — every domain shown grouped by source, sources ordered canonical first (`project_state, ui_state, cnb_cache, calculated, static_config`) and non-canonical last (`workbook_fallback, generated_default, unavailable`). Source cells are tone-coded chips; domain names are mono pills.

When `domain_sources` is empty, the section is omitted (no false reassurance).

## Disabled / not-wired actions

| Action | Visibility | Reason |
| --- | --- | --- |
| Section-level `Save not wired` | Disabled with tooltip | No backend settings mutation endpoint exists. |

No per-field "Edit" affordances are rendered. No "Reset", "Reload", or "Apply" buttons are rendered. Inputs are inert.

## Files changed

- `ui/frontend/src/types/api.ts` — added `SettingEditability`, `SettingFieldTruth`, `ExcelValidation`, `AppSettings`.
- `ui/frontend/src/lib/api.ts` — added `useSettingsQuery` against `GET /api/settings`.
- `ui/frontend/src/screens/settings-screen.tsx` — **new.** Full Settings room.
- `ui/frontend/src/App.tsx` — `/settings` now renders `<SettingsScreen />`. The unused `ComingNextScreen` import was removed since every route is now wired to a real screen. No other routes touched.

No backend files were modified.

## Commands run

```
cd ui/frontend
npm run build
```

Result: ✅ pass.

```
> stock-tax-frontend@0.0.0 build
> tsc -b && vite build

vite v8.0.10 building client environment for production...
✓ 1736 modules transformed.
dist/index.html                   0.46 kB │ gzip:   0.30 kB
dist/assets/index-CC3dHidj.css   25.15 kB │ gzip:   5.41 kB
dist/assets/index-DSq7oHg6.js   402.66 kB │ gzip: 118.42 kB
✓ built in 343ms
```

Backend was not touched, so backend tests were not re-run.

## Remaining gaps

- No `PATCH /api/settings` (or equivalent) exists, so the room remains display-only end-to-end.
- The screen does not surface the *reason* text from `field_meta` as a chip — only as italic body copy under the input. A chip would be louder, but the brief asked for compact rows.
- `default_tax_rate` is shown as a percentage; the underlying rate (`0.15`) is not surfaced because the backend already returns the canonical value and the percent rendering matches the operator's mental model. If exact decimal inspection becomes important, it could be added as a secondary line.
- Domain ownership is rendered as a flat domain → source table; nested groupings (e.g. by feature area) are not introduced.
- `excel_validation` value is shown verbatim (`strict` / `warn` / `off`); no humanisation, since the literal value is already operator-readable.

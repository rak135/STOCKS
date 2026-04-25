# Engine Extraction Phase Plan

Date: 2026-04-25  
Baseline: 3806 lines in `build_stock_tax_workbook.py`, 82 tests passing.  
Prior extraction: `corporate_actions.py` already extracted (committed separately).

## Established Pattern

Extracted modules:
- Accept `List[Any]` or `Any` for types defined in the monolith (Lot, Transaction, MatchLine, RawRow)
- Receive callable utilities (e.g. `parse_trade_date`, `safe_float`) as injected parameters
- Are pure functions with no imports from `build_stock_tax_workbook`
- Live under `stock_tax_app/engine/`

Monolith wrappers:
- Thin single-call delegations that pass monolith-local types to the new module
- Keep the same public signature the rest of the codebase uses
- No logic changes

---

## Phase 2 — open_positions.py

**New module:** `stock_tax_app/engine/open_positions.py`

**Candidate functions to move:**
| Function | Monolith line | Notes |
|---|---|---|
| `extract_position_rows` | 3220 | Thin wrapper over `_with_provenance` |
| `extract_position_rows_with_provenance` | 3229 | Core; needs `safe_float`, `parse_trade_date` injected |
| `build_open_position_rows` | 1819 | Needs `Lot` as `Any`, `RawRow` as `Any` |
| `_symbol_by_instrument` | 3213 | Helper; keep in monolith as it's only used by workbook write |

**Dependency injection needed:**
- `safe_float: Callable[[str, Any], Tuple[Optional[float], bool]]`
- `parse_trade_date: Callable[[str], Optional[date]]`

**Types used via duck-typing (`Any`):**
- `RawRow` — accessed via `.data`, `.source_file`, `.source_row`, `.source_broker`, `.source_account`
- `Lot` — accessed via `.instrument_id`, `.quantity_remaining`

**Wrappers remaining in build_stock_tax_workbook.py:**
- `extract_position_rows(raw_rows, instrument_map)` → delegates to new module, passes `safe_float`, `parse_trade_date`
- `extract_position_rows_with_provenance(raw_rows, instrument_map)` → same
- `build_open_position_rows(raw_rows, instrument_map, lots)` → same

**Tests to run:**
```
py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_exact_match_is_ok_and_ready
py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_warn_difference_creates_needs_review_and_status_check
py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_material_difference_blocks_collection_and_surfaces_audit_reason
py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_missing_reported_position_is_unknown_not_ok
py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_provenance_missing_snapshot_date_is_honest
py -3 -m pytest -q test_stock_tax_app_api.py::test_open_positions_multiple_reported_rows_expose_ambiguity_and_source_count
py -3 -m pytest -q
```

**Risk:** LOW — pure functions, no side effects, well-covered by tests.

**Stop conditions:** Any test failure.

---

## Phase 3 — checks.py

**New module:** `stock_tax_app/engine/checks.py`

**Candidate functions to move:**
| Function | Monolith line | Notes |
|---|---|---|
| `build_check_rows` | 1891 | Large; references `SUPPORTED_METHODS`, `FXResolver` |

**Note:** `_check_level`, `_check_href`, `_frontend_ready_href` already live in `core.py`. Do not move them again. Only move `build_check_rows` from the monolith.

**Dependency injection needed:**
- `supported_methods: Tuple[str, ...]` — pass `policy.SUPPORTED_METHODS`

**Types used via duck-typing (`Any`):**
- `FXResolver` — accessed via `.missing_daily`, `.missing_yearly`
- `MatchLine` — accessed via `.sell_date`, `.buy_date`
- `Lot` — accessed via `.lot_id`, `.quantity_remaining`, `.source_file`, `.source_row`

**Wrappers remaining:**
- `build_check_rows(...)` in monolith → delegates to new module, passes `SUPPORTED_METHODS`

**Tests to run:**
```
py -3 -m pytest -q test_stock_tax_app_api.py
py -3 -m pytest -q
```

**Risk:** LOW-MEDIUM — large function, many branches; test coverage is good.

**Stop conditions:** Any test failure.

---

## Phase 4 — fx.py

**New module:** `stock_tax_app/engine/fx.py`

**Candidate constants/functions to move:**
| Symbol | Monolith line | Notes |
|---|---|---|
| `DEFAULT_FX_YEARLY` | 76 | Authoritative GFŘ rates dict |
| `GFR_OFFICIAL_RATES` | 86 | Source labels dict |
| `DEFAULT_FX_METHOD` | 66 | Constant |
| `SUPPORTED_FX_METHODS` | 67 | Constant |
| `CNB_DAILY_CACHE_FILE` | 96 | Constant |
| `_cnb_cache_path` | 833 | Needs `Path` only |
| `_load_cnb_cache` | 837 | Pure |
| `_save_cnb_cache` | 848 | Pure |
| `download_cnb_daily_rates_year` | 856 | Network; pure logic |
| `refresh_fx_daily_for_years` | 896 | Pure; calls cache helpers |
| `FXResolver` | 944 | Core FX lookup class |
| `collect_required_fx_problems` | 989 | Pure; uses `FXResolver` |
| `build_fx_tables` | 605 | Needs `parse_trade_date` injected |

**Dependency injection needed:**
- `parse_trade_date: Callable[[str], Optional[date]]` — injected into `build_fx_tables`

**Wrappers remaining:**
- `DEFAULT_FX_YEARLY`, `GFR_OFFICIAL_RATES`, `DEFAULT_FX_METHOD`, `SUPPORTED_FX_METHODS`, `CNB_DAILY_CACHE_FILE` — re-exported as aliases in monolith  
- `FXResolver` — re-exported as alias in monolith
- `build_fx_tables(...)` — thin wrapper passing `parse_trade_date`
- `collect_required_fx_problems(...)` — thin wrapper
- All `_cnb_*` functions — re-exported or called via wrapper
- `refresh_fx_daily_for_years(...)` — thin wrapper

**Tests to run:**
```
py -3 -m pytest -q test_stock_tax_app_api.py -k "fx or FX or missing"
py -3 -m pytest -q test_project_state_store.py
py -3 -m pytest -q
```

**Risk:** MEDIUM — FXResolver is used throughout core.py and the API path; strict no-fallback behavior must be preserved.

**Stop conditions:** Any test failure.

---

## Phase 5 — matching.py

**New module:** `stock_tax_app/engine/matching.py`

**Candidate functions to move:**
| Function | Monolith line | Notes |
|---|---|---|
| `_add_years` | 1078 | Pure date helper |
| `_expected_contribution_per_share_czk` | 1061 | Scoring helper; needs FXResolver as Any |
| `rank_lots_for_sell` | 1086 | FIFO/LIFO/MIN_GAIN/MAX_GAIN ranker |
| `_make_match_line` | 1117 | Core match builder |
| `_match_global_optimized` | 1169 | Annual global optimizer |
| `match_sell` | 1275 | Per-sell FIFO/LIFO |
| `_lots_from_frozen` | 1301 | Deserializes frozen inventory |
| `simulate` | 1335 | Main lot simulation |
| `_clone_lots` | 1603 | Pure helper |
| `_coerce_date` | 1608 | Pure date helper |

**Dependency injection needed:**
- `apply_corporate_action_to_lots` — already in `corporate_actions.py`, import directly
- `parse_trade_date: Callable` — injected into `_lots_from_frozen` or `_coerce_date`
- `FXResolver` — import from `fx.py` (after Phase 4)
- `default_method_for: Callable` — from `policy`

**Types used via duck-typing (`Any`):**
- `Lot`, `Transaction`, `MatchLine` — constructed/accessed via attributes
- Since `MatchLine` is constructed by `_make_match_line`, we need either a factory or to import the class

**Design decision:** `MatchLine` is a dataclass from the monolith. For matching.py to construct `MatchLine` objects, we either:
1. Accept a `match_line_factory: Callable[..., Any]` parameter in `_make_match_line`
2. Move `MatchLine` (and `Lot`) to a shared module

**Decision:** Use factory injection for `MatchLine` construction. The wrapper in the monolith passes `MatchLine` as the factory.

**Wrappers remaining:**
- `match_sell(...)` — thin wrapper
- `simulate(...)` — thin wrapper passing `MatchLine` factory and `parse_trade_date`
- `_lots_from_frozen(...)` — thin wrapper passing `Lot` factory

**Tests to run:**
```
py -3 -m pytest -q test_min_gain_optimality.py
py -3 -m pytest -q test_stock_tax_app_api.py -k "sales or method or match or gain or year"
py -3 -m pytest -q test_stock_tax_app_api.py
py -3 -m pytest -q
```

**Risk:** HIGH — `simulate` is the core engine; any behavior change is critical. No rewrites.

**Stop conditions:** Any test failure.

---

## Phase 6 — tax_summary.py

**New module:** `stock_tax_app/engine/tax_summary.py`

**Candidate functions to move:**
| Function | Monolith line | Notes |
|---|---|---|
| `build_yearly_summary` | 1624 | Pure; needs constants |
| `run_method_comparison` | 1724 | Calls `simulate` and `build_yearly_summary` |
| `split_audit` | 1782 | Heuristic; uses `Transaction` as Any |

**Constants needed:**
- `DEFAULT_TAX_RATE`, `DEFAULT_APPLY_100K`, `DEFAULT_100K_THRESHOLD`, `DEFAULT_FX_METHOD` — pass as defaults or import from fx.py
- `SUPPORTED_METHODS` — import from `policy`

**Dependency injection for `run_method_comparison`:**
- `simulate_fn: Callable` — injected (calls simulate from matching.py or monolith wrapper)

**Types via duck-typing:**
- `MatchLine` attributes accessed but not constructed
- `Transaction` — only `.instrument_id` accessed in `split_audit`

**Wrappers remaining:**
- `build_yearly_summary(...)` — thin wrapper
- `run_method_comparison(...)` — thin wrapper passing `simulate` and `build_yearly_summary`
- `split_audit(...)` — thin wrapper

**Tests to run:**
```
py -3 -m pytest -q test_stock_tax_app_api.py -k "year or tax or exemption or audit"
py -3 -m pytest -q test_stock_tax_app_api.py
py -3 -m pytest -q
```

**Risk:** MEDIUM — tax formulas and 100k exemption must not change.

**Stop conditions:** Any test failure.

---

## Phase 7 — workbook_export.py

**New module:** `stock_tax_app/engine/workbook_export.py`

**Candidate functions to move:**
All workbook write functions (~lines 2228–3806):
- `write_calculation_result`, `write_workbook`
- `_tmp_output_path`, `_backup_existing_output`, `_replace_output_or_fail`
- All `_write_*` sheet writers (~21 functions)
- Excel styling constants: `HEADER_FONT`, `HEADER_FILL`, `SUBHEADER_FILL`, `EDITABLE_FILL`, `LOCKED_FILL`, `ERROR_FILL`, `WARNING_FILL`, `OK_FILL`, `THIN`, `BORDER`, `WRAP_LEFT`, `CENTER`
- Workbook helpers: `autosize_columns`, `write_header`, `add_table`

**Imports needed in new module:**
- openpyxl types directly (no monolith dependency)
- `Lot`, `MatchLine`, `RawRow`, `CalculationResult` — as `Any` types for write functions
- `build_open_position_rows` — from `open_positions.py` (Phase 2)
- `_symbol_by_instrument` — move into new module or keep in monolith

**Wrappers remaining:**
- `write_workbook(...)` — thin wrapper
- `write_calculation_result(...)` — thin wrapper
- Styling constants re-exported as aliases (or just let call sites import from new module)
- `autosize_columns`, `write_header`, `add_table` — re-exported

**Tests to run:**
```
py -3 -m pytest -q test_project_state_store.py
py -3 -m pytest -q test_stock_tax_app_api.py
py -3 -m pytest -q
py -3 test_locked_year_roundtrip.py
```

**Risk:** HIGH — workbook layout must not change; openpyxl API usage must remain identical.

**Stop conditions:** Any test failure; any workbook sheet layout change.

---

## Overall Stop Conditions

1. Any test failure after a phase.
2. Import cycle that cannot be resolved without logic changes.
3. Need to change business behavior to complete extraction.
4. Uncertainty about workbook sheet compatibility.
5. Any frontend/API contract break.

## Approximate Expected Reduction by Phase

| Phase | Functions Moved | Approx Lines Removed |
|---|---|---|
| 2: open_positions | 3 | ~100 |
| 3: checks | 1 large | ~150 |
| 4: fx | 12 | ~450 |
| 5: matching | 10 | ~580 |
| 6: tax_summary | 3 | ~200 |
| 7: workbook_export | 25+ | ~1600 |
| **Total** | **54+** | **~3080** |

Estimated post-extraction monolith size: ~700–900 lines (imports, data classes, thin wrappers, `calculate_workbook_data`, `main`).

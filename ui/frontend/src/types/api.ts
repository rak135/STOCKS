export type Check = {
  id: string
  level: 'error' | 'warn' | 'info'
  message: string
  year: number | null
  sell_id: string | null
  href: string
}

export type TruthStatus = 'ready' | 'needs_review' | 'blocked' | 'partial' | 'unknown' | 'not_implemented'

export type TruthReason = {
  code: string
  message: string
}

export type TruthSource =
  | 'project_state'
  | 'ui_state'
  | 'workbook_fallback'
  | 'calculated'
  | 'generated_default'
  | 'cnb_cache'
  | 'static_config'
  | 'unavailable'

export type CollectionTruth = {
  status: TruthStatus
  reasons: TruthReason[]
  sources: TruthSource[]
  summary: string | null
  item_count: number
  empty_meaning: 'not_empty' | 'no_data' | 'blocked' | 'unknown' | 'not_implemented'
}

export type TruthMeta = {
  status: TruthStatus
  reasons: TruthReason[]
  sources: TruthSource[]
  summary: string | null
}

export type NextAction = {
  label: string
  href: string
}

export type AppStatus = {
  project_path: string
  csv_folder: string
  output_path: string
  last_calculated_at: string | null
  global_status: 'ready' | 'needs_review' | 'blocked'
  truth_status: TruthStatus
  next_action: NextAction | null
  unresolved_checks: Check[]
  status_reasons: TruthReason[]
  workbook_backed_domains: string[]
}

export type ImportFile = {
  name: string
  broker: string
  account: string
  account_currency: string | null
  total_rows: number
  trade_rows: number
  ignored_rows: number
  position_rows: number
  min_trade_date: string | null
  max_trade_date: string | null
  unique_symbols: string[]
  warnings: string[]
  status: 'ok' | 'warnings' | 'error'
}

export type ImportSummary = {
  folder: string
  files: ImportFile[]
  total_trade_rows: number
  total_ignored_rows: number
  total_warnings: number
  truth: TruthMeta
}

export type MethodComparison = {
  FIFO: number
  LIFO: number
  MIN_GAIN: number
  MAX_GAIN: number
}

export type TaxYear = {
  year: number
  method: 'FIFO' | 'LIFO' | 'MIN_GAIN' | 'MAX_GAIN' | 'MIXED'
  filed_method: 'FIFO' | 'LIFO' | 'MIN_GAIN' | 'MAX_GAIN' | 'MIXED' | null
  fx_method: 'FX_DAILY_CNB' | 'FX_UNIFIED_GFR'
  tax_rate: number
  exemption_100k: boolean
  gross_proceeds_czk: number
  exempt_proceeds_czk: number
  taxable_gains_czk: number
  taxable_losses_czk: number
  taxable_base_czk: number
  tax_due_czk: number
  match_line_count: number
  filed: boolean
  locked: boolean
  show_method_comparison: boolean
  filed_tax_input_czk: number | null
  reconciliation_status: 'not_filed' | 'reconciled' | 'needs_attention' | 'accepted_with_note'
  reconciliation_note: string | null
  method_comparison: MethodComparison | null
  truth_status: TruthStatus
  settings_source: string
  method_source: string
  reconciliation_source: string
}

export type TaxYearsResponse = {
  items: TaxYear[]
  truth: CollectionTruth
}

export type YearPatchRequest = {
  method?: 'FIFO' | 'LIFO' | 'MIN_GAIN' | 'MAX_GAIN'
  fx_method?: 'FX_DAILY_CNB' | 'FX_UNIFIED_GFR'
  tax_rate?: number
  apply_100k_exemption?: boolean
}

export type ReviewStatus = 'unreviewed' | 'reviewed' | 'flagged'

export type SellClassification = 'taxable' | 'exempt' | 'mixed'

export type SourceRef = {
  file: string
  row: number
}

export type MatchedLot = {
  lot_id: string
  buy_date: string
  broker: string
  source: SourceRef
  quantity: number
  buy_price_usd: number
  sell_price_usd: number
  fx_buy: number
  fx_sell: number
  cost_basis_czk: number
  proceeds_czk: number
  holding_days: number
  time_test_exempt: boolean
  gain_loss_czk: number
}

export type SellSummary = {
  id: string
  sell_id: string
  year: number
  date: string
  ticker: string
  instrument_id: string
  broker: string
  quantity: number
  price_usd: number
  proceeds_czk: number
  total_gain_loss_czk: number
  total_cost_basis_czk: number
  method: 'FIFO' | 'LIFO' | 'MIN_GAIN' | 'MAX_GAIN' | 'MIXED'
  matched_quantity: number
  unmatched_quantity: number
  classification: SellClassification
  review_status: ReviewStatus
  truth_status: TruthStatus
  instrument_map_source: TruthSource
  review_state_source: TruthSource
}

export type Sell = SellSummary & {
  source: SourceRef
  note: string
  matched_lots: MatchedLot[]
  truth: TruthMeta
}

export type SellList = {
  items: SellSummary[]
  truth: CollectionTruth
}

export type SellReviewPatchRequest = {
  review_status: ReviewStatus | null
  note: string | null
}

export type FxMethod = 'FX_DAILY_CNB' | 'FX_UNIFIED_GFR'

export type FxYear = {
  year: number
  method: FxMethod
  unified_rate: number | null
  daily_cached: number
  daily_expected: number
  missing_dates: string[]
  source_label: string
  source_url: string | null
  verified_at: string | null
  manual_override: boolean
  locked: boolean
  truth_status: TruthStatus
  rate_source: TruthSource
  status_reason: string | null
}

export type FxYearList = {
  items: FxYear[]
  truth: CollectionTruth
}

export type OpenPositionStatus = 'ok' | 'warn' | 'error' | 'unknown'

export type OpenLot = {
  lot_id: string
  buy_date: string
  broker: string
  quantity: number
  cost_basis_czk: number
  unrealised_pl_czk: number | null
}

export type ReportedPositionSourceStatus = 'ready' | 'partial' | 'unknown'

export type ReportedPositionSource = {
  source_file: string
  source_row: number
  broker: string | null
  account: string | null
  snapshot_date: string | null
  source_type: 'csv_position_row'
}

export type OpenPosition = {
  ticker: string
  instrument_id: string
  calculated_qty: number
  reported_qty: number | null
  yahoo_qty: number | null
  difference: number | null
  tolerance: number | null
  status: OpenPositionStatus
  lots: OpenLot[]
  truth_status: TruthStatus
  status_reason_code: string | null
  status_reason: string | null
  instrument_map_source: TruthSource
  inventory_source: TruthSource
  reported_position_source_file: string | null
  reported_position_source_row: number | null
  reported_position_broker: string | null
  reported_position_account: string | null
  reported_position_snapshot_date: string | null
  reported_position_source_type: string
  reported_position_source_status: ReportedPositionSourceStatus
  reported_position_source_reason: string | null
  reported_position_source_count: number
  reported_position_sources: ReportedPositionSource[]
}

export type OpenPositionList = {
  items: OpenPosition[]
  truth: CollectionTruth
}

export type AuditSummary = {
  year_rows: TaxYear[]
  trace_counts: Record<string, number>
  locked_snapshots: number[]
  truth_status: TruthStatus
  summary_only: boolean
  status_reasons: TruthReason[]
  workbook_backed_domains: string[]
}

export type SettingEditability = 'editable' | 'read_only' | 'display_only' | 'not_implemented'

export type SettingFieldTruth = {
  editability: SettingEditability
  source: TruthSource
  status: TruthStatus
  reason: string | null
}

export type ExcelValidation = 'strict' | 'warn' | 'off'

export type AppSettings = {
  project_folder: string
  csv_folder: string
  output_path: string
  cache_folder: string
  default_tax_rate: number
  default_fx_method: FxMethod
  default_100k: boolean
  unmatched_qty_tolerance: number
  position_reconciliation_tolerance: number
  backup_on_recalc: boolean
  require_confirm_unlock: boolean
  keep_n_snapshots: number
  excel_validation: ExcelValidation
  truth_status: TruthStatus
  status_reasons: TruthReason[]
  field_meta: Record<string, SettingFieldTruth>
  domain_sources: Record<string, TruthSource>
}

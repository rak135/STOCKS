export type Check = {
  id: string
  level: 'error' | 'warn' | 'info'
  message: string
  year: number | null
  sell_id: string | null
  href: string
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
  next_action: NextAction | null
  unresolved_checks: Check[]
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
}

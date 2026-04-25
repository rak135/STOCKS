import { useEffect, useMemo, useState } from 'react'
import { Check, Lock } from 'lucide-react'
import { Button, Card, Chip, KeyVal, SectionHeader } from '../components/ui'
import { ApiError, usePatchYearMutation, useYearsQuery } from '../lib/api'
import { formatCurrency } from '../lib/format'
import type { TaxYear } from '../types/api'

const METHOD_OPTIONS = ['FIFO', 'LIFO', 'MIN_GAIN', 'MAX_GAIN'] as const
const FX_METHOD_OPTIONS = ['FX_UNIFIED_GFR', 'FX_DAILY_CNB'] as const

export function TaxYearsScreen() {
  const { data, isLoading, error } = useYearsQuery()

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Tax Years" subtitle="Loading per-year policy from backend." />
        <div className="space-y-3">
          <div className="h-32 animate-pulse rounded-xl bg-borderc/50" />
          <div className="h-32 animate-pulse rounded-xl bg-borderc/50" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Tax Years" subtitle="Backend years endpoint is required." />
        <Card className="p-5 border-err-bg">
          <div className="text-sm text-err">
            Could not load <span className="font-mono">/api/years</span>.
          </div>
        </Card>
      </div>
    )
  }

  const years = [...data.items].sort((a, b) => b.year - a.year)

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <SectionHeader
        title="Tax Years"
        subtitle="Method, FX, 100k exemption, filed status, and locking — per year."
      />
      {years.length === 0 ? (
        <Card className="p-6 text-sm text-ink3">{data.truth.summary ?? 'Tax years are not available.'}</Card>
      ) : (
        <div className="space-y-5">
          {years.map((y) => (
            <YearPanel key={y.year} y={y} />
          ))}
        </div>
      )}
    </div>
  )
}

function YearPanel({ y }: { y: TaxYear }) {
  const isLocked = y.locked
  const patchMutation = usePatchYearMutation()
  const [method, setMethod] = useState<(typeof METHOD_OPTIONS)[number]>('FIFO')
  const [fxMethod, setFxMethod] = useState<(typeof FX_METHOD_OPTIONS)[number]>('FX_UNIFIED_GFR')
  const [taxRatePercent, setTaxRatePercent] = useState('15')
  const [exemption100k, setExemption100k] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  useEffect(() => {
    const resolvedMethod = METHOD_OPTIONS.includes(y.method as (typeof METHOD_OPTIONS)[number])
      ? (y.method as (typeof METHOD_OPTIONS)[number])
      : 'FIFO'
    const resolvedFxMethod = FX_METHOD_OPTIONS.includes(y.fx_method)
      ? y.fx_method
      : 'FX_UNIFIED_GFR'
    setMethod(resolvedMethod)
    setFxMethod(resolvedFxMethod)
    setTaxRatePercent((y.tax_rate * 100).toFixed(2))
    setExemption100k(y.exemption_100k)
    setLocalError(null)
  }, [y.method, y.fx_method, y.tax_rate, y.exemption_100k])

  const normalizedTaxRateInput = taxRatePercent.trim().replace(',', '.')
  const parsedTaxRatePercent = normalizedTaxRateInput === '' ? Number.NaN : Number(normalizedTaxRateInput)
  const hasValidTaxRate = Number.isFinite(parsedTaxRatePercent) && parsedTaxRatePercent >= 0
  const draftTaxRateDecimal = hasValidTaxRate ? parsedTaxRatePercent / 100 : y.tax_rate
  const isDirty =
    method !== y.method ||
    fxMethod !== y.fx_method ||
    Math.abs(draftTaxRateDecimal - y.tax_rate) > 1e-12 ||
    exemption100k !== y.exemption_100k
  const mutationError = patchMutation.error instanceof ApiError ? patchMutation.error.detail : null
  const canSave = !isLocked && isDirty && hasValidTaxRate && !patchMutation.isPending
  const saveStateText = useMemo(() => {
    if (patchMutation.isPending) return 'Saving...'
    if (savedAt !== null) return 'Saved'
    return null
  }, [patchMutation.isPending, savedAt])

  async function handleSave() {
    if (!hasValidTaxRate) {
      setLocalError('Tax rate must be a numeric percent >= 0.')
      return
    }
    setLocalError(null)
    try {
      await patchMutation.mutateAsync({
        year: y.year,
        payload: {
          method,
          fx_method: fxMethod,
          tax_rate: parsedTaxRatePercent / 100,
          apply_100k_exemption: exemption100k,
        },
      })
      setSavedAt(Date.now())
    } catch {
      // The backend error is rendered from mutation state.
    }
  }

  const reconTone =
    y.reconciliation_status === 'reconciled'
      ? 'ok'
      : y.reconciliation_status === 'needs_attention'
        ? 'warn'
        : y.reconciliation_status === 'accepted_with_note'
          ? 'info'
          : 'neutral'
  const reconLabel = y.reconciliation_status.replaceAll('_', ' ')

  return (
    <Card className={`${isLocked ? 'bg-filed-bg/30' : ''} overflow-hidden`}>
      <div className="flex items-center gap-4 px-5 py-4 border-b border-borderc">
        <div className="text-[20px] font-semibold tracking-tight text-ink w-20">{y.year}</div>
        {isLocked ? (
          <Chip tone="filed">
            <Lock className="w-3 h-3" />
            Filed · Locked · {y.filed_method ?? y.method}
          </Chip>
        ) : (
          <Chip tone="neutral">Draft</Chip>
        )}
        <div className="flex-1" />
        <KeyVal label="Tax due" className="text-right">
          {formatCurrency(y.tax_due_czk)}
        </KeyVal>
      </div>

      <div className="grid grid-cols-2 gap-6 p-5">
        {/* LEFT: editable settings for unlocked years */}
        <div className="space-y-4">
          <div>
            <label className="text-[11px] uppercase tracking-wider text-ink3">Method policy</label>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              {METHOD_OPTIONS.map((m) => {
                return (
                  <button
                    key={m}
                    type="button"
                    disabled={isLocked || patchMutation.isPending}
                    onClick={() => setMethod(m)}
                    className={`px-2.5 py-1 rounded-md text-xs border ${
                      method === m
                        ? 'bg-accent-bg border-accent-bg text-accent font-medium'
                        : 'bg-surface border-borderc text-ink2'
                    } ${isLocked ? 'opacity-50 cursor-not-allowed' : 'hover:bg-bg'} `}
                    title={isLocked ? 'Filed/locked years cannot be changed.' : 'Select method and save.'}
                  >
                    {m}
                  </button>
                )
              })}
              {isLocked ? (
                <Chip tone="filed" className="ml-2">
                  Filed under {y.filed_method ?? y.method}
                </Chip>
              ) : null}
            </div>
            <div className="text-[11px] text-ink3 mt-1">Source: {y.method_source}</div>
          </div>

          <div className="grid grid-cols-2 gap-4 items-end">
            <div>
              <label className="text-[11px] uppercase tracking-wider text-ink3">FX method</label>
              <select
                className="mt-1 w-full rounded-md border border-borderc bg-surface px-2.5 py-2 text-sm text-ink focus-ring disabled:opacity-50 disabled:cursor-not-allowed"
                value={fxMethod}
                disabled={isLocked || patchMutation.isPending}
                onChange={(e) => setFxMethod(e.target.value as (typeof FX_METHOD_OPTIONS)[number])}
              >
                <option value="FX_UNIFIED_GFR">GFR yearly</option>
                <option value="FX_DAILY_CNB">CNB daily</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wider text-ink3">Tax rate (%)</label>
              <input
                type="text"
                inputMode="decimal"
                className="mt-1 w-full rounded-md border border-borderc bg-surface px-2.5 py-2 text-sm text-ink num focus-ring disabled:opacity-50 disabled:cursor-not-allowed"
                value={taxRatePercent}
                disabled={isLocked || patchMutation.isPending}
                onChange={(e) => setTaxRatePercent(e.target.value)}
              />
            </div>
          </div>

          <div className="text-sm text-ink2">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                className="h-4 w-4"
                checked={exemption100k}
                disabled={isLocked || patchMutation.isPending}
                onChange={(e) => setExemption100k(e.target.checked)}
              />
              {exemption100k ? (
                <Chip tone="ok">
                  <Check className="w-3 h-3" />
                  100k exemption applied
                </Chip>
              ) : (
                <Chip tone="neutral">100k exemption off</Chip>
              )}
            </label>
          </div>

          <div className="flex items-center gap-2">
            <Button type="button" onClick={handleSave} disabled={!canSave}>
              Apply year settings
            </Button>
            {saveStateText ? <span className="text-xs text-ink3">{saveStateText}</span> : null}
            {!isLocked && !hasValidTaxRate ? (
              <span className="text-xs text-err">Tax rate must be numeric and &gt;= 0.</span>
            ) : null}
          </div>
          {localError ? (
            <div className="text-xs text-err">{localError}</div>
          ) : null}
          {mutationError ? (
            <div className="text-xs text-err">Save failed: {mutationError}</div>
          ) : null}
          {patchMutation.error && !mutationError ? (
            <div className="text-xs text-err">Save failed. Please retry.</div>
          ) : null}
          {isLocked ? (
            <div className="text-xs text-ink3">Filed/locked years are read-only by backend policy.</div>
          ) : null}
          <div className="text-[11px] text-ink3">Settings source: {y.settings_source}</div>
          <div className="text-[11px] text-ink3">Method source: {y.method_source}</div>
          <div className="text-xs text-ink3">
            Saved values are confirmed from backend response after refetch; this screen does not treat local edits as final truth.
          </div>
        </div>

        {/* RIGHT: numbers + reconciliation */}
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <KeyVal label="Gross proceeds">{formatCurrency(y.gross_proceeds_czk)}</KeyVal>
            <KeyVal label="Exempt">{formatCurrency(y.exempt_proceeds_czk)}</KeyVal>
            <KeyVal label="Taxable base">{formatCurrency(y.taxable_base_czk)}</KeyVal>
          </div>
          <Card className="p-3">
            <div className="text-[11px] uppercase tracking-wider text-ink3 mb-2">Reconciliation</div>
            <div className="grid grid-cols-3 gap-3 items-center">
              <KeyVal label="Workbook tax">{formatCurrency(y.tax_due_czk)}</KeyVal>
              <KeyVal label="Filed tax">
                {y.filed_tax_input_czk == null ? '—' : formatCurrency(y.filed_tax_input_czk)}
              </KeyVal>
              <div>
                <Chip tone={reconTone}>
                  {y.reconciliation_status === 'reconciled' ? <Check className="w-3 h-3" /> : null}
                  {reconLabel}
                </Chip>
              </div>
            </div>
            {y.reconciliation_note ? (
              <div className="mt-2 text-[12px] text-ink2 italic">{y.reconciliation_note}</div>
            ) : null}
            <div className="mt-2 text-[11px] text-ink3">Source: {y.reconciliation_source}</div>
          </Card>

          <KeyVal label="Match lines" className="pt-1">
            {y.match_line_count}
          </KeyVal>
        </div>
      </div>

      {/* Method comparison strip */}
      <div className="px-5 py-3 border-t border-borderc bg-bg/60">
        {isLocked ? (
          <div className="text-[12px] text-filed italic">
            Filed year — {y.filed_method ?? y.method} — do not optimise. Method comparison is hidden for locked years.
          </div>
        ) : y.show_method_comparison && y.method_comparison ? (
          <div className="flex items-center gap-4 text-xs text-ink2 flex-wrap">
            <span className="uppercase tracking-wider text-[11px] text-ink3">Method comparison (informational)</span>
            {(['FIFO', 'LIFO', 'MIN_GAIN', 'MAX_GAIN'] as const).map((m) => {
              const t = y.method_comparison![m]
              return (
                <span key={m} className={`num ${m === y.method ? 'text-ink font-medium' : ''}`}>
                  {m} <span className="text-ink3 ml-1">{formatCurrency(t)}</span>
                </span>
              )
            })}
          </div>
        ) : (
          <div className="text-[12px] text-ink3 italic">Method comparison not available for this year.</div>
        )}
      </div>
    </Card>
  )
}

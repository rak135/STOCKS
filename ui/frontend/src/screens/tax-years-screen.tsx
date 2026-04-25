import { LockKeyhole, Scale, ShieldAlert } from 'lucide-react'
import { Panel } from '../components/panel'
import { useYearsQuery } from '../lib/api'
import { formatCurrency } from '../lib/format'

export function TaxYearsScreen() {
  const { data, isLoading, error } = useYearsQuery()

  if (isLoading) {
    return (
      <Panel eyebrow="Tax years" title="Loading year policies" subtitle="Waiting for live `/api/years` data.">
        <div className="grid gap-4">
          <div className="h-48 animate-pulse rounded-[1.7rem] bg-stone-200/80" />
          <div className="h-48 animate-pulse rounded-[1.7rem] bg-stone-200/80" />
        </div>
      </Panel>
    )
  }

  if (error || !data) {
    return (
      <Panel eyebrow="Tax years" title="Backend connection needed" subtitle="The UI could not load `/api/years`." tone="muted">
        <div className="rounded-[1.4rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          Start the backend and reload this screen.
        </div>
      </Panel>
    )
  }

  const years = [...data.items].sort((left, right) => right.year - left.year)

  return (
    <div className="grid gap-4">
      <Panel
        eyebrow="Server policy"
        title="Tax Years"
        subtitle="These cards are read-only for now. They surface server-side policy and explicitly freeze filed years."
      >
        {years.length > 0 ? (
          <div className="grid gap-4">
            {years.map((year) => (
              <article
                key={year.year}
                className={`rounded-[1.8rem] border p-5 ${
                  year.year === 2024
                    ? 'border-stone-300 bg-[linear-gradient(140deg,_rgba(244,244,245,0.98),_rgba(228,228,231,0.94))]'
                    : 'border-stone-200/80 bg-white/82'
                }`}
              >
                <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">Year {year.year}</div>
                        <h3 className="mt-2 font-display text-3xl text-stone-900">{year.method}</h3>
                        <p className="mt-2 text-sm leading-6 text-stone-600">
                          FX method {year.fx_method} with a {Math.round(year.tax_rate * 100)}% tax rate.
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge label={year.filed ? 'Filed' : 'Not filed'} tone={year.filed ? 'solid' : 'soft'} />
                        <Badge label={year.locked ? 'Locked' : 'Editable'} tone={year.locked ? 'solid' : 'soft'} />
                        <Badge label={year.method} tone="soft" />
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <Metric label="Gross proceeds" value={formatCurrency(year.gross_proceeds_czk)} />
                      <Metric label="Taxable base" value={formatCurrency(year.taxable_base_czk)} />
                      <Metric label="Tax due" value={formatCurrency(year.tax_due_czk)} />
                      <Metric label="Exempt proceeds" value={formatCurrency(year.exempt_proceeds_czk)} />
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="rounded-[1.45rem] bg-stone-50/90 p-4">
                      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
                        <ShieldAlert className="h-4 w-4" />
                        Reconciliation
                      </div>
                      <div className="mt-3 space-y-2 text-sm text-stone-700">
                        <Row label="Status" value={year.reconciliation_status.replaceAll('_', ' ')} />
                        <Row
                          label="Filed tax input"
                          value={year.filed_tax_input_czk === null ? 'None' : formatCurrency(year.filed_tax_input_czk)}
                        />
                        <Row label="Match lines" value={String(year.match_line_count)} />
                      </div>
                    </div>

                    {year.year === 2024 ? (
                      <div className="rounded-[1.45rem] border border-stone-400/50 bg-white/70 p-4">
                        <div className="flex items-center gap-2 text-sm font-semibold text-stone-900">
                          <LockKeyhole className="h-4 w-4" />
                          Filed {'\u00B7'} Locked {'\u00B7'} LIFO
                        </div>
                        <p className="mt-2 text-sm leading-6 text-stone-600">Do not optimize. Method comparison is intentionally hidden for this filed year.</p>
                      </div>
                    ) : year.show_method_comparison && year.method_comparison ? (
                      <div className="rounded-[1.45rem] border border-stone-200/80 bg-white/70 p-4">
                        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
                          <Scale className="h-4 w-4" />
                          Method comparison
                        </div>
                        <div className="mt-3 grid gap-2 text-sm text-stone-700">
                          <Row label="FIFO" value={formatCurrency(year.method_comparison.FIFO)} />
                          <Row label="LIFO" value={formatCurrency(year.method_comparison.LIFO)} />
                          <Row label="MIN_GAIN" value={formatCurrency(year.method_comparison.MIN_GAIN)} />
                          <Row label="MAX_GAIN" value={formatCurrency(year.method_comparison.MAX_GAIN)} />
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-[1.45rem] border border-stone-200/80 bg-white/70 p-4 text-sm text-stone-600">
                        Method comparison is not available for this year.
                      </div>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-[1.45rem] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {data.truth.summary ?? 'Tax years are temporarily unavailable.'}
          </div>
        )}
      </Panel>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.35rem] border border-stone-200/80 bg-stone-50/80 p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-500">{label}</div>
      <div className="mt-2 text-lg font-semibold text-stone-900">{value}</div>
    </div>
  )
}

function Badge({ label, tone }: { label: string; tone: 'soft' | 'solid' }) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
        tone === 'solid' ? 'bg-stone-900 text-stone-50' : 'bg-stone-900/5 text-stone-700'
      }`}
    >
      {label}
    </span>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-stone-500">{label}</span>
      <span className="text-right font-medium text-stone-900">{value}</span>
    </div>
  )
}

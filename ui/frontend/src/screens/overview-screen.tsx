import type { ReactNode } from 'react'
import { AlertTriangle, ArrowRight, FolderSearch, LockKeyhole, ShieldCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Panel } from '../components/panel'
import { StatusPill } from '../components/status-pill'
import { useImportQuery, useStatusQuery, useYearsQuery } from '../lib/api'
import { compactPath, formatCurrency, formatDateTime, formatNumber } from '../lib/format'

function resolveHref(href?: string | null) {
  if (!href) {
    return null
  }

  const known = new Set(['/', '/import', '/tax-years', '/sales-review', '/open-positions', '/fx', '/audit', '/settings'])
  return known.has(href) ? href : null
}

export function OverviewScreen() {
  const navigate = useNavigate()
  const statusQuery = useStatusQuery()
  const yearsQuery = useYearsQuery()
  const importQuery = useImportQuery()

  if (statusQuery.isLoading || yearsQuery.isLoading || importQuery.isLoading) {
    return (
      <Panel eyebrow="Overview" title="Checking project state" subtitle="Loading live backend data for the cockpit.">
        <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
          <div className="h-64 animate-pulse rounded-[1.7rem] bg-stone-200/80" />
          <div className="h-64 animate-pulse rounded-[1.7rem] bg-stone-200/80" />
        </div>
      </Panel>
    )
  }

  if (statusQuery.error || yearsQuery.error || importQuery.error || !statusQuery.data || !yearsQuery.data || !importQuery.data) {
    return (
      <Panel eyebrow="Overview" title="Backend connection needed" subtitle="This screen depends entirely on live API data.">
        <div className="rounded-[1.5rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          The frontend could not read one of `/api/status`, `/api/import`, or `/api/years`.
        </div>
      </Panel>
    )
  }

  const status = statusQuery.data
  const years = [...yearsQuery.data].sort((left, right) => right.year - left.year)
  const importSummary = importQuery.data
  const nextHref = resolveHref(status.next_action?.href)

  return (
    <div className="grid gap-4">
      <Panel
        eyebrow="Situation room"
        title="Overview"
        subtitle="The backend is the source of truth for health, next action, and tax-year posture."
        actions={<StatusPill status={status.global_status} />}
      >
        <div className="grid gap-4 xl:grid-cols-[1.45fr_1fr]">
          <div className="rounded-[1.75rem] bg-[linear-gradient(135deg,_rgba(28,25,23,0.95),_rgba(68,64,60,0.92))] p-6 text-stone-50">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-300">Recommended next action</div>
            <div className="mt-4 max-w-2xl">
              <h3 className="font-display text-3xl">
                {status.next_action?.label ?? (status.global_status === 'ready' ? 'No action needed right now' : 'Backend review required')}
              </h3>
              <p className="mt-3 text-sm leading-6 text-stone-300">
                {status.unresolved_checks.length > 0
                  ? status.unresolved_checks[0].message
                  : 'The current engine snapshot has no unresolved checks.'}
              </p>
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => (nextHref ? navigate(nextHref) : undefined)}
                className="inline-flex items-center gap-2 rounded-full bg-stone-50 px-4 py-2 text-sm font-semibold text-stone-900 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!nextHref}
              >
                {status.next_action?.label ?? 'No follow-up action'}
                <ArrowRight className="h-4 w-4" />
              </button>
              <div className="rounded-full border border-white/10 px-4 py-2 text-sm text-stone-300">
                Last calculated {formatDateTime(status.last_calculated_at)}
              </div>
            </div>
          </div>

          <div className="grid gap-4">
            <StatCard
              icon={<FolderSearch className="h-4 w-4" />}
              label="Project path"
              value={compactPath(status.project_path)}
              detail={`${importSummary.files.length} CSV files detected`}
            />
            <StatCard
              icon={<ShieldCheck className="h-4 w-4" />}
              label="CSV folder"
              value={compactPath(status.csv_folder)}
              detail={`${formatNumber(importSummary.total_trade_rows)} trade rows from /api/import`}
            />
            <StatCard
              icon={<LockKeyhole className="h-4 w-4" />}
              label="Workbook authority"
              value="Backend only"
              detail="The UI reads FastAPI responses and never parses Excel."
            />
          </div>
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[1.55fr_1fr]">
        <Panel
          eyebrow="Tax years"
          title="Year cards"
          subtitle="Recent years first, with 2024 visually frozen to avoid optimization temptations."
        >
          <div className="grid gap-4 lg:grid-cols-2">
            {years.map((year) => (
              <article
                key={year.year}
                className={`rounded-[1.55rem] border p-5 ${
                  year.year === 2024
                    ? 'border-stone-300 bg-[linear-gradient(135deg,_rgba(245,245,244,0.98),_rgba(231,229,228,0.94))]'
                    : 'border-stone-200/80 bg-stone-50/80'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">Tax year</div>
                    <div className="mt-2 font-display text-3xl text-stone-900">{year.year}</div>
                  </div>
                  <div className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-stone-600">{year.method}</div>
                </div>
                <div className="mt-5 grid gap-2 text-sm text-stone-700">
                  <Row label="Tax due" value={formatCurrency(year.tax_due_czk)} />
                  <Row label="Taxable base" value={formatCurrency(year.taxable_base_czk)} />
                  <Row label="Sales matched" value={formatNumber(year.match_line_count)} />
                </div>
                {year.year === 2024 ? (
                  <div className="mt-5 rounded-[1.35rem] border border-stone-400/50 bg-white/65 px-4 py-3">
                    <div className="text-sm font-semibold text-stone-900">
                      Filed {'\u00B7'} Locked {'\u00B7'} LIFO
                    </div>
                    <p className="mt-1 text-sm text-stone-600">Do not optimize.</p>
                  </div>
                ) : (
                  <div className="mt-5 flex flex-wrap gap-2">
                    <span className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-stone-700">
                      {year.filed ? 'Filed' : 'Not filed'}
                    </span>
                    <span className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-stone-700">
                      {year.locked ? 'Locked' : 'Editable'}
                    </span>
                    <span className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-stone-700">
                      {year.show_method_comparison ? 'Comparison available' : 'Comparison hidden'}
                    </span>
                  </div>
                )}
              </article>
            ))}
          </div>
        </Panel>

        <Panel
          eyebrow="Checks"
          title="Unresolved issues"
          subtitle="Warnings and blockers come straight from `/api/status`."
        >
          {status.unresolved_checks.length > 0 ? (
            <div className="space-y-3">
              {status.unresolved_checks.map((check) => (
                <div
                  key={check.id}
                  className="rounded-[1.45rem] border border-amber-200 bg-amber-50/90 p-4 text-amber-900"
                >
                  <div className="flex items-start gap-3">
                    <div className="rounded-xl bg-amber-100 p-2">
                      <AlertTriangle className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold">{check.message}</div>
                      <div className="mt-1 text-xs uppercase tracking-[0.16em] text-amber-700">
                        {check.level} {check.year ? `\u00B7 ${check.year}` : ''}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-[1.45rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              No unresolved issues.
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
  detail,
}: {
  icon: ReactNode
  label: string
  value: string
  detail: string
}) {
  return (
    <div className="rounded-[1.5rem] border border-stone-200/80 bg-stone-50/90 p-4">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        <span className="rounded-lg bg-stone-900/5 p-2 text-stone-600">{icon}</span>
        {label}
      </div>
      <div className="mt-3 text-base font-semibold text-stone-900">{value}</div>
      <p className="mt-2 text-sm leading-6 text-stone-600">{detail}</p>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-stone-500">{label}</span>
      <span className="font-medium text-stone-900">{value}</span>
    </div>
  )
}

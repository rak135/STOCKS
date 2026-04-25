import { AlertTriangle, ChevronRight, Lock } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Chip, KeyVal, SectionHeader } from '../components/ui'
import { useImportQuery, useStatusQuery, useYearsQuery } from '../lib/api'
import { compactPath, formatCurrency, formatDateTime, formatNumber } from '../lib/format'
import type { Check, TaxYear } from '../types/api'

const knownRoutes = new Set(['/', '/import', '/tax-years', '/sales-review', '/open-positions', '/fx', '/audit', '/settings'])

function resolveHref(href?: string | null): string | null {
  if (!href) return null
  return knownRoutes.has(href) ? href : null
}

export function OverviewScreen() {
  const navigate = useNavigate()
  const statusQuery = useStatusQuery()
  const yearsQuery = useYearsQuery()
  const importQuery = useImportQuery()

  if (statusQuery.isLoading || yearsQuery.isLoading || importQuery.isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Overview" subtitle="Loading live backend data for the cockpit." />
        <div className="grid gap-4">
          <div className="h-32 animate-pulse rounded-xl bg-borderc/50" />
          <div className="h-48 animate-pulse rounded-xl bg-borderc/50" />
        </div>
      </div>
    )
  }

  if (statusQuery.error || yearsQuery.error || importQuery.error || !statusQuery.data || !yearsQuery.data || !importQuery.data) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Overview" subtitle="The backend is the source of truth for this screen." />
        <Card className="p-5 border-err-bg">
          <div className="text-sm text-err">
            The frontend could not read one of <span className="font-mono">/api/status</span>,{' '}
            <span className="font-mono">/api/import</span>, or <span className="font-mono">/api/years</span>.
          </div>
        </Card>
      </div>
    )
  }

  const status = statusQuery.data
  const years = [...yearsQuery.data.items].sort((a, b) => b.year - a.year)
  const importSummary = importQuery.data
  const nextHref = resolveHref(status.next_action?.href)

  const heroCopy: Record<typeof status.global_status, { title: string; body: string }> = {
    ready: { title: 'Ready', body: 'No blocking issues reported by the backend. Filed years remain locked.' },
    needs_review: {
      title: 'Needs review',
      body:
        status.unresolved_checks[0]?.message ??
        'Backend reports unresolved checks. Review the list below.',
    },
    blocked: {
      title: 'Blocked',
      body: status.unresolved_checks[0]?.message ?? 'Backend reports a blocker.',
    },
  }

  const heroTone = status.global_status === 'ready' ? 'ok' : status.global_status === 'blocked' ? 'err' : 'warn'

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <SectionHeader
        title="Overview"
        subtitle="Where does the tax model stand, and what should you do next?"
      />

      <Card className="p-6 mb-6" raised>
        <div className="flex items-start gap-4">
          <div
            className={`w-10 h-10 rounded-full grid place-items-center shrink-0 ${
              heroTone === 'ok'
                ? 'bg-ok-bg text-ok'
                : heroTone === 'err'
                  ? 'bg-err-bg text-err'
                  : 'bg-warn-bg text-warn'
            }`}
          >
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="text-xs uppercase tracking-wider text-ink3 mb-1">Status</div>
            <div className="text-[22px] font-semibold tracking-tight text-ink mb-1">{heroCopy[status.global_status].title}</div>
            <div className="text-ink2 text-sm max-w-2xl leading-6">{heroCopy[status.global_status].body}</div>
          </div>
          {status.next_action && nextHref ? (
            <Button onClick={() => navigate(nextHref)}>
              {status.next_action.label}
              <ChevronRight className="w-4 h-4" />
            </Button>
          ) : null}
        </div>
      </Card>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-wider text-ink3 mb-1">Project path</div>
          <div className="text-sm font-mono text-ink truncate" title={status.project_path}>
            {compactPath(status.project_path)}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-wider text-ink3 mb-1">CSV folder</div>
          <div className="text-sm font-mono text-ink truncate" title={status.csv_folder}>
            {compactPath(status.csv_folder)}
          </div>
          <div className="text-xs text-ink3 mt-1">
            {importSummary.files.length} files · {formatNumber(importSummary.total_trade_rows)} trade rows
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-wider text-ink3 mb-1">Last calculation</div>
          <div className="text-sm text-ink">{formatDateTime(status.last_calculated_at)}</div>
          <div className="text-xs text-ink3 mt-1 truncate">Source: {status.output_path}</div>
        </Card>
      </div>

      <h2 className="text-sm font-semibold text-ink2 mb-3">Tax years</h2>
      <div className="grid grid-cols-1 gap-3 mb-8">
        {years.map((y) => (
          <YearSummaryRow key={y.year} y={y} onOpen={() => navigate('/tax-years')} />
        ))}
        {years.length === 0 ? (
          <Card className="p-5 text-sm text-ink3">{yearsQuery.data.truth.summary ?? 'No tax years available.'}</Card>
        ) : null}
      </div>

      <h2 className="text-sm font-semibold text-ink2 mb-3">Unresolved</h2>
      <Card>
        {status.unresolved_checks.length === 0 ? (
          <div className="p-6 text-sm text-ink3">No unresolved issues.</div>
        ) : (
          <ul className="divide-y divide-borderc">
            {status.unresolved_checks.map((c) => (
              <CheckRow key={c.id} check={c} onResolve={(href) => navigate(href)} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

function YearSummaryRow({ y, onOpen }: { y: TaxYear; onOpen: () => void }) {
  const isFiled = y.filed
  return (
    <Card className={`px-5 py-4 flex items-center gap-5 ${isFiled ? 'bg-filed-bg/40' : ''}`}>
      <div className="w-16 shrink-0">
        <div className="text-[22px] font-semibold tracking-tight text-ink">{y.year}</div>
        {isFiled ? (
          <Chip tone="filed">
            <Lock className="w-3 h-3" />
            Filed · Locked
          </Chip>
        ) : (
          <Chip tone="neutral">Draft</Chip>
        )}
      </div>
      <div className="flex-1 grid grid-cols-4 gap-3">
        <KeyVal label="Method">
          {isFiled ? (
            <>
              <span className="text-filed">{y.method}</span>{' '}
              <span className="text-ink3 text-xs">(filed)</span>
            </>
          ) : (
            y.method
          )}
        </KeyVal>
        <KeyVal label="Taxable base">{formatCurrency(y.taxable_base_czk)}</KeyVal>
        <KeyVal label="Tax due">{formatCurrency(y.tax_due_czk)}</KeyVal>
        <KeyVal label="FX method" mono={false}>
          {y.fx_method === 'FX_DAILY_CNB' ? 'CNB daily' : 'GFŘ yearly'}
        </KeyVal>
      </div>
      <div className="w-44 text-right shrink-0 flex items-center justify-end gap-3">
        {isFiled ? (
          <span className="text-[11px] text-filed italic">Filed — do not optimise</span>
        ) : (
          <Chip tone="neutral">Draft</Chip>
        )}
        <button onClick={onOpen} className="text-sm text-accent hover:underline focus-ring inline-flex items-center">
          Open <ChevronRight className="w-3 h-3 inline ml-0.5" />
        </button>
      </div>
    </Card>
  )
}

function CheckRow({ check, onResolve }: { check: Check; onResolve: (href: string) => void }) {
  const tone = check.level === 'error' ? 'err' : check.level === 'warn' ? 'warn' : 'info'
  const href = resolveHref(check.href)
  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <Chip tone={tone}>{check.level}</Chip>
      <span className="text-sm text-ink flex-1">{check.message}</span>
      {href ? (
        <button
          className="text-sm text-accent hover:underline focus-ring inline-flex items-center"
          onClick={() => onResolve(href)}
        >
          Resolve <ChevronRight className="w-3 h-3 inline ml-0.5" />
        </button>
      ) : null}
    </li>
  )
}

import {
  AlertTriangle,
  Ban,
  CircleHelp,
  Download,
  FileText,
  Lock,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { Card, Chip, SectionHeader, StatusDot } from '../components/ui'
import { useAuditQuery } from '../lib/api'
import { formatCurrency, formatNumber } from '../lib/format'
import type { AuditSummary, TaxYear, TruthReason, TruthStatus } from '../types/api'

const truthTone: Record<TruthStatus, 'ok' | 'warn' | 'err' | 'filed' | 'neutral'> = {
  ready: 'ok',
  needs_review: 'warn',
  partial: 'warn',
  blocked: 'err',
  unknown: 'filed',
  not_implemented: 'filed',
}

const truthLabel: Record<TruthStatus, string> = {
  ready: 'Ready',
  needs_review: 'Needs review',
  partial: 'Partial',
  blocked: 'Blocked',
  unknown: 'Unknown',
  not_implemented: 'Not implemented',
}

const traceLabels: Record<string, string> = {
  csv_files: 'CSV files',
  raw_rows: 'Raw rows',
  trade_rows: 'Trade rows',
  transactions: 'Transactions',
  ignored_rows: 'Ignored rows',
  match_lines: 'Match lines',
  matched_lots: 'Matched lots',
  open_lots: 'Open lots',
  sells: 'Sells',
  buys: 'Buys',
  years: 'Years',
}

function humaniseTraceKey(key: string): string {
  if (traceLabels[key]) return traceLabels[key]
  return key
    .split(/[_\s-]/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export function AuditScreen() {
  const { data, isLoading, error } = useAuditQuery()

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Audit Pack" subtitle="Loading audit summary from backend." />
        <div className="space-y-3">
          <div className="h-24 animate-pulse rounded-xl bg-borderc/50" />
          <div className="h-32 animate-pulse rounded-xl bg-borderc/50" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Audit Pack" subtitle="Backend audit endpoint is required." />
        <Card className="p-5 border-err-bg">
          <div className="text-sm text-err">
            Could not load <span className="font-mono">/api/audit</span>. Make sure the backend is running.
          </div>
        </Card>
      </div>
    )
  }

  const headerSubtitle = data.summary_only
    ? 'Summary-only view of what a tax-office check would ask for. This is not a final audit pack.'
    : 'Backend reports this audit summary as final readiness.'

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <SectionHeader
        title="Audit Pack"
        subtitle={headerSubtitle}
        primary={
          data.summary_only ? <Chip tone="warn">Summary-only · not final</Chip> : (
            <Chip tone={truthTone[data.truth_status]}>
              <StatusDot status={data.truth_status} />
              {truthLabel[data.truth_status]}
            </Chip>
          )
        }
      />

      <SummaryTruthBanner audit={data} />

      <ReadinessCard audit={data} />

      {data.workbook_backed_domains.length > 0 ? <WorkbookBackedCard audit={data} /> : null}

      {Object.keys(data.trace_counts).length > 0 ? <TraceCountsSection counts={data.trace_counts} /> : null}

      <YearSummaryTable rows={data.year_rows} />

      <LockedSnapshotsCard snapshots={data.locked_snapshots} />

      <ExportSection />
    </div>
  )
}

function SummaryTruthBanner({ audit }: { audit: AuditSummary }) {
  const tone = truthTone[audit.truth_status]
  const Icon =
    audit.truth_status === 'blocked'
      ? Ban
      : audit.truth_status === 'unknown' || audit.truth_status === 'not_implemented'
        ? CircleHelp
        : audit.truth_status === 'ready'
          ? ShieldCheck
          : AlertTriangle

  return (
    <Card
      className={`p-4 mb-5 ${
        tone === 'err'
          ? 'border-err-bg bg-err-bg/40'
          : tone === 'warn'
            ? 'border-warn-bg bg-warn-bg/40'
            : tone === 'filed'
              ? 'bg-filed-bg/30'
              : tone === 'ok'
                ? 'border-ok-bg bg-ok-bg/40'
                : ''
      }`}
    >
      <div className="flex items-start gap-3">
        <Icon className="w-4 h-4 mt-0.5 text-ink2 shrink-0" />
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink">Audit truth</span>
            <Chip tone={tone}>
              <StatusDot status={audit.truth_status} />
              {truthLabel[audit.truth_status]}
            </Chip>
            {audit.summary_only ? (
              <Chip tone="warn">Summary-only · not final export readiness</Chip>
            ) : (
              <Chip tone="ok">Final export readiness</Chip>
            )}
          </div>
          <p className="mt-1.5 text-[13px] text-ink2 leading-5">
            {audit.summary_only
              ? 'Backend marks this audit view as summary-only. Treat it as a snapshot for human review, not as the artefact a tax office would see.'
              : 'Backend reports this audit view as final export readiness.'}
          </p>
          {audit.status_reasons.length > 0 ? <ReasonList reasons={audit.status_reasons} /> : null}
        </div>
      </div>
    </Card>
  )
}

function ReasonList({ reasons }: { reasons: TruthReason[] }) {
  return (
    <ul className="mt-2 space-y-0.5 text-[12px] text-ink2">
      {reasons.map((r) => (
        <li key={`${r.code}-${r.message}`}>
          • <span className="font-mono">{r.code}</span>: {r.message}
        </li>
      ))}
    </ul>
  )
}

function ReadinessCard({ audit }: { audit: AuditSummary }) {
  const tone = truthTone[audit.truth_status]
  const headline =
    audit.truth_status === 'ready'
      ? 'Audit summary is ready'
      : audit.truth_status === 'partial'
        ? 'Audit summary is partial'
        : audit.truth_status === 'needs_review'
          ? 'Audit summary needs review'
          : audit.truth_status === 'blocked'
            ? 'Audit summary is blocked'
            : audit.truth_status === 'unknown'
              ? 'Audit readiness is unknown'
              : 'Audit readiness is not implemented'

  const body =
    audit.truth_status === 'ready'
      ? 'Backend reports no remaining blockers for the audit summary.'
      : audit.truth_status === 'partial'
        ? 'Important domains or explanations are still incomplete. See backend reasons below.'
        : audit.truth_status === 'blocked'
          ? 'Required checks failed. The audit summary cannot be trusted in this state.'
          : audit.truth_status === 'needs_review'
            ? 'Backend has facts to show, but a human should treat them as unresolved.'
            : 'Backend cannot currently resolve this view.'

  return (
    <Card className="p-5 mb-5">
      <div className="flex items-start gap-3">
        <div
          className={`w-10 h-10 rounded-full grid place-items-center shrink-0 ${
            tone === 'ok'
              ? 'bg-ok-bg text-ok'
              : tone === 'err'
                ? 'bg-err-bg text-err'
                : tone === 'filed'
                  ? 'bg-filed-bg text-filed'
                  : 'bg-warn-bg text-warn'
          }`}
        >
          <ShieldAlert className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <div className="text-[11px] uppercase tracking-wider text-ink3 mb-1">Readiness posture</div>
          <div className="text-[18px] font-semibold tracking-tight text-ink mb-1">{headline}</div>
          <p className="text-sm text-ink2 leading-6 max-w-2xl">{body}</p>
          {audit.status_reasons.length === 0 && audit.truth_status !== 'ready' ? (
            <p className="mt-2 text-[12px] text-ink3 italic">
              Backend has not attached structured status reasons for this view.
            </p>
          ) : null}
        </div>
      </div>
    </Card>
  )
}

function WorkbookBackedCard({ audit }: { audit: AuditSummary }) {
  return (
    <Card className="p-5 mb-5 border-warn-bg bg-warn-bg/30">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-warn shrink-0 mt-0.5" />
        <div className="flex-1">
          <div className="text-[11px] uppercase tracking-wider text-warn mb-1">Workbook-backed domains</div>
          <div className="text-sm font-medium text-ink mb-2">
            {audit.workbook_backed_domains.length}{' '}
            {audit.workbook_backed_domains.length === 1 ? 'domain' : 'domains'} still depend on the workbook
          </div>
          <p className="text-[13px] text-ink2 leading-5 max-w-2xl mb-3">
            These domains have not yet been migrated to canonical backend state. Their values still flow through
            the workbook fallback and must remain visible until they are.
          </p>
          <div className="flex flex-wrap gap-1.5">
            {audit.workbook_backed_domains.map((d) => (
              <Chip key={d} tone="warn">
                {d}
              </Chip>
            ))}
          </div>
        </div>
      </div>
    </Card>
  )
}

function TraceCountsSection({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts)
  return (
    <div className="mb-5">
      <h2 className="text-sm font-semibold text-ink2 mb-3">Trace counts</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {entries.map(([key, value]) => (
          <Card key={key} className="p-4">
            <div className="text-[11px] uppercase tracking-wider text-ink3 mb-1">{humaniseTraceKey(key)}</div>
            <div className="text-[18px] font-semibold text-ink num">{formatNumber(value)}</div>
          </Card>
        ))}
      </div>
    </div>
  )
}

function YearSummaryTable({ rows }: { rows: TaxYear[] }) {
  const sorted = [...rows].sort((a, b) => b.year - a.year)
  return (
    <div className="mb-5">
      <h2 className="text-sm font-semibold text-ink2 mb-3">Yearly summary</h2>
      <Card>
        {sorted.length === 0 ? (
          <div className="p-5 text-sm text-ink3">No tax-year rows reported by backend.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-[11px] uppercase text-ink3 tracking-wider">
              <tr className="text-left">
                <th className="px-5 py-2 font-normal">Year</th>
                <th className="px-5 py-2 font-normal">Method</th>
                <th className="px-5 py-2 font-normal">FX</th>
                <th className="px-5 py-2 font-normal text-right">Proceeds</th>
                <th className="px-5 py-2 font-normal text-right">Taxable base</th>
                <th className="px-5 py-2 font-normal text-right">Tax</th>
                <th className="px-5 py-2 font-normal">Recon</th>
                <th className="px-5 py-2 font-normal">Status</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((y) => (
                <tr key={y.year} className="border-t border-borderc/60">
                  <td className="px-5 py-2 font-semibold text-ink">{y.year}</td>
                  <td className="px-5 py-2 text-ink">
                    {y.method}
                    {y.filed_method && y.filed_method !== y.method ? (
                      <span className="text-ink3 text-[11px] ml-1">(filed: {y.filed_method})</span>
                    ) : null}
                  </td>
                  <td className="px-5 py-2 text-ink">
                    {y.fx_method === 'FX_DAILY_CNB' ? 'CNB daily' : 'GFŘ yearly'}
                  </td>
                  <td className="px-5 py-2 text-right num text-ink">{formatCurrency(y.gross_proceeds_czk)}</td>
                  <td className="px-5 py-2 text-right num text-ink">{formatCurrency(y.taxable_base_czk)}</td>
                  <td className="px-5 py-2 text-right num font-medium text-ink">{formatCurrency(y.tax_due_czk)}</td>
                  <td className="px-5 py-2">
                    <Chip
                      tone={
                        y.reconciliation_status === 'reconciled'
                          ? 'ok'
                          : y.reconciliation_status === 'needs_attention'
                            ? 'warn'
                            : y.reconciliation_status === 'accepted_with_note'
                              ? 'info'
                              : 'neutral'
                      }
                    >
                      {y.reconciliation_status.replaceAll('_', ' ')}
                    </Chip>
                  </td>
                  <td className="px-5 py-2">
                    {y.locked ? (
                      <Chip tone="filed">
                        <Lock className="w-3 h-3" />
                        Locked
                      </Chip>
                    ) : y.filed ? (
                      <Chip tone="info">Filed</Chip>
                    ) : (
                      <Chip tone="neutral">Draft</Chip>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

function LockedSnapshotsCard({ snapshots }: { snapshots: number[] }) {
  return (
    <div className="mb-5">
      <h2 className="text-sm font-semibold text-ink2 mb-3">Locked snapshots</h2>
      <Card>
        {snapshots.length === 0 ? (
          <div className="p-5 text-sm text-ink3">No locked-year snapshots reported by backend.</div>
        ) : (
          <ul className="divide-y divide-borderc">
            {snapshots
              .slice()
              .sort((a, b) => b - a)
              .map((y) => (
                <li key={y} className="flex items-center gap-4 px-5 py-3">
                  <Lock className="w-4 h-4 text-filed shrink-0" />
                  <span className="font-semibold text-ink w-16">{y}</span>
                  <span className="text-sm text-ink2">Locked year snapshot</span>
                  <span className="flex-1" />
                  <Chip tone="filed">snapshot ref</Chip>
                </li>
              ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

function ExportSection() {
  const exports: Array<{ title: string; desc: string }> = [
    {
      title: 'Excel workbook export',
      desc: 'Canonical workbook rebuild — not yet wired to a backend audit-export endpoint.',
    },
    {
      title: 'PDF audit report',
      desc: 'Human-readable yearly summaries, FX sources, and method choices — not implemented.',
    },
    {
      title: 'CSV lot ledger',
      desc: 'Flat ledger of every (sell, buy lot) pair with source refs — not implemented.',
    },
    {
      title: 'ZIP evidence pack',
      desc: 'Workbook + PDF + CSV + original CSVs + FX cache snapshot — not implemented.',
    },
  ]
  return (
    <div>
      <h2 className="text-sm font-semibold text-ink2 mb-3">Export</h2>
      <p className="text-[12px] text-ink3 mb-3">
        Export workflow is not yet wired. Each option below is shown as disabled rather than fabricating an
        artefact.
      </p>
      <div className="grid grid-cols-2 gap-3">
        {exports.map((e) => (
          <Card key={e.title} className="p-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-borderc/40 text-ink3 grid place-items-center shrink-0">
              <FileText className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-ink">{e.title}</div>
              <div className="text-[12px] text-ink3 leading-5">{e.desc}</div>
            </div>
            <button
              type="button"
              disabled
              title="No backend audit-export endpoint exists yet."
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium bg-surface border border-borderc text-ink3 opacity-60 cursor-not-allowed shrink-0"
            >
              <Download className="w-4 h-4" />
              Not wired
            </button>
          </Card>
        ))}
      </div>
    </div>
  )
}

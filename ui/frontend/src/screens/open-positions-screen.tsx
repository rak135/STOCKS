import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  Ban,
  Check as CheckIcon,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  RefreshCw,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { Button, Card, Chip, KeyVal, SectionHeader, StatusDot } from '../components/ui'
import { useOpenPositionsQuery } from '../lib/api'
import { formatCurrency, formatDate, formatNumber } from '../lib/format'
import type {
  CollectionTruth,
  OpenLot,
  OpenPosition,
  OpenPositionStatus,
  TruthSource,
  TruthStatus,
} from '../types/api'

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

const statusTone: Record<OpenPositionStatus, 'ok' | 'warn' | 'err' | 'filed'> = {
  ok: 'ok',
  warn: 'warn',
  error: 'err',
  unknown: 'filed',
}

const statusLabel: Record<OpenPositionStatus, string> = {
  ok: 'OK',
  warn: 'WARN',
  error: 'ERROR',
  unknown: 'UNKNOWN',
}

const sourceLabels: Record<TruthSource, string> = {
  project_state: 'Project state',
  ui_state: 'UI state',
  workbook_fallback: 'Workbook fallback',
  calculated: 'Calculated',
  generated_default: 'Generated default',
  cnb_cache: 'CNB cache',
  static_config: 'Static config',
  unavailable: 'Unavailable',
}

const sourceTone: Record<TruthSource, 'ok' | 'warn' | 'err' | 'filed' | 'info' | 'neutral'> = {
  project_state: 'ok',
  ui_state: 'info',
  workbook_fallback: 'warn',
  calculated: 'info',
  generated_default: 'warn',
  cnb_cache: 'info',
  static_config: 'neutral',
  unavailable: 'err',
}

type StatusFilter = 'all' | OpenPositionStatus

const statusFilters: StatusFilter[] = ['all', 'ok', 'warn', 'error', 'unknown']

export function OpenPositionsScreen() {
  const { data, isLoading, error } = useOpenPositionsQuery()

  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [expanded, setExpanded] = useState<string | null>(null)

  const sortedItems = useMemo(() => {
    if (!data) return []
    return [...data.items].sort((a, b) => a.ticker.localeCompare(b.ticker))
  }, [data])

  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return sortedItems.filter((p) => {
      if (statusFilter !== 'all' && p.status !== statusFilter) return false
      if (!q) return true
      return p.ticker.toLowerCase().includes(q) || p.instrument_id.toLowerCase().includes(q)
    })
  }, [sortedItems, searchQuery, statusFilter])

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Open Positions" subtitle="Loading residual inventory from backend." />
        <div className="space-y-3">
          <div className="h-20 animate-pulse rounded-xl bg-borderc/50" />
          <div className="h-16 animate-pulse rounded-xl bg-borderc/50" />
          <div className="h-16 animate-pulse rounded-xl bg-borderc/50" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Open Positions" subtitle="Backend open-positions endpoint is required." />
        <Card className="p-5 border-err-bg">
          <div className="text-sm text-err">
            Could not load <span className="font-mono">/api/open-positions</span>. Make sure the backend is running.
          </div>
        </Card>
      </div>
    )
  }

  const truth = data.truth
  const totalCount = data.items.length

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <SectionHeader
        title="Open Positions"
        subtitle="Does the residual inventory match what you actually hold?"
        primary={
          <Button
            variant="secondary"
            disabled
            title="No backend mutation endpoint exists for Yahoo/broker reconciliation yet."
          >
            <RefreshCw className="w-4 h-4" />
            Reconcile not wired
          </Button>
        }
      />

      <TruthBanner truth={truth} itemsInView={filteredItems.length} totalItems={totalCount} />

      <div className="mt-5 flex items-center gap-3 flex-wrap">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-2 top-2.5 text-ink3" />
          <input
            placeholder="Ticker or instrument…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="border border-borderc rounded-md pl-7 pr-2 py-2 text-sm bg-surface text-ink focus-ring w-64"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {statusFilters.map((s) => {
            const active = statusFilter === s
            return (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-2 py-0.5 rounded-full text-[11px] focus-ring ${
                  active ? 'bg-accent-bg text-accent' : 'bg-borderc/50 text-ink2 hover:text-ink'
                }`}
              >
                {s === 'all' ? 'All' : statusLabel[s as OpenPositionStatus]}
              </button>
            )
          })}
        </div>
        <div className="text-[12px] text-ink3 ml-auto">
          {filteredItems.length} of {totalCount} positions
        </div>
      </div>

      {totalCount === 0 ? (
        <Card className="p-6 mt-5 text-sm text-ink3">
          {truth.summary ?? 'Backend returned no open positions.'}
        </Card>
      ) : filteredItems.length === 0 ? (
        <Card className="p-6 mt-5 text-sm text-ink3">No positions match the current filter.</Card>
      ) : (
        <div className="space-y-3 mt-5">
          {filteredItems.map((p) => (
            <PositionCard
              key={`${p.instrument_id}-${p.ticker}`}
              p={p}
              expanded={expanded === p.instrument_id}
              onToggle={() =>
                setExpanded(expanded === p.instrument_id ? null : p.instrument_id)
              }
            />
          ))}
        </div>
      )}
    </div>
  )
}

function TruthBanner({
  truth,
  itemsInView,
  totalItems,
}: {
  truth: CollectionTruth
  itemsInView: number
  totalItems: number
}) {
  const tone = truthTone[truth.status]
  const Icon =
    truth.status === 'blocked'
      ? Ban
      : truth.status === 'unknown' || truth.status === 'not_implemented'
        ? CircleHelp
        : truth.status === 'ready'
          ? ShieldCheck
          : AlertTriangle

  return (
    <Card
      className={`p-4 ${
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
            <span className="text-sm font-medium text-ink">Collection truth</span>
            <Chip tone={tone}>
              <StatusDot status={truth.status} />
              {truthLabel[truth.status]}
            </Chip>
            <Chip tone="neutral">In view: {itemsInView}</Chip>
            <Chip tone="neutral">Total: {totalItems}</Chip>
            <Chip tone="neutral">empty: {truth.empty_meaning}</Chip>
          </div>
          {truth.summary ? <p className="mt-1.5 text-[13px] text-ink2 leading-5">{truth.summary}</p> : null}
          {truth.sources.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {truth.sources.map((src) => (
                <Chip key={src} tone={sourceTone[src]}>
                  src: {sourceLabels[src]}
                </Chip>
              ))}
            </div>
          ) : null}
          {truth.reasons.length > 0 ? (
            <ul className="mt-2 space-y-0.5 text-[12px] text-ink2">
              {truth.reasons.map((r) => (
                <li key={`${r.code}-${r.message}`}>
                  • <span className="font-mono">{r.code}</span>: {r.message}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </Card>
  )
}

function PositionCard({
  p,
  expanded,
  onToggle,
}: {
  p: OpenPosition
  expanded: boolean
  onToggle: () => void
}) {
  const isUnknown = p.status === 'unknown' || p.truth_status === 'unknown'
  const isWarn = p.status === 'warn' || p.truth_status === 'needs_review' || p.truth_status === 'partial'
  const isError = p.status === 'error' || p.truth_status === 'blocked'
  const cardTint = isError
    ? 'border-err-bg'
    : isUnknown
      ? 'bg-filed-bg/30'
      : isWarn
        ? 'border-warn-bg'
        : ''

  return (
    <Card className={`overflow-hidden ${cardTint}`}>
      <button onClick={onToggle} className="w-full flex items-center gap-5 px-5 py-4 text-left focus-ring">
        <div className="w-28 shrink-0">
          <div className="font-semibold text-ink">{p.ticker}</div>
          <div className="text-[11px] text-ink3 font-mono truncate" title={p.instrument_id}>
            {p.instrument_id}
          </div>
        </div>
        <div className="flex-1 grid grid-cols-4 gap-3">
          <KeyVal label="Calculated">{formatNumber(p.calculated_qty)}</KeyVal>
          <KeyVal label="Yahoo">{p.yahoo_qty == null ? '—' : formatNumber(p.yahoo_qty)}</KeyVal>
          <KeyVal label="Difference">
            {p.difference == null ? (
              <span className="text-ink3">—</span>
            ) : (
              <span className={p.difference === 0 ? 'text-ink' : p.difference > 0 ? 'text-warn' : 'text-err'}>
                {p.difference > 0 ? `+${formatNumber(p.difference)}` : formatNumber(p.difference)}
              </span>
            )}
          </KeyVal>
          <div className="flex items-center gap-1.5 flex-wrap">
            <Chip tone={statusTone[p.status]}>
              {p.status === 'ok' ? <CheckIcon className="w-3 h-3" /> : null}
              {statusLabel[p.status]}
            </Chip>
            {p.truth_status !== 'ready' ? (
              <Chip tone={truthTone[p.truth_status]}>
                <StatusDot status={p.truth_status} />
                {truthLabel[p.truth_status]}
              </Chip>
            ) : null}
          </div>
        </div>
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-ink3 shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-ink3 shrink-0" />
        )}
      </button>

      {/* Always-visible reason strip for unknown / warn / error rows */}
      {isUnknown || isWarn || isError ? (
        <div
          className={`px-5 pb-3 -mt-1 text-[12px] flex flex-wrap items-center gap-2 ${
            isError ? 'text-err' : isUnknown ? 'text-ink2 italic' : 'text-warn'
          }`}
        >
          {p.status_reason_code ? (
            <span className="font-mono bg-surface border border-borderc rounded px-1.5 py-0.5 text-[11px] text-ink2">
              {p.status_reason_code}
            </span>
          ) : null}
          <span>
            {p.status_reason ??
              (isUnknown
                ? 'Backend reports this position as unverified. Confirm the residual with your broker directly.'
                : isError
                  ? 'Backend reports this position as blocked.'
                  : 'Backend reports this position as needing review.')}
          </span>
        </div>
      ) : null}

      {/* Always-visible per-row provenance chips */}
      <div className="px-5 pb-3 -mt-1 flex flex-wrap items-center gap-1.5">
        <Chip tone={sourceTone[p.instrument_map_source]}>
          instrument: {sourceLabels[p.instrument_map_source]}
        </Chip>
        <Chip tone={sourceTone[p.inventory_source]}>
          inventory: {sourceLabels[p.inventory_source]}
        </Chip>
      </div>

      {expanded ? (
        <div className="border-t border-borderc px-5 py-4 bg-bg/60">
          {p.lots.length === 0 ? (
            <div className="text-[13px] text-ink3 italic">Lot detail not available from backend.</div>
          ) : (
            <LotTable lots={p.lots} />
          )}
        </div>
      ) : null}
    </Card>
  )
}

function LotTable({ lots }: { lots: OpenLot[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-[11px] uppercase text-ink3 tracking-wider">
          <tr className="text-left border-b border-borderc">
            <th className="py-2 font-normal">Lot</th>
            <th className="py-2 font-normal">Buy date</th>
            <th className="py-2 font-normal">Broker</th>
            <th className="py-2 font-normal text-right">Qty</th>
            <th className="py-2 font-normal text-right">Cost (CZK)</th>
            <th className="py-2 font-normal text-right">Unrealised P/L</th>
          </tr>
        </thead>
        <tbody>
          {lots.map((l) => (
            <tr key={l.lot_id} className="border-b border-borderc/60">
              <td className="py-2 font-mono text-xs text-ink">{l.lot_id}</td>
              <td className="py-2 text-ink">{formatDate(l.buy_date)}</td>
              <td className="py-2 text-ink">{l.broker}</td>
              <td className="py-2 text-right num text-ink">{formatNumber(l.quantity)}</td>
              <td className="py-2 text-right num text-ink">{formatCurrency(l.cost_basis_czk)}</td>
              <td className="py-2 text-right num">
                {l.unrealised_pl_czk == null ? (
                  <span className="text-ink3">—</span>
                ) : (
                  <span className={l.unrealised_pl_czk >= 0 ? 'text-ok' : 'text-err'}>
                    {formatCurrency(l.unrealised_pl_czk)}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

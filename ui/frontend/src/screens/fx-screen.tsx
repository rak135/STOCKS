import {
  AlertTriangle,
  Ban,
  Check as CheckIcon,
  CircleHelp,
  Download,
  ExternalLink,
  Lock,
  Pencil,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import { Button, Card, Chip, KeyVal, SectionHeader, StatusDot } from '../components/ui'
import { useFxQuery } from '../lib/api'
import { formatDate, formatDateTime } from '../lib/format'
import type { CollectionTruth, FxYear, TruthSource, TruthStatus } from '../types/api'

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

function methodLabel(method: FxYear['method']): string {
  return method === 'FX_DAILY_CNB' ? 'CNB daily' : 'GFŘ yearly'
}

export function FxScreen() {
  const { data, isLoading, error } = useFxQuery()

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="FX Rates" subtitle="Loading FX provenance from backend." />
        <div className="space-y-3">
          <div className="h-20 animate-pulse rounded-xl bg-borderc/50" />
          <div className="h-32 animate-pulse rounded-xl bg-borderc/50" />
          <div className="h-32 animate-pulse rounded-xl bg-borderc/50" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="FX Rates" subtitle="Backend FX endpoint is required." />
        <Card className="p-5 border-err-bg">
          <div className="text-sm text-err">
            Could not load <span className="font-mono">/api/fx</span>. Make sure the backend is running.
          </div>
        </Card>
      </div>
    )
  }

  const items = [...data.items].sort((a, b) => b.year - a.year)
  const truth = data.truth

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <SectionHeader
        title="FX Rates"
        subtitle="Every rate used must be defensibly sourced from CNB or GFŘ."
        primary={
          <Button
            variant="secondary"
            disabled
            title="No backend mutation endpoint exists for FX fetch yet."
          >
            <Download className="w-4 h-4" />
            Fetch not wired
          </Button>
        }
      />

      <TruthBanner truth={truth} itemsInView={items.length} />

      {items.length === 0 ? (
        <Card className="p-6 mt-5 text-sm text-ink3">
          {truth.summary ?? 'Backend returned no FX years.'}
        </Card>
      ) : (
        <div className="space-y-4 mt-5">
          {items.map((y) => (
            <FxYearCard key={y.year} y={y} />
          ))}
        </div>
      )}
    </div>
  )
}

function TruthBanner({ truth, itemsInView }: { truth: CollectionTruth; itemsInView: number }) {
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
            <Chip tone="neutral">Total: {truth.item_count}</Chip>
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

function FxYearCard({ y }: { y: FxYear }) {
  const isUnified = y.method === 'FX_UNIFIED_GFR'
  const missingCount = y.missing_dates.length
  const hasMissing = missingCount > 0
  const cached = y.daily_cached
  const expected = y.daily_expected

  return (
    <Card className={y.locked ? 'bg-filed-bg/30 overflow-hidden' : 'overflow-hidden'}>
      <div className="flex items-center gap-3 px-5 py-4 border-b border-borderc flex-wrap">
        <div className="text-[20px] font-semibold tracking-tight text-ink w-20">{y.year}</div>
        <Chip tone="neutral">{methodLabel(y.method)}</Chip>
        <Chip tone={truthTone[y.truth_status]}>
          <StatusDot status={y.truth_status} />
          {truthLabel[y.truth_status]}
        </Chip>
        <Chip tone={sourceTone[y.rate_source]}>rate src: {sourceLabels[y.rate_source]}</Chip>
        {y.locked ? (
          <Chip tone="filed">
            <Lock className="w-3 h-3" />
            Locked
          </Chip>
        ) : null}
        {y.manual_override ? <Chip tone="warn">Manual override</Chip> : null}
        {hasMissing ? (
          <Chip tone="warn">
            <AlertTriangle className="w-3 h-3" />
            {missingCount} {missingCount === 1 ? 'rate missing' : 'rates missing'}
          </Chip>
        ) : null}
        {y.verified_at ? (
          <Chip tone="ok">
            <CheckIcon className="w-3 h-3" />
            Verified {y.verified_at.slice(0, 10)}
          </Chip>
        ) : null}
        <div className="flex-1" />
        <Button
          variant="secondary"
          disabled
          title="No backend mutation endpoint exists for FX fetch / verify yet."
        >
          <RefreshCw className="w-4 h-4" />
          Fetch not wired
        </Button>
        <Button
          variant="ghost"
          disabled
          title="No backend mutation endpoint exists for manual FX edit yet."
        >
          <Pencil className="w-4 h-4" />
          Manual edit not wired
        </Button>
      </div>

      <div className="px-5 py-4 grid grid-cols-4 gap-4">
        {isUnified ? (
          <>
            <KeyVal label="Unified USD/CZK">
              {y.unified_rate == null ? '—' : y.unified_rate.toFixed(3)}
            </KeyVal>
            <KeyVal label="Source" mono={false}>
              {y.source_label}
            </KeyVal>
            <KeyVal label="Verified" mono={false}>
              {y.verified_at ? formatDateTime(y.verified_at) : '—'}
            </KeyVal>
            <KeyVal label="Manual override" mono={false}>
              {y.manual_override ? 'Yes' : 'No'}
            </KeyVal>
          </>
        ) : (
          <>
            <KeyVal label="Daily rates cached">
              {cached} / {expected || '—'}
            </KeyVal>
            <KeyVal label="Missing">{missingCount}</KeyVal>
            <KeyVal label="Source" mono={false}>
              {y.source_label}
            </KeyVal>
            <KeyVal label="Verified" mono={false}>
              {y.verified_at ? formatDateTime(y.verified_at) : '—'}
            </KeyVal>
          </>
        )}
      </div>

      {y.source_url ? (
        <div className="px-5 pb-3 -mt-1 text-[12px] text-ink2 flex items-center gap-1.5">
          <ExternalLink className="w-3.5 h-3.5" />
          <a
            href={y.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-accent hover:underline focus-ring"
          >
            {y.source_url}
          </a>
        </div>
      ) : null}

      {hasMissing ? (
        <div className="px-5 pb-4">
          <div className="rounded-md bg-warn-bg/60 border border-warn-bg px-3 py-2">
            <div className="text-[11px] uppercase tracking-wider text-warn font-medium mb-1 flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3" />
              Missing dates ({missingCount})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {y.missing_dates.slice(0, 30).map((d) => (
                <span
                  key={d}
                  className="text-[11px] font-mono text-warn bg-surface border border-warn-bg rounded px-1.5 py-0.5"
                >
                  {formatDate(d)}
                </span>
              ))}
              {y.missing_dates.length > 30 ? (
                <span className="text-[11px] text-warn">
                  +{y.missing_dates.length - 30} more
                </span>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {y.status_reason ? (
        <div className="px-5 pb-4">
          <div className="rounded-md bg-bg/80 border border-borderc px-3 py-2 text-[12px] text-ink2">
            <span className="text-[11px] uppercase tracking-wider text-ink3 mr-2">Backend reason</span>
            {y.status_reason}
          </div>
        </div>
      ) : null}

      {(y.rate_source === 'workbook_fallback' ||
        y.rate_source === 'generated_default' ||
        y.rate_source === 'unavailable') && !y.status_reason ? (
        <div className="px-5 pb-4">
          <div className="rounded-md bg-bg/80 border border-borderc px-3 py-2 text-[12px] text-ink2">
            Effective rate provenance is{' '}
            <span className="font-medium">{sourceLabels[y.rate_source]}</span>. The backend has not
            attached a status reason for this year.
          </div>
        </div>
      ) : null}
    </Card>
  )
}

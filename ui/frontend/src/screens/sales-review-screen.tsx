import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Ban,
  Check as CheckIcon,
  CircleHelp,
  ClipboardList,
  Flag,
  Link as LinkIcon,
  LoaderCircle,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { Button, Card, Chip, KeyVal, SectionHeader, StatusDot } from '../components/ui'
import { ApiError, usePatchSaleReviewMutation, useSaleQuery, useSalesQuery } from '../lib/api'
import { formatCurrency, formatDate, formatNumber } from '../lib/format'
import type {
  CollectionTruth,
  MatchedLot,
  ReviewStatus,
  Sell,
  SellSummary,
  TruthSource,
  TruthStatus,
} from '../types/api'

const reviewStatuses: ReviewStatus[] = ['unreviewed', 'reviewed', 'flagged']
const reviewFilters: Array<'all' | ReviewStatus> = ['all', ...reviewStatuses]

const truthStatusTone: Record<TruthStatus, 'ok' | 'warn' | 'err' | 'filed' | 'neutral'> = {
  ready: 'ok',
  needs_review: 'warn',
  partial: 'warn',
  blocked: 'err',
  unknown: 'filed',
  not_implemented: 'filed',
}

const truthStatusLabel: Record<TruthStatus, string> = {
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

const reviewTone: Record<ReviewStatus, 'ok' | 'warn' | 'neutral'> = {
  unreviewed: 'neutral',
  reviewed: 'ok',
  flagged: 'warn',
}

function toUserError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return error.detail ?? 'The requested sale was not found on the backend.'
    return `${fallback} (HTTP ${error.status}${error.detail ? `: ${error.detail}` : ''})`
  }
  return fallback
}

function ReviewDot({ status }: { status: ReviewStatus }) {
  const cls: Record<ReviewStatus, string> = {
    reviewed: 'bg-ok',
    unreviewed: 'bg-ink3',
    flagged: 'bg-warn',
  }
  return <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${cls[status]}`} />
}

function TruthBanner({ truth, salesInView, totalSales }: { truth: CollectionTruth; salesInView: number; totalSales: number }) {
  const tone = truthStatusTone[truth.status]
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
            <Chip tone={tone}>{truthStatusLabel[truth.status]}</Chip>
            <Chip tone="neutral">In view: {salesInView}</Chip>
            <Chip tone="neutral">Total: {totalSales}</Chip>
          </div>
          {truth.summary ? <p className="mt-1.5 text-[13px] text-ink2 leading-5">{truth.summary}</p> : null}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Chip tone="neutral">empty: {truth.empty_meaning}</Chip>
            {truth.sources.map((src) => (
              <Chip key={src} tone="info">
                src: {sourceLabels[src]}
              </Chip>
            ))}
          </div>
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

export function SalesReviewScreen() {
  const salesQuery = useSalesQuery()
  const patchReview = usePatchSaleReviewMutation()

  const [selectedSellId, setSelectedSellId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [reviewFilter, setReviewFilter] = useState<'all' | ReviewStatus>('all')
  const [reviewStatusInput, setReviewStatusInput] = useState<ReviewStatus>('unreviewed')
  const [reviewNote, setReviewNote] = useState('')
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  const sortedItems = useMemo(() => {
    if (!salesQuery.data) return []
    return [...salesQuery.data.items].sort((a, b) => b.date.localeCompare(a.date))
  }, [salesQuery.data])

  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return sortedItems.filter((s) => {
      if (reviewFilter !== 'all' && s.review_status !== reviewFilter) return false
      if (!q) return true
      return s.ticker.toLowerCase().includes(q) || s.instrument_id.toLowerCase().includes(q)
    })
  }, [reviewFilter, searchQuery, sortedItems])

  useEffect(() => {
    if (!salesQuery.data) return
    if (salesQuery.data.items.length === 0) {
      setSelectedSellId(null)
      return
    }
    if (filteredItems.length === 0) {
      setSelectedSellId(null)
      return
    }
    if (!selectedSellId || !filteredItems.some((it) => it.id === selectedSellId)) {
      setSelectedSellId(filteredItems[0]?.id ?? null)
    }
  }, [salesQuery.data, filteredItems, selectedSellId])

  const saleQuery = useSaleQuery(selectedSellId)

  useEffect(() => {
    if (!saleQuery.data) return
    setReviewStatusInput(saleQuery.data.review_status)
    setReviewNote(saleQuery.data.note ?? '')
  }, [saleQuery.data?.id, saleQuery.data?.review_status, saleQuery.data?.note])

  async function handleSaveReview() {
    if (!selectedSellId) return
    setSaveMessage(null)
    try {
      const updated = await patchReview.mutateAsync({
        sellId: selectedSellId,
        payload: { review_status: reviewStatusInput, note: reviewNote.trim() === '' ? null : reviewNote },
      })
      setReviewStatusInput(updated.review_status)
      setReviewNote(updated.note ?? '')
      setSaveMessage('Review saved.')
    } catch (error) {
      setSaveMessage(toUserError(error, 'Saving review failed'))
    }
  }

  if (salesQuery.isLoading) {
    return (
      <div className="h-full flex">
        <div className="w-[340px] border-r border-borderc bg-surface p-5">
          <div className="h-6 w-24 animate-pulse rounded bg-borderc/60 mb-4" />
          <div className="space-y-2">
            <div className="h-16 animate-pulse rounded-lg bg-borderc/40" />
            <div className="h-16 animate-pulse rounded-lg bg-borderc/40" />
            <div className="h-16 animate-pulse rounded-lg bg-borderc/40" />
          </div>
        </div>
        <div className="flex-1 p-8">
          <div className="h-32 animate-pulse rounded-xl bg-borderc/40" />
        </div>
      </div>
    )
  }

  if (salesQuery.error || !salesQuery.data) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Sales Review" subtitle="Backend sales endpoint is required." />
        <Card className="p-5 border-err-bg">
          <div className="text-sm text-err">{toUserError(salesQuery.error, 'Could not load /api/sales.')}</div>
        </Card>
      </div>
    )
  }

  const truth = salesQuery.data.truth
  const totalSales = salesQuery.data.items.length

  return (
    <div className="h-full flex min-h-0">
      {/* LEFT pane: queue */}
      <div className="w-[340px] shrink-0 border-r border-borderc bg-surface flex flex-col min-h-0">
        <div className="px-4 pt-5 pb-3">
          <div className="text-[11px] uppercase tracking-wider text-ink3 mb-1">Sales Review</div>
          <div className="text-[17px] font-semibold tracking-tight text-ink">
            Sells — {filteredItems.length}
          </div>
        </div>
        <div className="px-4 pb-3 space-y-2">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-2 top-2.5 text-ink3" />
            <input
              placeholder="Ticker or instrument…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full border border-borderc rounded-md pl-7 pr-2 py-2 text-sm bg-bg text-ink focus-ring"
            />
          </div>
          <div className="flex gap-1 flex-wrap">
            {reviewFilters.map((k) => (
              <button
                key={k}
                onClick={() => setReviewFilter(k)}
                className={`px-2 py-0.5 rounded-full text-[11px] focus-ring ${
                  reviewFilter === k ? 'bg-accent-bg text-accent' : 'bg-borderc/50 text-ink2 hover:text-ink'
                }`}
              >
                {k === 'all' ? 'All' : k}
              </button>
            ))}
          </div>
        </div>

        <ul className="flex-1 overflow-auto divide-y divide-borderc">
          {totalSales === 0 ? (
            <li className="p-4 text-[13px] text-ink3">{truth.summary ?? 'No sales reported by backend.'}</li>
          ) : filteredItems.length === 0 ? (
            <li className="p-4 text-[13px] text-ink3">No sales match the current filter.</li>
          ) : (
            filteredItems.map((s) => (
              <li key={s.id}>
                <SaleQueueRow
                  sale={s}
                  selected={selectedSellId === s.id}
                  onSelect={() => {
                    setSelectedSellId(s.id)
                    setSaveMessage(null)
                  }}
                />
              </li>
            ))
          )}
        </ul>
      </div>

      {/* RIGHT pane: detail */}
      <div className="flex-1 overflow-auto min-w-0">
        <div className="max-w-3xl mx-auto px-8 py-8 space-y-5">
          <TruthBanner truth={truth} salesInView={filteredItems.length} totalSales={totalSales} />

          {!selectedSellId ? (
            <Card className="p-6 text-sm text-ink3">Select a sale from the queue to inspect detail.</Card>
          ) : saleQuery.isLoading ? (
            <Card className="p-6 text-sm text-ink2 flex items-center gap-2">
              <LoaderCircle className="w-4 h-4 animate-spin" />
              Loading sale detail…
            </Card>
          ) : saleQuery.error || !saleQuery.data ? (
            <Card className="p-5 border-err-bg">
              <div className="text-sm text-err">
                {toUserError(saleQuery.error, 'Could not load sale detail from backend.')}
              </div>
            </Card>
          ) : (
            <SaleDetail
              sale={saleQuery.data}
              reviewStatusInput={reviewStatusInput}
              reviewNote={reviewNote}
              onReviewStatusChange={setReviewStatusInput}
              onReviewNoteChange={setReviewNote}
              onSaveReview={handleSaveReview}
              isSaving={patchReview.isPending}
              saveMessage={saveMessage}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function SaleQueueRow({
  sale,
  selected,
  onSelect,
}: {
  sale: SellSummary
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left px-4 py-3 hover:bg-bg focus-ring ${selected ? 'bg-accent-bg/60' : ''}`}
    >
      <div className="flex items-center gap-2">
        <ReviewDot status={sale.review_status} />
        <span className="text-sm font-medium text-ink">{sale.ticker}</span>
        <span className="text-[11px] text-ink3 ml-auto whitespace-nowrap">{formatDate(sale.date)}</span>
      </div>
      <div className="flex items-center justify-between mt-0.5">
        <span className="text-[12px] text-ink2 truncate">
          {formatNumber(sale.quantity)} sh · {sale.broker}
        </span>
        <span className="text-[12px] num text-ink ml-2 whitespace-nowrap">{formatCurrency(sale.proceeds_czk)}</span>
      </div>
      <div className="mt-1 flex items-center gap-1.5 flex-wrap">
        <Chip tone={truthStatusTone[sale.truth_status]} className="!text-[10px]">
          <StatusDot status={sale.truth_status} />
          {truthStatusLabel[sale.truth_status]}
        </Chip>
        <Chip tone={reviewTone[sale.review_status]} className="!text-[10px]">
          {sale.review_status}
        </Chip>
      </div>
    </button>
  )
}

function SaleDetail({
  sale,
  reviewStatusInput,
  reviewNote,
  onReviewStatusChange,
  onReviewNoteChange,
  onSaveReview,
  isSaving,
  saveMessage,
}: {
  sale: Sell
  reviewStatusInput: ReviewStatus
  reviewNote: string
  onReviewStatusChange: (v: ReviewStatus) => void
  onReviewNoteChange: (v: string) => void
  onSaveReview: () => void
  isSaving: boolean
  saveMessage: string | null
}) {
  const matchedDiff = sale.quantity - sale.matched_quantity
  const totalGain = sale.matched_lots.reduce((acc, l) => acc + l.gain_loss_czk, 0)

  return (
    <>
      <SectionHeader
        title={`${sale.ticker} — ${formatDate(sale.date)}`}
        subtitle={`Sell evidence packet · ${sale.broker} · ${formatNumber(sale.quantity)} shares at $${sale.price_usd.toFixed(
          2,
        )}`}
        primary={
          <Button
            onClick={() =>
              onReviewStatusChange(reviewStatusInput === 'reviewed' ? 'unreviewed' : 'reviewed')
            }
            variant={reviewStatusInput === 'reviewed' ? 'secondary' : 'primary'}
          >
            <CheckIcon className="w-4 h-4" />
            {reviewStatusInput === 'reviewed' ? 'Reviewed — undo' : 'Mark reviewed'}
          </Button>
        }
        secondary={
          <Button
            variant="ghost"
            onClick={() =>
              onReviewStatusChange(reviewStatusInput === 'flagged' ? 'unreviewed' : 'flagged')
            }
          >
            <Flag className="w-4 h-4" />
            {reviewStatusInput === 'flagged' ? 'Unflag' : 'Flag'}
          </Button>
        }
      />

      {/* Header card */}
      <Card className="p-5">
        <div className="grid grid-cols-5 gap-5">
          <KeyVal label="Quantity">{formatNumber(sale.quantity)}</KeyVal>
          <KeyVal label="Sell price">${sale.price_usd.toFixed(2)}</KeyVal>
          <KeyVal label="Proceeds">{formatCurrency(sale.proceeds_czk)}</KeyVal>
          <KeyVal label="Method">{sale.method}</KeyVal>
          <KeyVal label="Matched qty">
            {formatNumber(sale.matched_quantity)}
            {matchedDiff !== 0 ? (
              <Chip tone="warn" className="ml-2">
                {matchedDiff > 0 ? `${formatNumber(matchedDiff)} sh unmatched` : `+${formatNumber(-matchedDiff)} sh over`}
              </Chip>
            ) : null}
          </KeyVal>
        </div>
        <div className="mt-4 flex items-center gap-2 text-[12px] text-ink2 flex-wrap">
          <LinkIcon className="w-3.5 h-3.5" />
          Source:
          <span className="font-mono text-ink">
            {sale.source.file}:row {sale.source.row}
          </span>
          <div className="flex-1" />
          <span>
            Classification:{' '}
            <Chip
              tone={
                sale.classification === 'taxable'
                  ? 'neutral'
                  : sale.classification === 'exempt'
                    ? 'ok'
                    : 'info'
              }
            >
              {sale.classification}
            </Chip>
          </span>
        </div>
      </Card>

      {/* Truth and provenance for the sale */}
      <Card className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-ink3 mb-2">Truth and provenance</div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip tone={truthStatusTone[sale.truth_status]}>
            <StatusDot status={sale.truth_status} />
            {truthStatusLabel[sale.truth_status]}
          </Chip>
          <Chip tone="info">instrument: {sourceLabels[sale.instrument_map_source]}</Chip>
          <Chip tone="info">review state: {sourceLabels[sale.review_state_source]}</Chip>
          {sale.truth.sources.map((src) => (
            <Chip key={src} tone="info">
              detail src: {sourceLabels[src]}
            </Chip>
          ))}
        </div>
        {sale.truth.summary ? (
          <p className="mt-2 text-[13px] text-ink2 leading-5">{sale.truth.summary}</p>
        ) : null}
        {sale.truth.reasons.length > 0 ? (
          <ul className="mt-2 space-y-0.5 text-[12px] text-ink2">
            {sale.truth.reasons.map((r) => (
              <li key={`${r.code}-${r.message}`}>
                • <span className="font-mono">{r.code}</span>: {r.message}
              </li>
            ))}
          </ul>
        ) : null}
      </Card>

      {/* Matched lots */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <h2 className="text-sm font-semibold text-ink2">Matched buy lots ({sale.matched_lots.length})</h2>
          <div className="flex-1" />
          <span className="text-[12px] text-ink3 num">
            Total gain/loss:{' '}
            <span className={totalGain >= 0 ? 'text-ok' : 'text-err'}>{formatCurrency(totalGain)}</span>
          </span>
        </div>
        {sale.matched_lots.length === 0 ? (
          <Card className="p-5 text-sm text-ink3">No matched lot lines were provided by the backend.</Card>
        ) : (
          <div className="space-y-3">
            {sale.matched_lots.map((l) => (
              <BuyLotCard key={l.lot_id} l={l} />
            ))}
          </div>
        )}
      </div>

      {/* Reviewer note + save */}
      <Card className="p-5">
        <div className="text-[11px] uppercase tracking-wider text-ink3 mb-2">Reviewer note</div>
        <textarea
          value={reviewNote}
          onChange={(e) => onReviewNoteChange(e.target.value)}
          rows={3}
          placeholder="Add any context for the audit trail…"
          className="w-full border border-borderc rounded-md px-3 py-2 text-sm bg-surface text-ink focus-ring resize-y num"
        />
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <label className="text-[12px] text-ink2 inline-flex items-center gap-2">
            Review status
            <select
              value={reviewStatusInput}
              onChange={(e) => onReviewStatusChange(e.target.value as ReviewStatus)}
              className="border border-borderc rounded-md px-2 py-1 text-sm bg-surface text-ink focus-ring"
            >
              {reviewStatuses.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <div className="flex-1" />
          <Button onClick={onSaveReview} disabled={isSaving}>
            {isSaving ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <CheckIcon className="w-4 h-4" />}
            Save review
          </Button>
        </div>
        {saveMessage ? (
          <div
            className={`mt-3 text-[12px] rounded-md px-3 py-2 ${
              saveMessage.toLowerCase().includes('failed') || saveMessage.includes('HTTP')
                ? 'bg-err-bg text-err'
                : 'bg-ok-bg text-ok'
            }`}
          >
            {saveMessage}
          </div>
        ) : null}
      </Card>
    </>
  )
}

function BuyLotCard({ l }: { l: MatchedLot }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <ClipboardList className="w-4 h-4 text-ink2 shrink-0" />
        <span className="font-mono text-[13px] text-ink">{l.lot_id}</span>
        <Chip tone="neutral">{l.broker}</Chip>
        <span className="text-[12px] text-ink3 font-mono">
          {l.source.file}:row {l.source.row}
        </span>
        <div className="flex-1" />
        {l.time_test_exempt ? (
          <Chip tone="ok">
            <CheckIcon className="w-3 h-3" />
            3y time test · exempt
          </Chip>
        ) : (
          <Chip tone="neutral">{l.holding_days} holding days</Chip>
        )}
      </div>
      <div className="grid grid-cols-6 gap-3 text-sm">
        <KeyVal label="Buy date" mono={false}>
          {formatDate(l.buy_date)}
        </KeyVal>
        <KeyVal label="Qty">{formatNumber(l.quantity)}</KeyVal>
        <KeyVal label="Buy (USD)">${l.buy_price_usd.toFixed(2)}</KeyVal>
        <KeyVal label="Sell (USD)">${l.sell_price_usd.toFixed(2)}</KeyVal>
        <KeyVal label="FX buy / sell">
          {l.fx_buy.toFixed(3)} / {l.fx_sell.toFixed(3)}
        </KeyVal>
        <KeyVal label="Gain / loss">
          <span className={l.time_test_exempt ? 'text-filed' : l.gain_loss_czk >= 0 ? 'text-ok' : 'text-err'}>
            {formatCurrency(l.gain_loss_czk)}
          </span>
        </KeyVal>
      </div>
      <div className="grid grid-cols-3 gap-3 text-sm mt-2 pt-3 border-t border-borderc">
        <KeyVal label="Cost basis">{formatCurrency(l.cost_basis_czk)}</KeyVal>
        <KeyVal label="Proceeds">{formatCurrency(l.proceeds_czk)}</KeyVal>
        <KeyVal label="Net">{formatCurrency(l.proceeds_czk - l.cost_basis_czk)}</KeyVal>
      </div>
    </Card>
  )
}

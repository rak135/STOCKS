import { AlertTriangle, FolderOpen, Rows3, ShieldCheck } from 'lucide-react'
import { Panel } from '../components/panel'
import { useImportQuery } from '../lib/api'
import { compactPath, formatDate, formatNumber } from '../lib/format'

export function ImportScreen() {
  const { data, isLoading, error } = useImportQuery()

  if (isLoading) {
    return <LoadingPanel title="Import" />
  }

  if (error || !data) {
    return <ErrorPanel title="Import" message="The frontend could not load `/api/import` from the backend." />
  }

  return (
    <div className="grid gap-4">
      <Panel
        eyebrow="Input confidence"
        title="Import"
        subtitle="The backend remains the importer of record. This screen simply reflects what FastAPI says it found in `.csv/`."
      >
        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
          <div className="rounded-[1.5rem] bg-stone-900 px-5 py-5 text-stone-50">
            <div className="flex items-center gap-3 text-sm font-semibold">
              <FolderOpen className="h-4 w-4" />
              Source folder
            </div>
            <p className="mt-3 font-mono text-sm text-stone-200">{data.folder}</p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <Metric label="Files" value={String(data.files.length)} />
              <Metric label="Trade rows" value={formatNumber(data.total_trade_rows)} />
              <Metric label="Ignored rows" value={formatNumber(data.total_ignored_rows)} />
            </div>
          </div>
          <div className="rounded-[1.5rem] border border-stone-200/80 bg-stone-50/80 p-5">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">Current import posture</div>
            <div className="mt-4 flex items-start gap-3">
              <div className="rounded-xl bg-emerald-100 p-2 text-emerald-700">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <div>
                <div className="text-sm font-semibold text-stone-900">Real CSV inputs detected</div>
                <p className="mt-1 text-sm leading-6 text-stone-600">
                  {data.files.length} files are exposed by `/api/import`, and the frontend does not inspect raw workbook sheets.
                </p>
              </div>
            </div>
          </div>
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        {data.files.map((file) => (
          <Panel
            key={file.name}
            eyebrow={file.broker}
            title={file.name}
            subtitle={`${compactPath(data.folder)}\\${file.name}`}
            actions={
              <span
                className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${
                  file.status === 'ok'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : file.status === 'warnings'
                      ? 'border-amber-200 bg-amber-50 text-amber-700'
                      : 'border-rose-200 bg-rose-50 text-rose-700'
                }`}
              >
                {file.status === 'ok' ? 'OK' : file.status === 'warnings' ? 'Warnings' : 'Error'}
              </span>
            }
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-[1.4rem] bg-stone-50/90 p-4">
                <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
                  <Rows3 className="h-4 w-4" />
                  Row counts
                </div>
                <div className="grid gap-2 text-sm text-stone-700">
                  <KeyValue label="Total rows" value={formatNumber(file.total_rows)} />
                  <KeyValue label="Trade rows" value={formatNumber(file.trade_rows)} />
                  <KeyValue label="Ignored rows" value={formatNumber(file.ignored_rows)} />
                  <KeyValue label="Position rows" value={formatNumber(file.position_rows)} />
                </div>
              </div>
              <div className="rounded-[1.4rem] bg-stone-50/90 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">Coverage</div>
                <div className="mt-3 grid gap-2 text-sm text-stone-700">
                  <KeyValue label="Account" value={file.account || 'Primary'} />
                  <KeyValue label="Min trade date" value={formatDate(file.min_trade_date)} />
                  <KeyValue label="Max trade date" value={formatDate(file.max_trade_date)} />
                  <KeyValue label="Symbols" value={formatNumber(file.unique_symbols.length)} />
                </div>
              </div>
            </div>
            <div className="mt-4 rounded-[1.4rem] border border-stone-200/80 bg-white/70 p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">Unique symbols</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {file.unique_symbols.map((symbol) => (
                  <span key={symbol} className="rounded-full bg-stone-900/5 px-3 py-1 text-xs font-semibold text-stone-700">
                    {symbol}
                  </span>
                ))}
              </div>
              <div className="mt-4">
                {file.warnings.length > 0 ? (
                  <div className="space-y-2">
                    {file.warnings.map((warning) => (
                      <div
                        key={warning}
                        className="flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                      >
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                        <span>{warning}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                    No import warnings reported for this file.
                  </div>
                )}
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  )
}

function LoadingPanel({ title }: { title: string }) {
  return (
    <Panel eyebrow="Loading" title={title} subtitle="Waiting for the backend to answer.">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="h-44 animate-pulse rounded-[1.5rem] bg-stone-200/80" />
        <div className="h-44 animate-pulse rounded-[1.5rem] bg-stone-200/80" />
      </div>
    </Panel>
  )
}

function ErrorPanel({ title, message }: { title: string; message: string }) {
  return (
    <Panel eyebrow="Connection issue" title={title} subtitle={message} tone="muted">
      <div className="rounded-[1.4rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        Check that `py -3 -m stock_tax_app.backend.main` is running on `127.0.0.1:8787`.
      </div>
    </Panel>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.2rem] bg-white/10 px-3 py-3">
      <div className="text-[11px] uppercase tracking-[0.18em] text-stone-300">{label}</div>
      <div className="mt-2 text-lg font-semibold text-white">{value}</div>
    </div>
  )
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-stone-500">{label}</span>
      <span className="text-right font-medium text-stone-900">{value}</span>
    </div>
  )
}

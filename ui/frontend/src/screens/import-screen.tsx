import { AlertTriangle, FileText, FolderOpen } from 'lucide-react'
import { Card, Chip, KeyVal, SectionHeader } from '../components/ui'
import { useImportQuery } from '../lib/api'
import { compactPath, formatDate, formatNumber } from '../lib/format'

export function ImportScreen() {
  const { data, isLoading, error } = useImportQuery()

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Import" subtitle="Loading CSV folder state from backend." />
        <div className="space-y-3">
          <div className="h-16 animate-pulse rounded-xl bg-borderc/50" />
          <div className="h-32 animate-pulse rounded-xl bg-borderc/50" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <SectionHeader title="Import" subtitle="Backend import endpoint is required." />
        <Card className="p-5 border-err-bg">
          <div className="text-sm text-err">
            Could not load <span className="font-mono">/api/import</span>. Make sure the backend is running.
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <SectionHeader title="Import" subtitle="Is the CSV folder correct and complete?" />

      <Card className="p-4 mb-5 flex items-center gap-3">
        <FolderOpen className="w-5 h-5 text-ink2" />
        <div className="font-mono text-sm text-ink truncate" title={data.folder}>
          {compactPath(data.folder)}
        </div>
        <span className="text-ink3 text-xs ml-auto whitespace-nowrap">
          {data.files.length} files · {formatNumber(data.total_trade_rows)} trade rows · {formatNumber(data.total_ignored_rows)} ignored
        </span>
      </Card>

      {data.files.length === 0 ? (
        <Card className="p-6 text-sm text-ink3">No CSV files were detected by the backend.</Card>
      ) : (
        <div className="space-y-3">
          {data.files.map((f) => {
            const tone = f.status === 'ok' ? 'ok' : f.status === 'warnings' ? 'warn' : 'err'
            const label = f.status === 'ok' ? 'OK' : f.status === 'warnings' ? 'Warnings' : 'Error'
            return (
              <Card key={f.name} className="p-5">
                <div className="flex items-center gap-4 mb-3">
                  <FileText className="w-5 h-5 text-ink2 shrink-0" />
                  <div className="font-mono text-sm text-ink">{f.name}</div>
                  <Chip tone="neutral">{f.broker}</Chip>
                  {f.account_currency ? <Chip tone="neutral">{f.account_currency}</Chip> : null}
                  <div className="flex-1" />
                  <Chip tone={tone}>{label}</Chip>
                </div>
                <div className="grid grid-cols-4 gap-4">
                  <KeyVal label="Total rows">{formatNumber(f.total_rows)}</KeyVal>
                  <KeyVal label="Trades">{formatNumber(f.trade_rows)}</KeyVal>
                  <KeyVal label="Ignored">{formatNumber(f.ignored_rows)}</KeyVal>
                  <KeyVal label="Symbols">{formatNumber(f.unique_symbols.length)}</KeyVal>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-4 text-[12px] text-ink2">
                  <div>
                    <span className="text-ink3">Account:</span> {f.account || 'Primary'}
                  </div>
                  <div>
                    <span className="text-ink3">Min date:</span> {formatDate(f.min_trade_date)}
                  </div>
                  <div>
                    <span className="text-ink3">Max date:</span> {formatDate(f.max_trade_date)}
                  </div>
                </div>
                {f.warnings.length > 0 ? (
                  <ul className="mt-3 space-y-1">
                    {f.warnings.map((w, i) => (
                      <li key={i} className="text-xs text-warn flex items-center gap-2">
                        <AlertTriangle className="w-3 h-3" />
                        {w}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {f.unique_symbols.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {f.unique_symbols.slice(0, 24).map((s) => (
                      <span
                        key={s}
                        className="text-[11px] font-mono text-ink2 bg-borderc/40 rounded-md px-1.5 py-0.5"
                      >
                        {s}
                      </span>
                    ))}
                    {f.unique_symbols.length > 24 ? (
                      <span className="text-[11px] text-ink3">+{f.unique_symbols.length - 24} more</span>
                    ) : null}
                  </div>
                ) : null}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

import {
  AlertTriangle,
  Ban,
  CircleHelp,
  Eye,
  Lock,
  ShieldCheck,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Card, Chip, SectionHeader, StatusDot } from '../components/ui'
import { useSettingsQuery } from '../lib/api'
import type {
  AppSettings,
  SettingEditability,
  SettingFieldTruth,
  TruthReason,
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

const sourceLabel: Record<TruthSource, string> = {
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

const editabilityLabel: Record<SettingEditability, string> = {
  editable: 'Editable',
  read_only: 'Read-only',
  display_only: 'Display-only',
  not_implemented: 'Not implemented',
}

const editabilityTone: Record<SettingEditability, 'ok' | 'warn' | 'filed' | 'neutral'> = {
  editable: 'ok',
  read_only: 'neutral',
  display_only: 'filed',
  not_implemented: 'filed',
}

export function SettingsScreen() {
  const { data, isLoading, error } = useSettingsQuery()

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto px-8 py-8">
        <SectionHeader title="Settings" subtitle="Loading settings from backend." />
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
      <div className="max-w-3xl mx-auto px-8 py-8">
        <SectionHeader title="Settings" subtitle="Backend settings endpoint is required." />
        <Card className="p-5 border-err-bg">
          <div className="text-sm text-err">
            Could not load <span className="font-mono">/api/settings</span>. Make sure the backend is running.
          </div>
        </Card>
      </div>
    )
  }

  const fxMethodLabel = data.default_fx_method === 'FX_DAILY_CNB' ? 'CNB daily' : 'GFŘ yearly'

  return (
    <div className="max-w-3xl mx-auto px-8 py-8">
      <SectionHeader
        title="Settings"
        subtitle="Local app configuration. This view is display-only — no settings mutation endpoint exists."
        primary={
          <button
            type="button"
            disabled
            title="No backend settings mutation endpoint exists yet."
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium bg-surface border border-borderc text-ink3 opacity-60 cursor-not-allowed"
          >
            <Lock className="w-4 h-4" />
            Save not wired
          </button>
        }
      />

      <DisplayOnlyBanner audit={data} />

      <Fieldset title="Paths">
        <Field name="project_folder" label="Project folder" value={data.project_folder} field={data.field_meta.project_folder} mono />
        <Field name="csv_folder" label="CSV folder" value={data.csv_folder} field={data.field_meta.csv_folder} mono />
        <Field name="output_path" label="Output workbook" value={data.output_path} field={data.field_meta.output_path} mono />
        <Field name="cache_folder" label="Cache folder" value={data.cache_folder} field={data.field_meta.cache_folder} mono />
      </Fieldset>

      <Fieldset title="Calculation defaults">
        <Field
          name="default_tax_rate"
          label="Default tax rate"
          value={`${(data.default_tax_rate * 100).toFixed(2)}%`}
          field={data.field_meta.default_tax_rate}
        />
        <Field
          name="default_fx_method"
          label="Default FX method"
          value={fxMethodLabel}
          field={data.field_meta.default_fx_method}
        />
        <Field
          name="default_100k"
          label="Default 100k exemption"
          value={data.default_100k ? 'On' : 'Off'}
          field={data.field_meta.default_100k}
        />
      </Fieldset>

      <Fieldset title="Tolerances">
        <Field
          name="unmatched_qty_tolerance"
          label="Unmatched quantity tolerance (shares)"
          value={data.unmatched_qty_tolerance.toString()}
          field={data.field_meta.unmatched_qty_tolerance}
        />
        <Field
          name="position_reconciliation_tolerance"
          label="Yahoo position reconciliation tolerance (shares)"
          value={data.position_reconciliation_tolerance.toString()}
          field={data.field_meta.position_reconciliation_tolerance}
        />
      </Fieldset>

      <Fieldset title="Backup &amp; lock policy">
        <Field
          name="backup_on_recalc"
          label="Backup workbook on every recalculate"
          value={data.backup_on_recalc ? 'Yes' : 'No'}
          field={data.field_meta.backup_on_recalc}
        />
        <Field
          name="require_confirm_unlock"
          label="Require confirmation to unlock a year"
          value={data.require_confirm_unlock ? 'Yes' : 'No'}
          field={data.field_meta.require_confirm_unlock}
        />
        <Field
          name="keep_n_snapshots"
          label="Snapshots kept per year"
          value={data.keep_n_snapshots.toString()}
          field={data.field_meta.keep_n_snapshots}
        />
      </Fieldset>

      <Fieldset title="Validation">
        <Field
          name="excel_validation"
          label="Excel validation"
          value={data.excel_validation}
          field={data.field_meta.excel_validation}
        />
      </Fieldset>

      <DomainSourcesSection sources={data.domain_sources} />
    </div>
  )
}

function DisplayOnlyBanner({ audit }: { audit: AppSettings }) {
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
      className={`p-4 mb-6 ${
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
            <span className="text-sm font-medium text-ink">Settings truth</span>
            <Chip tone={tone}>
              <StatusDot status={audit.truth_status} />
              {truthLabel[audit.truth_status]}
            </Chip>
            <Chip tone="filed">
              <Eye className="w-3 h-3" />
              Display-only
            </Chip>
            <Chip tone="filed">Editing not implemented</Chip>
          </div>
          <p className="mt-1.5 text-[13px] text-ink2 leading-5">
            Backend exposes <span className="font-mono">GET /api/settings</span> only. There is no settings
            mutation endpoint yet, so this room shows the live configuration but cannot save changes.
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

function Fieldset({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-6">
      <h2 className="text-[11px] uppercase tracking-wider text-ink3 mb-2">{title}</h2>
      <Card className="p-5 space-y-4">{children}</Card>
    </section>
  )
}

function Field({
  name,
  label,
  value,
  field,
  mono = false,
}: {
  name: string
  label: string
  value: string
  field?: SettingFieldTruth
  mono?: boolean
}) {
  return (
    <div>
      <div className="flex items-baseline gap-3 flex-wrap mb-1.5">
        <label className="text-[12px] text-ink2" htmlFor={`set-${name}`}>
          {label}
        </label>
        {field ? (
          <>
            <Chip tone={editabilityTone[field.editability]}>{editabilityLabel[field.editability]}</Chip>
            <Chip tone={sourceTone[field.source]}>src: {sourceLabel[field.source]}</Chip>
            {field.status !== 'ready' ? (
              <Chip tone={truthTone[field.status]}>
                <StatusDot status={field.status} />
                {truthLabel[field.status]}
              </Chip>
            ) : null}
          </>
        ) : (
          <Chip tone="filed">no field metadata</Chip>
        )}
      </div>
      <input
        id={`set-${name}`}
        readOnly
        disabled
        value={value}
        title="Settings are display-only. No mutation endpoint is wired."
        className={`w-full border border-borderc rounded-md px-2 py-1.5 text-sm bg-bg text-ink2 cursor-not-allowed ${
          mono ? 'font-mono' : ''
        }`}
      />
      {field?.reason ? <p className="mt-1 text-[12px] text-ink3 italic">{field.reason}</p> : null}
    </div>
  )
}

function DomainSourcesSection({ sources }: { sources: Record<string, TruthSource> }) {
  const entries = Object.entries(sources)
  if (entries.length === 0) {
    return null
  }

  const buckets: Record<TruthSource, string[]> = {
    project_state: [],
    ui_state: [],
    workbook_fallback: [],
    calculated: [],
    generated_default: [],
    cnb_cache: [],
    static_config: [],
    unavailable: [],
  }
  for (const [domain, src] of entries) {
    buckets[src].push(domain)
  }

  const order: TruthSource[] = [
    'project_state',
    'ui_state',
    'cnb_cache',
    'calculated',
    'static_config',
    'workbook_fallback',
    'generated_default',
    'unavailable',
  ]
  const nonEmpty = order.filter((src) => buckets[src].length > 0)
  const flagged = (['workbook_fallback', 'generated_default', 'unavailable'] as const).filter(
    (src) => buckets[src].length > 0,
  )

  return (
    <section className="mb-6">
      <h2 className="text-[11px] uppercase tracking-wider text-ink3 mb-2">Domain ownership</h2>

      {flagged.length > 0 ? (
        <Card className="p-4 mb-3 border-warn-bg bg-warn-bg/30">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-warn shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="text-sm font-medium text-ink mb-1">Non-canonical domains visible</div>
              <p className="text-[13px] text-ink2 leading-5 mb-2">
                The backend reports domains whose effective values still come from the workbook, generated
                defaults, or are entirely unavailable. They must remain visible until they are migrated.
              </p>
              <div className="flex flex-wrap gap-1.5">
                {flagged.flatMap((src) =>
                  buckets[src].map((d) => (
                    <Chip key={`${src}-${d}`} tone={sourceTone[src]}>
                      {d} · {sourceLabel[src]}
                    </Chip>
                  )),
                )}
              </div>
            </div>
          </div>
        </Card>
      ) : null}

      <Card>
        <table className="w-full text-sm">
          <thead className="text-[11px] uppercase text-ink3 tracking-wider">
            <tr className="text-left">
              <th className="px-5 py-2 font-normal">Source</th>
              <th className="px-5 py-2 font-normal">Domains</th>
            </tr>
          </thead>
          <tbody>
            {nonEmpty.map((src) => (
              <tr key={src} className="border-t border-borderc/60">
                <td className="px-5 py-3 align-top w-48">
                  <Chip tone={sourceTone[src]}>{sourceLabel[src]}</Chip>
                </td>
                <td className="px-5 py-3">
                  <div className="flex flex-wrap gap-1.5">
                    {buckets[src].map((d) => (
                      <span
                        key={d}
                        className="text-[12px] font-mono text-ink2 bg-borderc/40 rounded-md px-1.5 py-0.5"
                      >
                        {d}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </section>
  )
}

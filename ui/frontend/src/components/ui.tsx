import type { ButtonHTMLAttributes, PropsWithChildren, ReactNode } from 'react'

type Tone = 'neutral' | 'info' | 'ok' | 'warn' | 'err' | 'filed'

const chipTones: Record<Tone, string> = {
  neutral: 'bg-borderc/60 text-ink2',
  info: 'bg-accent-bg text-accent',
  ok: 'bg-ok-bg text-ok',
  warn: 'bg-warn-bg text-warn',
  err: 'bg-err-bg text-err',
  filed: 'bg-filed-bg text-filed',
}

export function Chip({
  tone = 'neutral',
  className = '',
  children,
}: PropsWithChildren<{ tone?: Tone; className?: string }>) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${chipTones[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

const buttonVariants: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-white hover:bg-[#B3573A]',
  secondary: 'bg-surface border border-borderc text-ink hover:bg-bg',
  ghost: 'text-ink2 hover:text-ink hover:bg-borderc/40',
  danger: 'bg-surface border border-err-bg text-err hover:bg-err-bg',
}

export function Button({
  variant = 'primary',
  className = '',
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium focus-ring transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${buttonVariants[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}

export function Card({
  children,
  className = '',
  raised = false,
}: PropsWithChildren<{ className?: string; raised?: boolean }>) {
  return (
    <div
      className={`rounded-xl border border-borderc ${raised ? 'bg-raised shadow-[0_1px_2px_rgba(0,0,0,0.04)]' : 'bg-surface'} ${className}`}
    >
      {children}
    </div>
  )
}

export function SectionHeader({
  title,
  subtitle,
  primary,
  secondary,
}: {
  title: string
  subtitle?: string
  primary?: ReactNode
  secondary?: ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle ? <p className="text-sm text-ink2 mt-1 max-w-xl">{subtitle}</p> : null}
      </div>
      {(primary || secondary) && (
        <div className="flex items-center gap-2 shrink-0">
          {secondary}
          {primary}
        </div>
      )}
    </div>
  )
}

export function KeyVal({
  label,
  children,
  mono = true,
  className = '',
}: PropsWithChildren<{ label: string; mono?: boolean; className?: string }>) {
  return (
    <div className={className}>
      <div className="text-[11px] uppercase tracking-wider text-ink3 mb-1">{label}</div>
      <div className={`text-sm text-ink ${mono ? 'num' : ''}`}>{children}</div>
    </div>
  )
}

export function EmptyState({
  title,
  description,
  children,
}: PropsWithChildren<{ title: string; description?: string }>) {
  return (
    <Card className="p-8 text-center">
      <div className="text-sm font-semibold text-ink">{title}</div>
      {description ? <p className="mt-2 text-sm text-ink2 max-w-md mx-auto leading-6">{description}</p> : null}
      {children ? <div className="mt-4">{children}</div> : null}
    </Card>
  )
}

type StatusTone = 'ready' | 'needs_review' | 'blocked' | 'partial' | 'unknown' | 'not_implemented'

export function StatusDot({ status }: { status: StatusTone }) {
  const cls: Record<StatusTone, string> = {
    ready: 'bg-ok',
    needs_review: 'bg-warn',
    partial: 'bg-warn',
    blocked: 'bg-err',
    unknown: 'bg-ink3',
    not_implemented: 'bg-ink3',
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${cls[status]}`} />
}

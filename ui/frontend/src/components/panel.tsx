import type { PropsWithChildren, ReactNode } from 'react'

type PanelProps = PropsWithChildren<{
  eyebrow?: string
  title?: string
  subtitle?: string
  actions?: ReactNode
  tone?: 'default' | 'muted' | 'frozen'
}>

const toneClasses: Record<NonNullable<PanelProps['tone']>, string> = {
  default: 'border-stone-200/80 bg-white/82',
  muted: 'border-stone-200/70 bg-stone-50/80',
  frozen: 'border-stone-300/80 bg-[linear-gradient(135deg,_rgba(245,245,244,0.96),_rgba(231,229,228,0.92))]',
}

export function Panel({ eyebrow, title, subtitle, actions, children, tone = 'default' }: PanelProps) {
  return (
    <section className={`rounded-[1.75rem] border p-5 shadow-[0_18px_40px_rgba(70,63,58,0.08)] ${toneClasses[tone]}`}>
      {(eyebrow || title || subtitle || actions) && (
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            {eyebrow ? (
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">{eyebrow}</p>
            ) : null}
            {title ? <h3 className="mt-2 font-display text-2xl text-stone-900">{title}</h3> : null}
            {subtitle ? <p className="mt-2 max-w-3xl text-sm leading-6 text-stone-600">{subtitle}</p> : null}
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      )}
      {children}
    </section>
  )
}

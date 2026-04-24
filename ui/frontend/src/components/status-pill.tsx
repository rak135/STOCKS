type Status = 'ready' | 'needs_review' | 'blocked'

const statusClasses: Record<Status, string> = {
  ready: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  needs_review: 'border-amber-200 bg-amber-50 text-amber-700',
  blocked: 'border-rose-200 bg-rose-50 text-rose-700',
}

const statusLabels: Record<Status, string> = {
  ready: 'Ready',
  needs_review: 'Needs review',
  blocked: 'Blocked',
}

export function StatusPill({ status }: { status: Status }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${statusClasses[status]}`}>
      {statusLabels[status]}
    </span>
  )
}

import { Chip, StatusDot } from './ui'

type Status = 'ready' | 'needs_review' | 'blocked'

const tones: Record<Status, 'ok' | 'warn' | 'err'> = {
  ready: 'ok',
  needs_review: 'warn',
  blocked: 'err',
}

const labels: Record<Status, string> = {
  ready: 'Ready',
  needs_review: 'Needs review',
  blocked: 'Blocked',
}

export function StatusPill({ status }: { status: Status }) {
  return (
    <Chip tone={tones[status]}>
      <StatusDot status={status} />
      {labels[status]}
    </Chip>
  )
}

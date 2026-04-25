import { Construction } from 'lucide-react'
import { Card, Chip, SectionHeader } from '../components/ui'

export function ComingNextScreen({
  title,
  subtitle,
  description,
}: {
  title: string
  subtitle?: string
  description?: string
}) {
  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <SectionHeader title={title} subtitle={subtitle} primary={<Chip tone="filed">Not implemented</Chip>} />
      <Card className="p-8">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-full grid place-items-center bg-filed-bg text-filed shrink-0">
            <Construction className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="text-xs uppercase tracking-wider text-ink3 mb-1">Reserved room</div>
            <div className="text-[18px] font-semibold tracking-tight text-ink mb-1">Backend not wired yet</div>
            <p className="text-sm text-ink2 leading-6 max-w-2xl">
              {description ??
                'This screen is intentionally honest about what is not yet connected. The shell, navigation, and visual system match the rest of the cockpit so future backend work can land here without restyling.'}
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}

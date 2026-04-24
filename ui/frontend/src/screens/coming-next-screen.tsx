import { Sparkles } from 'lucide-react'
import { Panel } from '../components/panel'

export function ComingNextScreen({ title, description }: { title: string; description: string }) {
  return (
    <div className="grid gap-4">
      <Panel eyebrow="Reserved space" title={title} subtitle={description} tone="muted">
        <div className="rounded-[1.5rem] border border-dashed border-stone-300/80 bg-white/55 p-8 text-center">
          <div className="mx-auto inline-flex rounded-full bg-stone-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-stone-50">
            Coming next
          </div>
          <div className="mt-5 flex justify-center">
            <div className="rounded-[1.5rem] bg-stone-900/5 p-4 text-stone-600">
              <Sparkles className="h-7 w-7" />
            </div>
          </div>
          <p className="mx-auto mt-5 max-w-2xl text-sm leading-6 text-stone-600">
            The shell, routing, and layout are already in place so future work can land here without moving the navigation or redesigning the frame.
          </p>
        </div>
      </Panel>
    </div>
  )
}

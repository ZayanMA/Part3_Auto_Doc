'use client'
import { useDemoStore } from '@/lib/useDemoStore'

export default function JobProgressBar() {
  const { phase, totalUnits, doneUnits, patchTotalUnits, patchDoneUnits } = useDemoStore()

  const isPatch = phase === 'patch-running' || phase === 'patch-done'
  const total = isPatch ? patchTotalUnits : totalUnits
  const done = isPatch ? patchDoneUnits : doneUnits
  const pct = total > 0 ? Math.round((done / total) * 100) : 0
  const running = phase === 'running' || phase === 'patch-running'

  if (phase === 'idle') return null

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-500">
        <span>
          {running
            ? done >= total && total > 0
              ? 'Finalizing — generating repository overview...'
              : `Processing unit ${Math.min(done + 1, total)} of ${total}`
            : `Done — ${done} of ${total} units`}
        </span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        {running && total === 0 ? (
          <div className="h-full shimmer rounded-full" style={{ width: '30%' }} />
        ) : (
          <div
            className={`h-full rounded-full transition-all duration-500 ${running ? 'shimmer' : 'bg-green-500'}`}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  )
}

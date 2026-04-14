'use client'
import { useDemoStore } from '@/lib/useDemoStore'

export default function JobProgressBar() {
  const {
    phase,
    totalUnits,
    doneUnits,
    patchTotalUnits,
    patchDoneUnits,
    currentJobPhase,
    currentJobPhaseMessage,
  } = useDemoStore()

  const isPatch = phase === 'patch-running' || phase === 'patch-done'
  const total = isPatch ? patchTotalUnits : totalUnits
  const done = isPatch ? patchDoneUnits : doneUnits
  const pct = total > 0 ? Math.round((done / total) * 100) : 0
  const running = phase === 'running' || phase === 'patch-running'
  const waitingForTotals = running && total === 0

  function phaseLabel(rawPhase: string | null | undefined): string {
    switch (rawPhase) {
      case 'seeding_base':
        return 'Preparing base documentation for comparison…'
      case 'cloning':
        return 'Cloning repository'
      case 'extracting':
        return 'Extracting ZIP archive'
      case 'discovering_files':
        return 'Discovering relevant files'
      case 'grouping_units':
        return 'Grouping files into documentation units'
      case 'building_graph':
        return 'Building repository import graph'
      case 'naming_units':
        return 'Naming documentation units'
      case 'filtering_units':
        return 'Filtering documentation units'
      case 'generating':
        return 'Generating documentation'
      case 'finalizing':
        return 'Building repository overview'
      case 'done':
        return 'Documentation generation complete'
      case 'failed':
        return 'Job failed'
      default:
        return 'Preparing job'
    }
  }

  if (phase === 'idle') return null

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-500">
        <span>
          {waitingForTotals
            ? (currentJobPhaseMessage ?? phaseLabel(currentJobPhase))
            : running
            ? done >= total && total > 0
              ? 'Finalizing — generating repository overview...'
              : `Processing unit ${Math.min(done + 1, total)} of ${total}`
            : `Done — ${done} of ${total} units`}
        </span>
        <span>{waitingForTotals ? '...' : `${pct}%`}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        {waitingForTotals ? (
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

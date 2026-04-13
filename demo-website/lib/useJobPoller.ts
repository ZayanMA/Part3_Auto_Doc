'use client'
import { useEffect, useRef } from 'react'
import { JobEvent } from './types'
import { getJob } from './api'

const POLL_INTERVAL_MS = 2000
const TIMEOUT_MS = 20 * 60 * 1000 // 20 minutes

export function useJobPoller(
  jobId: string | null,
  onEvent: (event: JobEvent) => void,
  active: boolean
) {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Refs so the interval closure always reads the latest values without re-registering
  const startedRef = useRef(false)
  const prevDoneRef = useRef(0)
  const startTimeRef = useRef(0)

  useEffect(() => {
    if (!jobId || !active) return

    // Reset per-job state
    startedRef.current = false
    prevDoneRef.current = 0
    startTimeRef.current = Date.now()

    intervalRef.current = setInterval(async () => {
      // Hard timeout — prevents polling forever if backend is gone
      if (Date.now() - startTimeRef.current > TIMEOUT_MS) {
        clearInterval(intervalRef.current!)
        intervalRef.current = null
        onEvent({ event: 'job_failed', job_id: jobId, error: 'Job timed out after 20 minutes' })
        return
      }

      try {
        const job = await getJob(jobId)

        // Emit job_started once (when we first see the job is past pending)
        if (!startedRef.current && job.status !== 'pending') {
          startedRef.current = true
          onEvent({
            event: 'job_started',
            job_id: jobId,
            total_units: job.total_units ?? 0,
          })
        }

        // Emit a synthetic unit_done whenever done_units advances
        const currentDone: number = job.done_units ?? 0
        if (currentDone > prevDoneRef.current) {
          prevDoneRef.current = currentDone
          onEvent({
            event: 'unit_done',
            job_id: jobId,
            name: `unit ${currentDone}`,
            status: 'generated',
            total_units: job.total_units ?? 0,
            done_units: currentDone,
          })
        }

        if (job.status === 'done') {
          clearInterval(intervalRef.current!)
          intervalRef.current = null
          const total = job.total_units ?? job.units?.length ?? 0
          onEvent({
            event: 'job_done',
            job_id: jobId,
            units: job.units,
            repo_doc: job.repo_doc,
            total_units: total,
            done_units: total,
          })
        } else if (job.status === 'failed') {
          clearInterval(intervalRef.current!)
          intervalRef.current = null
          onEvent({ event: 'job_failed', job_id: jobId, error: job.error })
        }
      } catch (_) {
        // Transient network error — keep polling
      }
    }, POLL_INTERVAL_MS)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [jobId, active])
}

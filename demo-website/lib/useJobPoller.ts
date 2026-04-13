'use client'
import { useEffect, useRef } from 'react'
import { JobEvent } from './types'
import { getStreamUrl, getJob } from './api'

export function useJobPoller(
  jobId: string | null,
  onEvent: (event: JobEvent) => void,
  active: boolean
) {
  const esRef = useRef<EventSource | null>(null)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!jobId || !active) return

    let sseActive = false

    // Try SSE first
    try {
      const es = new EventSource(getStreamUrl(jobId))
      esRef.current = es
      sseActive = true

      es.onmessage = (e) => {
        try {
          const event: JobEvent = JSON.parse(e.data)
          onEvent(event)
          if (event.event === 'job_done' || event.event === 'job_failed') {
            es.close()
          }
        } catch (_) {}
      }

      es.onerror = () => {
        es.close()
        sseActive = false
        // Fall back to polling
        startPolling()
      }
    } catch (_) {
      startPolling()
    }

    function startPolling() {
      if (pollIntervalRef.current) return
      pollIntervalRef.current = setInterval(async () => {
        try {
          const job = await getJob(jobId!)
          if (job.status === 'done') {
            clearInterval(pollIntervalRef.current!)
            pollIntervalRef.current = null
            onEvent({
              event: 'job_done',
              job_id: jobId!,
              units: job.units,
              repo_doc: job.repo_doc,
              total_units: job.units?.length ?? 0,
              done_units: job.units?.length ?? 0,
            })
          } else if (job.status === 'failed') {
            clearInterval(pollIntervalRef.current!)
            pollIntervalRef.current = null
            onEvent({ event: 'job_failed', job_id: jobId!, error: job.error })
          }
        } catch (_) {}
      }, 3000)
    }

    return () => {
      esRef.current?.close()
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [jobId, active])
}

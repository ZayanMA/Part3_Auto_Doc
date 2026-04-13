'use client'
import { useEffect, useCallback } from 'react'
import NavBar from '@/components/layout/NavBar'
import InputPanel from '@/components/input/InputPanel'
import JobProgressBar from '@/components/progress/JobProgressBar'
import StreamingLogPane from '@/components/progress/StreamingLogPane'
import DocsViewer from '@/components/docs/DocsViewer'
import JiraIssueMock from '@/components/jira-mock/JiraIssueMock'
import CIPipelineShowcase from '@/components/ci-showcase/CIPipelineShowcase'
import { useDemoStore } from '@/lib/useDemoStore'
import { useJobPoller } from '@/lib/useJobPoller'
import { JobEvent } from '@/lib/types'

function now() {
  return new Date().toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function DemoPage() {
  const {
    phase, jobId, patchJobId,
    units,
    addLogLine, addPatchLogLine,
    updateJobPhase,
    updateProgress, updatePatchProgress,
    setDone, setPatchDone,
  } = useDemoStore()

  const handleEvent = useCallback((event: JobEvent) => {
    const isPatch = phase === 'patch-running'
    const log = isPatch ? addPatchLogLine : addLogLine
    const updateProg = isPatch ? updatePatchProgress : updateProgress

    switch (event.event) {
      case 'job_phase':
        updateJobPhase(event.phase ?? null, event.phase_message ?? null)
        if (event.phase_message) {
          log({ timestamp: now(), message: event.phase_message, type: 'info' })
        }
        if (event.total_units !== undefined && event.done_units !== undefined) {
          updateProg(event.total_units, event.done_units)
        }
        break
      case 'job_started':
        log({ timestamp: now(), message: `Job started — ${event.total_units} units to process`, type: 'info' })
        updateJobPhase(event.phase ?? 'generating', event.phase_message ?? 'Generating documentation units')
        if (event.total_units !== undefined) updateProg(event.total_units, 0)
        break
      case 'unit_started':
        log({ timestamp: now(), message: `Processing: ${event.name} [${event.kind}]`, type: 'unit' })
        break
      case 'unit_done':
        log({ timestamp: now(), message: `Done: ${event.name} — ${event.status}`, type: 'success' })
        if (event.total_units !== undefined && event.done_units !== undefined)
          updateProg(event.total_units, event.done_units)
        break
      case 'unit_failed':
        log({ timestamp: now(), message: `Failed: ${event.name} — ${event.error}`, type: 'error' })
        if (event.total_units !== undefined && event.done_units !== undefined)
          updateProg(event.total_units, event.done_units)
        break
      case 'job_done':
        log({ timestamp: now(), message: 'Documentation generation complete!', type: 'success' })
        updateJobPhase(event.phase ?? 'done', event.phase_message ?? 'Documentation generation complete')
        if (isPatch) setPatchDone(event.units ?? [])
        else setDone(event.units ?? [], event.repo_doc ?? null)
        break
      case 'job_failed':
        updateJobPhase(event.phase ?? 'failed', event.phase_message ?? 'Job failed')
        log({ timestamp: now(), message: `Job failed: ${event.error}`, type: 'error' })
        break
    }
  }, [phase, addLogLine, addPatchLogLine, updateJobPhase, updateProgress, updatePatchProgress, setDone, setPatchDone])

  const isRunning = phase === 'running'
  const isPatchRunning = phase === 'patch-running'
  const activeJobId = isPatchRunning ? patchJobId : (isRunning ? jobId : null)

  useJobPoller(activeJobId, handleEvent, isRunning || isPatchRunning)

  const isDone = phase === 'done' || phase === 'patch-done' || phase === 'patch-running'

  return (
    <>
      <NavBar />
      <main className="pt-14">
        {/* Hero */}
        <section className="bg-gradient-to-br from-blue-600 to-blue-800 text-white py-20 px-4">
          <div className="max-w-4xl mx-auto text-center">
            <h1 className="text-5xl font-bold mb-4">AutoDoc</h1>
            <p className="text-xl text-blue-100 max-w-2xl mx-auto">
              AI-powered documentation that writes itself. PR merged → docs generated → published to Confluence.
            </p>
            <div className="flex justify-center gap-3 mt-8">
              <a href="#try" className="bg-white text-blue-600 font-semibold px-6 py-3 rounded-lg hover:bg-blue-50 transition-colors">
                Try the Demo
              </a>
              <a href="#architecture" className="border border-white/40 text-white font-semibold px-6 py-3 rounded-lg hover:bg-white/10 transition-colors">
                How It Works
              </a>
            </div>
          </div>
        </section>

        {/* Section 1: Try It */}
        <section id="try" className="py-16 px-4 bg-gray-50">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-10">
              <h2 className="text-3xl font-bold text-gray-900">Generate Documentation</h2>
              <p className="text-gray-500 mt-2">Point AutoDoc at any Git repository or upload a ZIP to see it in action</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
              <div className="space-y-4">
                <InputPanel />
                {(phase === 'running' || phase === 'patch-running') && (
                  <div className="space-y-3">
                    <JobProgressBar />
                    <StreamingLogPane />
                  </div>
                )}
                {(phase === 'done' || phase === 'patch-done') && (
                  <div className="space-y-2">
                    <JobProgressBar />
                    <StreamingLogPane />
                  </div>
                )}
              </div>

              <div className="space-y-4">
                {!isDone && phase !== 'running' && (
                  <div className="bg-white border-2 border-dashed border-gray-200 rounded-xl p-8 text-center text-gray-400">
                    <div className="text-4xl mb-3">📄</div>
                    <p>Documentation will appear here after generation</p>
                  </div>
                )}
              </div>
            </div>

            {isDone && (
              <div className="mt-8">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-gray-700">Generated Documentation</h3>
                </div>
                <DocsViewer />
              </div>
            )}
          </div>
        </section>

        {/* Section 2: Jira Mock */}
        <section id="jira" className="py-16 px-4">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-10">
              <h2 className="text-3xl font-bold text-gray-900">Review in Jira</h2>
              <p className="text-gray-500 mt-2">
                Generated docs appear as a Jira panel for human review before publishing to Confluence
              </p>
            </div>
            <JiraIssueMock />
          </div>
        </section>

        {/* Section 3: CI Pipeline */}
        <section id="ci" className="py-16 px-4 bg-gray-950">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-10">
              <h2 className="text-3xl font-bold text-white">GitHub Actions Pipeline</h2>
              <p className="text-gray-400 mt-2">
                AutoDoc integrates as a reusable workflow — just call it from your CI
              </p>
            </div>
            <CIPipelineShowcase />
          </div>
        </section>

        {/* Section 4: Architecture */}
        <section id="architecture" className="py-16 px-4 bg-white">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-10">
              <h2 className="text-3xl font-bold text-gray-900">How It Works</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                {
                  title: 'Backend Engine',
                  icon: '⚙️',
                  desc: 'Python FastAPI server clones the repo, groups files into logical units via import graph analysis, and calls an LLM (via OpenRouter) to generate documentation per unit.',
                  tags: ['Python', 'FastAPI', 'OpenRouter'],
                },
                {
                  title: 'GitHub Actions',
                  icon: '🔁',
                  desc: 'A reusable workflow triggers on PR merge, calls the backend, polls for completion, HMAC-signs the result, and pushes it to the Forge webhook.',
                  tags: ['GitHub Actions', 'HMAC', 'Webhook'],
                },
                {
                  title: 'Atlassian Forge',
                  icon: '🧩',
                  desc: 'A Forge app receives docs, stores them in KVS as pending, shows a review panel in Jira, and publishes approved docs to Confluence page hierarchy.',
                  tags: ['Forge', 'Jira', 'Confluence'],
                },
              ].map((card) => (
                <div key={card.title} className="border border-gray-200 rounded-xl p-6 hover:shadow-md transition-shadow">
                  <div className="text-3xl mb-3">{card.icon}</div>
                  <h3 className="font-semibold text-gray-900 mb-2">{card.title}</h3>
                  <p className="text-sm text-gray-600 mb-4">{card.desc}</p>
                  <div className="flex flex-wrap gap-1">
                    {card.tags.map((tag) => (
                      <span key={tag} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">{tag}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Flow diagram */}
            <div className="mt-12 bg-gray-50 rounded-xl p-6">
              <h3 className="text-center font-semibold text-gray-700 mb-6">End-to-End Flow</h3>
              <div className="flex flex-wrap items-center justify-center gap-2 text-sm">
                {[
                  'PR Merged',
                  'GitHub Actions',
                  'POST /generate',
                  'LLM generates docs',
                  'Poll /jobs/{id}',
                  'HMAC sign',
                  'POST webhook',
                  'Jira panel',
                  'Reviewer approves',
                  'Published to Confluence',
                ].map((step, i, arr) => (
                  <span key={i} className="flex items-center gap-2">
                    <span className="bg-white border border-gray-200 rounded-lg px-3 py-1.5 font-medium text-gray-700 shadow-sm">
                      {step}
                    </span>
                    {i < arr.length - 1 && <span className="text-gray-400">→</span>}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="bg-gray-900 text-gray-400 py-8 px-4 text-center text-sm">
          <p>AutoDoc — AI-powered documentation generator</p>
        </footer>
      </main>
    </>
  )
}

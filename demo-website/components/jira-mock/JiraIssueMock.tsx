'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useDemoStore } from '@/lib/useDemoStore'
import ConfluenceHierarchy from './ConfluenceHierarchy'
import MarkdownRenderer from '../docs/MarkdownRenderer'
import DiffViewer from '../docs/DiffViewer'

interface PendingDoc {
  slug: string
  title: string
  kind: string
  markdown: string
  prev_markdown?: string
  submittedAt: string
}

interface LiveDoc {
  slug: string
  title: string
  kind: string
  markdown: string
}

export default function JiraIssueMock() {
  const { units, repoName, phase } = useDemoStore()
  const [tab, setTab] = useState<'pending' | 'live'>('pending')
  const [pending, setPending] = useState<PendingDoc[]>([])
  const [live, setLive] = useState<LiveDoc[]>([])
  const [toast, setToast] = useState<string | null>(null)
  const [actioning, setActioning] = useState<string | null>(null)
  const [expandedSlug, setExpandedSlug] = useState<string | null>(null)

  // Sync pending docs from units when they change
  const initialised = pending.length > 0 || live.length > 0
  const hasUnits = units.length > 0

  if (hasUnits && !initialised && (phase === 'done' || phase === 'patch-done')) {
    setPending(units.map((u) => ({
      slug: u.slug,
      title: u.name,
      kind: u.kind,
      markdown: u.markdown,
      prev_markdown: u.prev_markdown,
      submittedAt: new Date().toISOString(),
    })))
  }

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  const handleApprove = (slug: string) => {
    setActioning(slug)
    setTimeout(() => {
      const doc = pending.find((p) => p.slug === slug)
      if (doc) {
        setPending((prev) => prev.filter((p) => p.slug !== slug))
        setLive((prev) => [...prev, doc])
        showToast(`Published "${doc.title}" to Confluence`)
      }
      setActioning(null)
    }, 600)
  }

  const handleReject = (slug: string) => {
    setActioning(slug)
    setTimeout(() => {
      setPending((prev) => prev.filter((p) => p.slug !== slug))
      setActioning(null)
    }, 400)
  }

  if (phase === 'idle' || phase === 'running') {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
        Generate documentation above to see the Jira review panel
      </div>
    )
  }

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      {/* Atlassian header */}
      <div className="bg-[#0052CC] text-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xs bg-blue-400 rounded px-1.5 py-0.5 font-mono">AU-42</span>
          <span className="font-medium text-sm">
            docs: {repoName || 'repository'} — auto-generated documentation
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-blue-200">
          <span className="bg-green-500 text-white px-2 py-0.5 rounded text-xs font-medium">In Review</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 bg-white">
        <button
          onClick={() => setTab('live')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
            tab === 'live' ? 'text-[#0052CC] border-[#0052CC]' : 'text-[#6B778C] border-transparent hover:text-gray-700'
          }`}
        >
          Live Docs · Confluence
        </button>
        <button
          onClick={() => setTab('pending')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
            tab === 'pending' ? 'text-[#0052CC] border-[#0052CC]' : 'text-[#6B778C] border-transparent hover:text-gray-700'
          }`}
        >
          Pending Review {pending.length > 0 ? `(${pending.length})` : ''}
        </button>
      </div>

      {/* Content */}
      <div className="p-4 bg-white relative" style={{ minHeight: 200 }}>
        {/* Toast */}
        <AnimatePresence>
          {toast && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="absolute top-3 right-3 bg-green-500 text-white text-xs px-3 py-2 rounded shadow-lg z-10"
            >
              {toast}
            </motion.div>
          )}
        </AnimatePresence>

        {tab === 'live' && (
          <div>
            {live.length === 0 ? (
              <p className="text-[#6B778C] italic text-sm">No documentation published yet.</p>
            ) : (
              <div className="space-y-3 mb-6">
                {live.map((doc) => (
                  <div key={doc.slug} className="block px-3 py-2 bg-[#F4F5F7] rounded text-[#0052CC] text-sm hover:bg-[#EBECF0]">
                    <span className="font-medium">{doc.title}</span>
                    <span className="ml-2 text-xs bg-[#EBECF0] text-[#172B4D] px-1.5 py-0.5 rounded uppercase font-semibold">
                      {doc.kind}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {live.length > 0 && (
              <div className="mt-4 border-t border-gray-200 pt-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-1">Confluence Page Hierarchy</h4>
                <p className="text-xs text-[#6B778C] mb-3">Approved docs are published to this Confluence page hierarchy</p>
                <ConfluenceHierarchy repoName={repoName} pages={live} />
              </div>
            )}
          </div>
        )}

        {tab === 'pending' && (
          <div>
            {pending.length === 0 ? (
              <p className="text-[#6B778C] italic text-sm">No pending documentation to review.</p>
            ) : (
              <div className="space-y-3">
                {pending.map((doc) => {
                  const isActioning = actioning === doc.slug
                  const isExpanded = expandedSlug === doc.slug
                  return (
                    <div key={doc.slug} className="border border-[#DFE1E6] rounded p-3 bg-[#FAFBFC]">
                      <div className="flex items-center gap-2 mb-1.5">
                        <strong className="text-sm text-[#172B4D]">{doc.title}</strong>
                        <span className="text-xs font-semibold px-1.5 py-0.5 bg-[#EBECF0] text-[#172B4D] rounded uppercase">
                          {doc.kind}
                        </span>
                        {doc.prev_markdown && (
                          <span className="text-xs font-semibold px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded uppercase">
                            patch
                          </span>
                        )}
                        <button
                          onClick={() => setExpandedSlug(isExpanded ? null : doc.slug)}
                          className="ml-auto text-xs text-[#0052CC] hover:underline flex items-center gap-1"
                        >
                          Preview {isExpanded ? '▲' : '▼'}
                        </button>
                      </div>
                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="max-h-64 overflow-y-auto border border-[#DFE1E6] rounded bg-white p-3 mb-2 text-xs">
                              {doc.prev_markdown ? (
                                <DiffViewer markdown={doc.markdown} prevMarkdown={doc.prev_markdown} defaultTab="diff" />
                              ) : (
                                <MarkdownRenderer content={doc.markdown} />
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                      {!isExpanded && (
                        <p className="text-xs text-[#6B778C] font-mono mb-2 line-clamp-3">
                          {doc.prev_markdown
                            ? `Patch: ${doc.markdown.split('\n').filter(Boolean).length} lines updated`
                            : `${doc.markdown.slice(0, 200)}${doc.markdown.length > 200 ? '…' : ''}`}
                        </p>
                      )}
                      <p className="text-xs text-[#97A0AF] mb-2">
                        Submitted: {new Date(doc.submittedAt).toLocaleString()}
                      </p>
                      <div className="flex gap-2">
                        <button
                          disabled={isActioning}
                          onClick={() => handleApprove(doc.slug)}
                          className="px-3 py-1 bg-[#36B37E] text-white text-xs font-medium rounded disabled:opacity-60 hover:bg-green-600"
                        >
                          {isActioning ? 'Working…' : 'Approve'}
                        </button>
                        <button
                          disabled={isActioning}
                          onClick={() => handleReject(doc.slug)}
                          className="px-3 py-1 bg-[#FF5630] text-white text-xs font-medium rounded disabled:opacity-60 hover:bg-red-600"
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

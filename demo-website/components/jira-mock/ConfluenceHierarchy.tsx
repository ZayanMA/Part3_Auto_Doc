'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import MarkdownRenderer from '../docs/MarkdownRenderer'

interface ConfluencePage {
  slug: string
  title: string
  kind: string
  markdown: string
}

interface Props {
  repoName: string
  pages: ConfluencePage[]
}

const KIND_ORDER = ['api', 'models', 'config', 'cli', 'tests', 'modules']

function groupByKind(pages: ConfluencePage[]) {
  const groups: Record<string, ConfluencePage[]> = {}
  for (const p of pages) {
    const k = p.kind in groups ? p.kind : p.kind
    if (!groups[k]) groups[k] = []
    groups[k].push(p)
  }
  return groups
}

export default function ConfluenceHierarchy({ repoName, pages }: Props) {
  const [expandedPage, setExpandedPage] = useState<string | null>(null)
  const groups = groupByKind(pages)
  const kindKeys = Array.from(new Set([...KIND_ORDER, ...Object.keys(groups)])).filter((k) => groups[k])

  return (
    <div className="font-mono text-sm">
      {/* Space root */}
      <div className="flex items-center gap-2 text-blue-600 font-medium mb-1">
        <span>📁</span>
        <span>AU Space</span>
      </div>
      {/* AutoDoc parent */}
      <div className="ml-4">
        <div className="flex items-center gap-2 text-gray-700 font-medium mb-1">
          <span>📂</span>
          <span>[AutoDoc] {repoName}</span>
          <span className="text-xs bg-blue-100 text-blue-600 px-1 rounded">AutoDoc</span>
        </div>
        {/* Kind subpages */}
        <div className="ml-4 space-y-1">
          {kindKeys.map((kind) => (
            <div key={kind}>
              <div className="flex items-center gap-2 text-gray-600">
                <span>📄</span>
                <span className="capitalize">{kind}</span>
              </div>
              {/* Unit pages */}
              <div className="ml-4 space-y-0.5">
                {groups[kind].map((page) => (
                  <div key={page.slug}>
                    <button
                      onClick={() => setExpandedPage(expandedPage === page.slug ? null : page.slug)}
                      className="flex items-center gap-2 text-blue-600 hover:underline text-left"
                    >
                      <span>📃</span>
                      <span>{page.title}</span>
                      <span className="text-gray-400 text-xs">{expandedPage === page.slug ? '▲' : '▼'}</span>
                    </button>
                    <AnimatePresence>
                      {expandedPage === page.slug && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="ml-6 mt-2 mb-2 overflow-hidden"
                        >
                          <div className="bg-white border border-gray-200 rounded shadow-sm">
                            {/* Confluence-style header */}
                            <div className="bg-[#F4F5F7] border-b border-gray-200 px-4 py-2 flex items-center justify-between">
                              <div className="text-xs text-[#6B778C] flex items-center gap-1">
                                <span>AU Space</span>
                                <span>›</span>
                                <span>[AutoDoc] {repoName}</span>
                                <span className="capitalize">{kind}</span>
                                <span>›</span>
                                <span className="text-[#172B4D] font-medium">{page.title}</span>
                              </div>
                              <span className="text-xs bg-[#0052CC] text-white px-2 py-0.5 rounded font-semibold">Confluence</span>
                            </div>
                            {/* Page title */}
                            <div className="px-4 pt-3 pb-1">
                              <h2 className="text-lg font-bold text-[#172B4D]">{page.title}</h2>
                            </div>
                            {/* Full markdown content */}
                            <div className="px-4 pb-4 overflow-y-auto max-h-96 text-sm">
                              <MarkdownRenderer content={page.markdown} />
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

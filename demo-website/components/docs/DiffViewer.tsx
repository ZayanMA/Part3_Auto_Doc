'use client'
import { useState } from 'react'
import MarkdownRenderer from './MarkdownRenderer'
import { computeDiff, collapseForDisplay } from '@/lib/diffUtils'
import type { DisplayBlock } from '@/lib/diffUtils'

interface DiffViewerProps {
  markdown: string
  prevMarkdown: string
  defaultTab?: 'after' | 'before' | 'diff'
}

export default function DiffViewer({ markdown, prevMarkdown, defaultTab = 'after' }: DiffViewerProps) {
  const [tab, setTab] = useState<'after' | 'before' | 'diff'>(defaultTab)

  const diffLines = tab === 'diff' ? computeDiff(prevMarkdown, markdown) : []

  const added = diffLines.filter((l) => l.type === 'added').length
  const removed = diffLines.filter((l) => l.type === 'removed').length
  const hasChanges = added > 0 || removed > 0

  const blocks: DisplayBlock[] = tab === 'diff' ? collapseForDisplay(diffLines) : []

  return (
    <div>
      {/* Tab bar */}
      <div className="flex items-center border-b border-gray-200 mb-4 gap-0">
        {(['after', 'before', 'diff'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 -mb-px transition-colors ${
              tab === t
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'after' ? 'After' : t === 'before' ? 'Before' : 'Diff'}
          </button>
        ))}
        {tab === 'diff' && hasChanges && (
          <span className="ml-3 text-xs font-medium">
            <span className="text-green-700">+{added}</span>
            {' / '}
            <span className="text-red-700">-{removed}</span>
            <span className="text-gray-500"> lines changed</span>
          </span>
        )}
      </div>

      {/* Content */}
      {tab === 'after' && <MarkdownRenderer content={markdown} />}
      {tab === 'before' && <MarkdownRenderer content={prevMarkdown} />}
      {tab === 'diff' && (
        !hasChanges ? (
          <p className="text-sm text-gray-400 py-4 text-center">No changes detected</p>
        ) : (
          <pre className="text-xs font-mono leading-5 overflow-x-auto rounded-lg border border-gray-200 bg-white">
            {blocks.map((block, bi) =>
              block.kind === 'collapse' ? (
                <div
                  key={bi}
                  className="text-center text-gray-400 bg-gray-50 border-y border-gray-100 py-1 select-none cursor-default"
                >
                  ↕ {block.count} unchanged line{block.count !== 1 ? 's' : ''}
                </div>
              ) : (
                block.lines.map((line, li) => (
                  <div
                    key={`${bi}-${li}`}
                    className={
                      line.type === 'added'
                        ? 'bg-green-50 text-green-900'
                        : line.type === 'removed'
                        ? 'bg-red-50 text-red-900'
                        : 'text-gray-700'
                    }
                  >
                    <span className={`select-none pr-2 inline-block w-5 text-center ${
                      line.type === 'added' ? 'text-green-600' : line.type === 'removed' ? 'text-red-600' : 'text-gray-400'
                    }`}>
                      {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
                    </span>
                    {line.text}
                  </div>
                ))
              )
            )}
          </pre>
        )
      )}
    </div>
  )
}

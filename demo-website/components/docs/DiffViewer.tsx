'use client'
import { useState } from 'react'
import MarkdownRenderer from './MarkdownRenderer'

interface DiffViewerProps {
  markdown: string
  prevMarkdown: string
  defaultTab?: 'after' | 'before' | 'diff'
}

type DiffLine = { type: 'added' | 'removed' | 'unchanged'; text: string }

function computeDiff(prev: string, next: string): DiffLine[] {
  const a = prev.split('\n')
  const b = next.split('\n')
  const m = a.length
  const n = b.length
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1])
  const out: DiffLine[] = []
  let i = m, j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      out.push({ type: 'unchanged', text: a[i - 1] })
      i--; j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      out.push({ type: 'added', text: b[j - 1] })
      j--
    } else {
      out.push({ type: 'removed', text: a[i - 1] })
      i--
    }
  }
  return out.reverse()
}

export default function DiffViewer({ markdown, prevMarkdown, defaultTab = 'after' }: DiffViewerProps) {
  const [tab, setTab] = useState<'after' | 'before' | 'diff'>(defaultTab)

  const diffLines = tab === 'diff' ? computeDiff(prevMarkdown, markdown) : []

  const added = diffLines.filter((l) => l.type === 'added').length
  const removed = diffLines.filter((l) => l.type === 'removed').length

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
        {tab === 'diff' && (added > 0 || removed > 0) && (
          <span className="ml-3 text-xs text-gray-500">
            <span className="text-green-700 font-medium">+{added}</span>
            {' / '}
            <span className="text-red-700 font-medium">-{removed}</span>
            {' lines'}
          </span>
        )}
      </div>

      {/* Content */}
      {tab === 'after' && <MarkdownRenderer content={markdown} />}
      {tab === 'before' && <MarkdownRenderer content={prevMarkdown} />}
      {tab === 'diff' && (
        <pre className="text-xs font-mono leading-5 overflow-x-auto rounded-lg border border-gray-200 bg-white">
          {diffLines.map((line, i) => (
            <div
              key={i}
              className={
                line.type === 'added'
                  ? 'bg-green-50 text-green-900'
                  : line.type === 'removed'
                  ? 'bg-red-50 text-red-900'
                  : 'text-gray-600'
              }
            >
              <span className={`select-none pr-2 inline-block w-5 text-center ${
                line.type === 'added' ? 'text-green-600' : line.type === 'removed' ? 'text-red-600' : 'text-gray-400'
              }`}>
                {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
              </span>
              {line.text}
            </div>
          ))}
        </pre>
      )}
    </div>
  )
}

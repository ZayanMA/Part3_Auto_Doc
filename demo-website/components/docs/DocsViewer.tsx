'use client'
import { useDemoStore } from '@/lib/useDemoStore'
import MarkdownRenderer from './MarkdownRenderer'
import DiffViewer from './DiffViewer'

const KIND_COLORS: Record<string, string> = {
  api: 'bg-purple-100 text-purple-700',
  models: 'bg-blue-100 text-blue-700',
  config: 'bg-yellow-100 text-yellow-700',
  cli: 'bg-green-100 text-green-700',
  tests: 'bg-red-100 text-red-700',
  modules: 'bg-gray-100 text-gray-700',
}

const STATUS_COLORS: Record<string, string> = {
  full:   'bg-green-100 text-green-700',
  patch:  'bg-blue-100 text-blue-700',
  cached: 'bg-gray-100 text-gray-600',
  mock:   'bg-amber-100 text-amber-700',
}

const STATUS_LABELS: Record<string, string> = {
  full:   'generated',
  patch:  'updated',
  cached: 'cached',
  mock:   'mock',
}

export default function DocsViewer() {
  const { phase, units, repoDoc, selectedUnitSlug, setSelectedUnit } = useDemoStore()

  if (phase !== 'done' && phase !== 'patch-done' && phase !== 'patch-running') return null

  const allUnits = repoDoc
    ? [{ slug: '__repo__', name: 'Repository Overview', kind: 'overview', markdown: repoDoc, status: 'full' }, ...units]
    : units

  const selected = allUnits.find((u) => u.slug === selectedUnitSlug) ?? allUnits[0]

  return (
    <div className="flex gap-0 border border-gray-200 rounded-xl overflow-hidden h-[calc(100vh-300px)] min-h-[500px]">
      {/* Sidebar */}
      <div className="w-64 shrink-0 bg-gray-50 border-r border-gray-200 overflow-y-auto">
        <div className="p-3 border-b border-gray-200">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            {units.length} unit{units.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="py-1">
          {allUnits.map((u) => (
            <button
              key={u.slug}
              onClick={() => setSelectedUnit(u.slug)}
              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                selectedUnitSlug === u.slug
                  ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-600'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              <div className="font-medium truncate">{u.name}</div>
              <div className="flex gap-1 mt-0.5">
                <span className={`text-xs px-1 rounded ${KIND_COLORS[u.kind] ?? 'bg-gray-100 text-gray-600'}`}>
                  {u.kind}
                </span>
                {u.status && !u.status.startsWith('failed') && (
                  <span className={`text-xs px-1 rounded ${STATUS_COLORS[u.status] ?? 'bg-gray-100 text-gray-600'}`}>
                    {STATUS_LABELS[u.status] ?? u.status}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {selected ? (
          selected.prev_markdown ? (
            <DiffViewer markdown={selected.markdown} prevMarkdown={selected.prev_markdown} />
          ) : (
            <MarkdownRenderer content={selected.markdown} />
          )
        ) : (
          <p className="text-gray-400 text-sm">Select a unit from the sidebar</p>
        )}
      </div>
    </div>
  )
}

'use client'
import { useState } from 'react'
import GitUrlForm from './GitUrlForm'
import ZipUploadForm from './ZipUploadForm'

const TABS = [
  { id: 'git', label: 'Git URL' },
  { id: 'zip', label: 'ZIP Upload' },
]

export default function InputPanel() {
  const [tab, setTab] = useState<'git' | 'zip'>('git')

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <h2 className="text-lg font-semibold mb-4">Generate Documentation</h2>
      <div className="flex border-b border-gray-200 mb-5">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id as 'git' | 'zip')}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.id
                ? 'text-blue-600 border-blue-600'
                : 'text-gray-500 border-transparent hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'git' ? <GitUrlForm /> : <ZipUploadForm />}
    </div>
  )
}

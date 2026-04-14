'use client'
import { useState } from 'react'
import { postDemoGenerate } from '@/lib/api'
import { useDemoStore } from '@/lib/useDemoStore'

export default function GitUrlForm() {
  const [url, setUrl] = useState('')
  const [token, setToken] = useState('')
  const [mode, setMode] = useState<'full' | 'patch'>('full')
  const [base, setBase] = useState('HEAD~1')
  const [head, setHead] = useState('HEAD')
  const [mockGeneration, setMockGeneration] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { startJob } = useDemoStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) { setError('Please enter a Git URL'); return }
    setError('')
    setLoading(true)
    try {
      const repoName = url.split('/').pop()?.replace('.git', '') ?? url
      const res = await postDemoGenerate({
        git_url: url.trim(),
        git_token: token || undefined,
        base: mode === 'patch' ? base : 'HEAD~1',
        head: mode === 'patch' ? head : 'HEAD',
        all_files: mode === 'full',
        mock_generation: mockGeneration,
      })
      startJob(res.job_id, repoName)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Git URL</label>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo"
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="button"
          onClick={() => {
            setUrl('https://github.com/microsoft/markitdown')
            setMode('patch')
            setBase('HEAD~1')
            setHead('HEAD')
          }}
          className="mt-1.5 text-xs text-blue-600 hover:underline"
        >
          Try example: markitdown (patch mode)
        </button>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Private token <span className="text-gray-400">(optional)</span>
        </label>
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="ghp_..."
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="radio" value="full" checked={mode === 'full'} onChange={() => setMode('full')} />
          Full documentation
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="radio" value="patch" checked={mode === 'patch'} onChange={() => setMode('patch')} />
          Patch mode
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input
          type="checkbox"
          checked={mockGeneration}
          onChange={(e) => setMockGeneration(e.target.checked)}
        />
        Mock generation mode (no AI credits)
      </label>
      {mode === 'patch' && (
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Base ref</label>
            <input value={base} onChange={(e) => setBase(e.target.value)}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm" />
          </div>
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Head ref</label>
            <input value={head} onChange={(e) => setHead(e.target.value)}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm" />
          </div>
        </div>
      )}
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <button
        type="submit"
        disabled={loading}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium py-2 px-4 rounded-md text-sm transition-colors"
      >
        {loading ? 'Starting...' : (mockGeneration ? 'Generate Mock Documentation' : 'Generate Documentation')}
      </button>
    </form>
  )
}

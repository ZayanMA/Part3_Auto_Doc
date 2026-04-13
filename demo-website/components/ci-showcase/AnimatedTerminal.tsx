'use client'
import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const SCRIPT_LINES = [
  { text: '$ pip install httpx', type: 'cmd' },
  { text: 'Successfully installed httpx-0.27.0', type: 'out' },
  { text: '$ echo "Detecting Jira issue key from PR body..."', type: 'cmd' },
  { text: 'Detected Jira issue key → AU-42', type: 'success' },
  { text: '$ python3 trigger.py', type: 'cmd' },
  { text: 'POST /generate → {"repo_full_name": "owner/repo", ...}', type: 'out' },
  { text: 'Job triggered: a3f2b1c9-4d5e-6f7a-8b9c-0d1e2f3a4b5c', type: 'success' },
  { text: '[1] status=pending', type: 'out' },
  { text: '[2] status=running', type: 'out' },
  { text: '[3] status=running', type: 'out' },
  { text: '[4] status=running', type: 'out' },
  { text: '[5] status=done', type: 'success' },
  { text: 'Generation complete. 4 units documented.', type: 'success' },
  { text: '$ python3 push_webhook.py', type: 'cmd' },
  { text: 'Signing payload (HMAC-SHA256)...', type: 'out' },
  { text: 'POST webhook → 200 OK', type: 'success' },
  { text: '✓ AutoDoc pipeline complete', type: 'success' },
]

const TYPE_COLORS: Record<string, string> = {
  cmd: 'text-green-400',
  out: 'text-gray-300',
  success: 'text-emerald-400',
}

export default function AnimatedTerminal({ onStepChange }: { onStepChange?: (step: number) => void }) {
  const [visibleLines, setVisibleLines] = useState<typeof SCRIPT_LINES>([])
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)

  const STEP_MAPPING = [0, 0, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]

  const startAnimation = useCallback(() => {
    setVisibleLines([])
    setRunning(true)
    setDone(false)
    onStepChange?.(0)
  }, [onStepChange])

  useEffect(() => {
    if (!running) return
    if (visibleLines.length >= SCRIPT_LINES.length) {
      setRunning(false)
      setDone(true)
      return
    }
    const timer = setTimeout(() => {
      const idx = visibleLines.length
      setVisibleLines((prev) => [...prev, SCRIPT_LINES[idx]])
      onStepChange?.(STEP_MAPPING[idx] ?? 3)
    }, 600)
    return () => clearTimeout(timer)
  }, [running, visibleLines.length, onStepChange])

  useEffect(() => {
    // Auto-start on mount
    setTimeout(startAnimation, 800)
  }, [])

  return (
    <div className="bg-gray-950 rounded-xl overflow-hidden shadow-2xl">
      {/* Terminal header */}
      <div className="bg-gray-800 px-4 py-2 flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-red-500" />
        <div className="w-3 h-3 rounded-full bg-yellow-500" />
        <div className="w-3 h-3 rounded-full bg-green-500" />
        <span className="ml-2 text-gray-400 text-xs">autodoc-ci — bash</span>
      </div>
      {/* Terminal body */}
      <div className="p-4 font-mono text-xs h-80 overflow-y-auto">
        <AnimatePresence initial={false}>
          {visibleLines.map((line, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.15 }}
              className={`leading-5 ${TYPE_COLORS[line.type] ?? 'text-gray-300'}`}
            >
              {line.text}
            </motion.div>
          ))}
        </AnimatePresence>
        {running && (
          <span className="inline-block w-2 h-3.5 bg-green-400 terminal-cursor ml-0.5" />
        )}
      </div>
      {/* Replay button */}
      <div className="px-4 pb-3 flex justify-end">
        <button
          onClick={startAnimation}
          disabled={running}
          className="text-xs text-gray-400 hover:text-white disabled:opacity-40 transition-colors px-2 py-1 border border-gray-700 rounded"
        >
          {running ? 'Running...' : 'Replay'}
        </button>
      </div>
    </div>
  )
}

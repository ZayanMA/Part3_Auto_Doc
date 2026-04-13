'use client'
import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useDemoStore } from '@/lib/useDemoStore'

const TYPE_COLORS: Record<string, string> = {
  info: 'text-gray-400',
  success: 'text-green-400',
  error: 'text-red-400',
  unit: 'text-blue-400',
}

export default function StreamingLogPane() {
  const { logLines, patchLogLines, phase } = useDemoStore()
  const lines = (phase === 'patch-running' || phase === 'patch-done') ? patchLogLines : logLines
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [lines.length])

  if (lines.length === 0) return null

  return (
    <div ref={containerRef} className="bg-gray-950 rounded-lg p-4 font-mono text-xs h-48 overflow-y-auto">
      <AnimatePresence initial={false}>
        {lines.map((line) => (
          <motion.div
            key={line.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className={`flex gap-2 leading-5 ${TYPE_COLORS[line.type] ?? 'text-gray-400'}`}
          >
            <span className="text-gray-600 shrink-0">{line.timestamp}</span>
            <span>{line.message}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

'use client'
import { useEffect, useState } from 'react'

const SECTIONS = [
  { id: 'try', label: 'Try It' },
  { id: 'jira', label: 'Review' },
  { id: 'ci', label: 'CI Pipeline' },
  { id: 'architecture', label: 'How It Works' },
]

export default function NavBar() {
  const [active, setActive] = useState('try')

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setActive(entry.target.id)
        })
      },
      { rootMargin: '-40% 0px -55% 0px' }
    )
    SECTIONS.forEach(({ id }) => {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    })
    return () => observer.disconnect()
  }, [])

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur border-b border-gray-200">
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14">
        <span className="font-bold text-lg tracking-tight">AutoDoc</span>
        <div className="flex items-center gap-1">
          {SECTIONS.map(({ id, label }) => (
            <a
              key={id}
              href={`#${id}`}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                active === id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              {label}
            </a>
          ))}
          <button
            onClick={async () => {
              await fetch('/api/auth/logout', { method: 'POST' })
              window.location.href = '/login'
            }}
            className="ml-2 px-3 py-1.5 rounded text-sm font-medium text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors"
            title="Sign out"
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  )
}

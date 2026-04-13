'use client'
import { useState } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { UnitResult, UnitQuality } from '@/lib/types'

const KIND_COLORS: Record<string, string> = {
  api: '#7C3AED',
  models: '#2563EB',
  config: '#D97706',
  cli: '#059669',
  tests: '#DC2626',
  module: '#6B7280',
}

const REQUIRED_SECTIONS = [
  'Overview',
  'Responsibilities',
  'Key APIs & Interfaces',
  'Configuration & Data',
  'Dependencies',
  'Usage Notes',
]

function scoreColor(score: number): string {
  if (score >= 0.75) return 'text-green-600'
  if (score >= 0.5) return 'text-amber-600'
  return 'text-red-600'
}

function scoreBg(score: number): string {
  if (score >= 0.75) return 'bg-green-100 text-green-800'
  if (score >= 0.5) return 'bg-amber-100 text-amber-800'
  return 'bg-red-100 text-red-800'
}

interface Props {
  units: UnitResult[]
}

export default function QualityDashboard({ units }: Props) {
  const qualityUnits = units.filter((u): u is UnitResult & { quality: UnitQuality } => !!u.quality)
  const [selectedSlug, setSelectedSlug] = useState<string>(qualityUnits[0]?.slug ?? '')

  if (qualityUnits.length === 0) return null

  const selected = qualityUnits.find((u) => u.slug === selectedSlug)?.quality ?? qualityUnits[0].quality

  // A — radar data for selected unit
  const radarData = [
    { axis: 'Sections', value: Math.round(selected.section_completeness * 100) },
    { axis: 'Coverage', value: Math.round(selected.technical_coverage * 100) },
    { axis: 'Safety', value: Math.round((1 - selected.hallucination_risk) * 100) },
    { axis: 'Readability', value: Math.min(100, Math.round(selected.readability_ease)) },
    { axis: 'Density', value: Math.min(100, Math.round((selected.content_density.word_count / 300) * 100)) },
  ]

  // C — bar chart data
  const barData = qualityUnits.map((u) => ({
    name: u.name.length > 16 ? u.name.slice(0, 14) + '…' : u.name,
    score: u.quality.overall_score,
    kind: u.kind,
    fullName: u.name,
  }))

  return (
    <div className="space-y-8">

      {/* A — Summary Table */}
      <div>
        <h3 className="font-semibold text-gray-800 mb-3 text-lg">Quality Summary</h3>
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Unit</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Kind</th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">Overall</th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">Sections</th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">Coverage</th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">Words</th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">Grade</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {qualityUnits.map((u) => {
                const q = u.quality
                const sectionCount = REQUIRED_SECTIONS.length - q.missing_sections.length
                return (
                  <tr key={u.slug} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium text-gray-900">{u.name}</td>
                    <td className="px-4 py-2">
                      <span
                        className="text-xs font-semibold px-2 py-0.5 rounded uppercase"
                        style={{
                          background: KIND_COLORS[u.kind] + '22',
                          color: KIND_COLORS[u.kind] ?? '#6B7280',
                        }}
                      >
                        {u.kind}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      <span className={`font-semibold ${scoreColor(q.overall_score)}`}>
                        {(q.overall_score * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700">
                      {sectionCount}/{REQUIRED_SECTIONS.length}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700">
                      {(q.technical_coverage * 100).toFixed(0)}%
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700">
                      {q.content_density.word_count}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700">
                      {q.readability_grade.toFixed(1)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* B + C — Radar & Bar side-by-side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* B — Radar chart */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-800">Unit Detail</h3>
            <select
              className="text-sm border border-gray-200 rounded px-2 py-1 text-gray-700"
              value={selectedSlug}
              onChange={(e) => setSelectedSlug(e.target.value)}
            >
              {qualityUnits.map((u) => (
                <option key={u.slug} value={u.slug}>{u.name}</option>
              ))}
            </select>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="axis" tick={{ fontSize: 12 }} />
              <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
              <Radar
                name="Score"
                dataKey="value"
                stroke="#2563EB"
                fill="#2563EB"
                fillOpacity={0.25}
              />
            </RadarChart>
          </ResponsiveContainer>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            {radarData.map((d) => (
              <div key={d.axis} className="flex justify-between text-gray-600">
                <span>{d.axis}</span>
                <span className="font-medium">{d.value}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* C — Bar chart */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h3 className="font-semibold text-gray-800 mb-4">Overall Scores by Unit</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={barData} margin={{ top: 5, right: 10, bottom: 40, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 10 }}
                angle={-35}
                textAnchor="end"
                interval={0}
              />
              <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
              <Tooltip
                formatter={(value) => [`${(Number(value) * 100).toFixed(0)}%`, 'Score']}
                labelFormatter={(_, payload) => (payload as any)?.[0]?.payload?.fullName ?? ''}
              />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {barData.map((entry, index) => (
                  <Cell
                    key={index}
                    fill={KIND_COLORS[entry.kind] ?? KIND_COLORS.module}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* D — Missing sections heatmap */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <h3 className="font-semibold text-gray-800 mb-4">Section Coverage Heatmap</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs border-collapse">
            <thead>
              <tr>
                <th className="px-3 py-2 text-left text-gray-600 font-medium min-w-[140px]">Unit</th>
                {REQUIRED_SECTIONS.map((s) => (
                  <th key={s} className="px-2 py-2 text-center text-gray-600 font-medium min-w-[90px] leading-tight">
                    {s.replace(' & ', '\n& ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {qualityUnits.map((u) => {
                const missing = new Set(u.quality.missing_sections)
                return (
                  <tr key={u.slug}>
                    <td className="px-3 py-1.5 text-gray-700 font-medium truncate max-w-[140px]">{u.name}</td>
                    {REQUIRED_SECTIONS.map((s) => (
                      <td key={s} className="px-2 py-1.5 text-center">
                        <div
                          className={`w-5 h-5 mx-auto rounded ${missing.has(s) ? 'bg-red-200' : 'bg-green-200'}`}
                          title={missing.has(s) ? `Missing: ${s}` : `Present: ${s}`}
                        />
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
          <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-200 rounded inline-block" /> Present</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-200 rounded inline-block" /> Missing</span>
        </div>
      </div>

      {/* E — Methodology explanation */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <h3 className="font-semibold text-gray-800 mb-4">How Quality is Measured</h3>
        <p className="text-sm text-gray-500 mb-5">
          Every documentation unit is scored automatically after generation — no LLM involved, all pure static analysis against the source files. Five metrics combine into a weighted overall score (0–100%).
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            {
              label: 'Section Completeness',
              weight: '30%',
              color: 'bg-blue-100 text-blue-800',
              how: 'Checks for the 6 required H2 headings AutoDoc is instructed to produce: Overview, Responsibilities, Key APIs & Interfaces, Configuration & Data, Dependencies, Usage Notes. Score = sections present ÷ 6.',
              shown: 'Summary table "Sections" column (e.g. 5/6), heatmap grid (green = present, red = missing), radar axis "Sections".',
            },
            {
              label: 'Technical Coverage',
              weight: '25%',
              color: 'bg-violet-100 text-violet-800',
              how: 'Extracts all public symbol names from the unit\'s source files using regex (Python: def/class; JS/TS: function, class, const, export). Checks each symbol name appears as a substring in the generated markdown. Private symbols (underscore-prefixed) are excluded. Score = mentioned ÷ total.',
              shown: 'Summary table "Coverage" column, radar axis "Coverage".',
            },
            {
              label: 'Hallucination Safety',
              weight: '25%',
              color: 'bg-green-100 text-green-800',
              how: 'Finds every inline backtick token in the doc (e.g. `myFunction`). Checks whether each token appears verbatim anywhere in the source corpus for that unit. Risk = unverified ÷ total backtick tokens. Safety score = 1 − risk.',
              shown: 'Summary table "Hallucination" column (lower % = safer), radar axis "Safety".',
            },
            {
              label: 'Readability',
              weight: '10%',
              color: 'bg-amber-100 text-amber-800',
              how: 'Strips code blocks and markdown syntax, then runs the Flesch-Kincaid formula on the remaining prose. Reports both grade level (US school grade, lower = simpler) and reading ease (0–100, higher = easier). Docs scoring grade 8–12 with ease 30–70 are considered well-pitched for developer audiences.',
              shown: 'Summary table "Grade" column (Flesch-Kincaid grade level), radar axis "Readability" (mapped from reading ease).',
            },
            {
              label: 'Content Density',
              weight: '10%',
              color: 'bg-rose-100 text-rose-800',
              how: 'Counts prose words (after stripping code blocks and markdown), fenced code block count, and link count. Score targets ~300 prose words (saturates at 1.0) and at least 2 code blocks. Penalises near-empty docs.',
              shown: 'Summary table "Words" column, radar axis "Density".',
            },
            {
              label: 'Overall Score',
              weight: '—',
              color: 'bg-gray-100 text-gray-700',
              how: 'Weighted sum: Section Completeness × 0.30 + Technical Coverage × 0.25 + Hallucination Safety × 0.25 + Content Density × 0.10 + Readability × 0.10.',
              shown: 'Summary table "Overall" column (green ≥ 75%, amber ≥ 50%, red < 50%), bar chart Y-axis, radar centroid.',
            },
          ].map(({ label, weight, color, how, shown }) => (
            <div key={label} className="border border-gray-100 rounded-lg p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-semibold px-2 py-0.5 rounded ${color}`}>{label}</span>
                <span className="text-xs text-gray-400 font-medium">weight {weight}</span>
              </div>
              <p className="text-xs text-gray-600 leading-relaxed"><span className="font-medium text-gray-700">How: </span>{how}</p>
              <p className="text-xs text-gray-500 leading-relaxed"><span className="font-medium text-gray-600">Shown: </span>{shown}</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}

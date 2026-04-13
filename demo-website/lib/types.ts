export interface UnitQuality {
  slug: string
  name: string
  kind: string
  section_completeness: number
  missing_sections: string[]
  content_density: { word_count: number; code_block_count: number; link_count: number }
  technical_coverage: number
  uncovered_symbols: string[]
  readability_grade: number
  readability_ease: number
  hallucination_risk: number
  unverified_tokens: string[]
  overall_score: number
}

export interface UnitResult {
  slug: string
  name: string
  kind: string
  markdown: string
  status: string
  prev_markdown?: string
  quality?: UnitQuality
}

export interface JobRecord {
  job_id: string
  status: 'pending' | 'running' | 'done' | 'failed'
  created_at: string
  finished_at?: string
  units?: UnitResult[]
  repo_doc?: string
  error?: string
}

export interface JobEvent {
  event: string
  job_id: string
  slug?: string
  name?: string
  kind?: string
  status?: string
  total_units?: number
  done_units?: number
  units?: UnitResult[]
  repo_doc?: string
  error?: string
}

export interface LogLine {
  id: string
  timestamp: string
  message: string
  type: 'info' | 'success' | 'error' | 'unit'
}

'use client'
import { create } from 'zustand'
import { UnitResult, LogLine } from './types'

export type DemoPhase = 'idle' | 'running' | 'done' | 'patch-running' | 'patch-done'

interface DemoState {
  phase: DemoPhase
  jobId: string | null
  repoName: string
  logLines: LogLine[]
  units: UnitResult[]
  repoDoc: string | null
  selectedUnitSlug: string | null
  totalUnits: number
  doneUnits: number
  // patch
  patchJobId: string | null
  patchUnits: UnitResult[]
  patchLogLines: LogLine[]
  patchDoneUnits: number
  patchTotalUnits: number

  // actions
  startJob: (jobId: string, repoName: string) => void
  addLogLine: (line: Omit<LogLine, 'id'>) => void
  addPatchLogLine: (line: Omit<LogLine, 'id'>) => void
  updateProgress: (total: number, done: number) => void
  updatePatchProgress: (total: number, done: number) => void
  setDone: (units: UnitResult[], repoDoc: string | null) => void
  setPatchDone: (units: UnitResult[]) => void
  setSelectedUnit: (slug: string | null) => void
  startPatchJob: (jobId: string) => void
  reset: () => void
}

let _idCounter = 0
const nextId = () => String(++_idCounter)

export const useDemoStore = create<DemoState>((set) => ({
  phase: 'idle',
  jobId: null,
  repoName: '',
  logLines: [],
  units: [],
  repoDoc: null,
  selectedUnitSlug: null,
  totalUnits: 0,
  doneUnits: 0,
  patchJobId: null,
  patchUnits: [],
  patchLogLines: [],
  patchDoneUnits: 0,
  patchTotalUnits: 0,

  startJob: (jobId, repoName) => set({
    phase: 'running',
    jobId,
    repoName,
    logLines: [],
    units: [],
    repoDoc: null,
    selectedUnitSlug: null,
    totalUnits: 0,
    doneUnits: 0,
    patchJobId: null,
    patchUnits: [],
    patchLogLines: [],
  }),

  addLogLine: (line) => set((s) => ({
    logLines: [...s.logLines, { ...line, id: nextId() }],
  })),

  addPatchLogLine: (line) => set((s) => ({
    patchLogLines: [...s.patchLogLines, { ...line, id: nextId() }],
  })),

  updateProgress: (total, done) => set({ totalUnits: total, doneUnits: done }),

  updatePatchProgress: (total, done) => set({ patchTotalUnits: total, patchDoneUnits: done }),

  setDone: (units, repoDoc) => set((s) => ({
    phase: 'done',
    units,
    repoDoc,
    selectedUnitSlug: repoDoc ? '__repo__' : (units.length > 0 ? units[0].slug : null),
  })),

  setPatchDone: (units) => set({ phase: 'patch-done', patchUnits: units }),

  setSelectedUnit: (slug) => set({ selectedUnitSlug: slug }),

  startPatchJob: (jobId) => set({ phase: 'patch-running', patchJobId: jobId, patchLogLines: [], patchUnits: [], patchDoneUnits: 0, patchTotalUnits: 0 }),

  reset: () => set({
    phase: 'idle',
    jobId: null,
    repoName: '',
    logLines: [],
    units: [],
    repoDoc: null,
    selectedUnitSlug: null,
    totalUnits: 0,
    doneUnits: 0,
    patchJobId: null,
    patchUnits: [],
    patchLogLines: [],
  }),
}))

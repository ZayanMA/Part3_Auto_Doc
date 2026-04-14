export type DiffLine = { type: 'added' | 'removed' | 'unchanged'; text: string }

export type DisplayBlock =
  | { kind: 'lines'; lines: DiffLine[] }
  | { kind: 'collapse'; count: number }

export function computeDiff(prev: string, next: string): DiffLine[] {
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

export function collapseForDisplay(diffLines: DiffLine[], ctx = 3): DisplayBlock[] {
  const interesting = new Set<number>()
  diffLines.forEach((l, i) => {
    if (l.type !== 'unchanged') {
      for (let k = Math.max(0, i - ctx); k <= Math.min(diffLines.length - 1, i + ctx); k++)
        interesting.add(k)
    }
  })
  const blocks: DisplayBlock[] = []
  let i = 0
  while (i < diffLines.length) {
    if (interesting.has(i)) {
      const chunk: DiffLine[] = []
      while (i < diffLines.length && interesting.has(i)) chunk.push(diffLines[i++])
      blocks.push({ kind: 'lines', lines: chunk })
    } else {
      let count = 0
      while (i < diffLines.length && !interesting.has(i)) { count++; i++ }
      blocks.push({ kind: 'collapse', count })
    }
  }
  return blocks
}

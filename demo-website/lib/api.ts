const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080'

export async function postDemoGenerate(params: {
  git_url: string
  base?: string
  head?: string
  all_files?: boolean
  git_token?: string
}) {
  const res = await fetch(`${API_BASE}/demo/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(`Failed to start job: ${res.status} ${await res.text()}`)
  return res.json() as Promise<{ job_id: string; status: string; poll_url: string; stream_url: string }>
}

export async function postDemoGenerateZip(file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/demo/generate-zip`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(`Failed to start zip job: ${res.status} ${await res.text()}`)
  return res.json() as Promise<{ job_id: string; status: string; poll_url: string; stream_url: string }>
}

export async function getJob(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`)
  if (!res.ok) throw new Error(`Failed to get job: ${res.status}`)
  return res.json()
}

export function getStreamUrl(jobId: string) {
  return `${API_BASE}/jobs/${jobId}/stream`
}

export async function postDemoGenerate(params: {
  git_url: string
  base?: string
  head?: string
  all_files?: boolean
  git_token?: string
  mock_generation?: boolean
}) {
  const res = await fetch('/api/demo/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(`Failed to start job: ${res.status} ${await res.text()}`)
  return res.json() as Promise<{ job_id: string; status: string; poll_url: string; stream_url: string }>
}

export async function postDemoGenerateZip(file: File, mockGeneration = false) {
  const form = new FormData()
  form.append('file', file)
  form.append('mock_generation', String(mockGeneration))
  const res = await fetch('/api/demo/generate-zip', {
    method: 'POST',
    cache: 'no-store',
    body: form,
  })
  if (!res.ok) throw new Error(`Failed to start zip job: ${res.status} ${await res.text()}`)
  return res.json() as Promise<{ job_id: string; status: string; poll_url: string; stream_url: string }>
}

export async function getJob(jobId: string) {
  const res = await fetch(`/api/jobs/${jobId}`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to get job: ${res.status}`)
  return res.json()
}

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8080'
const API_KEY = process.env.AUTODOC_API_KEY

export async function POST(request: Request) {
  const formData = await request.formData()

  const headers: Record<string, string> = {}
  if (API_KEY) headers['Authorization'] = `Bearer ${API_KEY}`
  // Do not set Content-Type — fetch sets it automatically with the multipart boundary

  try {
    const res = await fetch(`${BACKEND}/demo/generate-zip`, {
      method: 'POST',
      headers,
      body: formData,
    })
    const data = await res.json()
    return Response.json(data, { status: res.status })
  } catch {
    return Response.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8080'
const API_KEY = process.env.AUTODOC_API_KEY

export async function POST(request: Request) {
  const body = await request.json()

  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (API_KEY) headers['Authorization'] = `Bearer ${API_KEY}`

  try {
    const res = await fetch(`${BACKEND}/demo/generate`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })
    const data = await res.json()
    return Response.json(data, { status: res.status })
  } catch (err) {
    return Response.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}

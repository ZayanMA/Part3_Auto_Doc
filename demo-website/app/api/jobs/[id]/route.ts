const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8080'
const API_KEY = process.env.AUTODOC_API_KEY

export async function GET(
  _request: Request,
  { params }: { params: { id: string } }
) {
  const headers: Record<string, string> = {}
  if (API_KEY) headers['Authorization'] = `Bearer ${API_KEY}`

  try {
    const res = await fetch(`${BACKEND}/jobs/${params.id}`, { headers })
    const data = await res.json()
    return Response.json(data, { status: res.status })
  } catch {
    return Response.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}

export const runtime = 'edge'
export const dynamic = 'force-dynamic'

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8080'
const API_KEY = process.env.AUTODOC_API_KEY

export async function GET(
  _request: Request,
  { params }: { params: { id: string } }
) {
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (API_KEY) headers['Authorization'] = `Bearer ${API_KEY}`

  try {
    const upstream = await fetch(`${BACKEND}/jobs/${params.id}/stream`, { headers })

    if (!upstream.ok || !upstream.body) {
      return new Response('Stream unavailable', { status: 502 })
    }

    return new Response(upstream.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
      },
    })
  } catch {
    return new Response('Stream error', { status: 502 })
  }
}

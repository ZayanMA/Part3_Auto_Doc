import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  const { code } = await request.json()
  const expected = process.env.DEMO_ACCESS_CODE

  if (!expected) {
    // No access code configured — always allow (open mode)
    return NextResponse.json({ ok: true })
  }

  if (code !== expected) {
    return NextResponse.json({ error: 'Invalid access code' }, { status: 401 })
  }

  const res = NextResponse.json({ ok: true })
  res.cookies.set('demo_auth', expected, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 7, // 7 days
    path: '/',
  })
  return res
}

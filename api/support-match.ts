import type { VercelRequest, VercelResponse } from '@vercel/node'

const BACKEND_URL = 'https://startup-support-cn3c.onrender.com'

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: { code: 'METHOD_NOT_ALLOWED', message: 'POST만 허용됩니다.' } })
  }

  try {
    const upstream = await fetch(`${BACKEND_URL}/api/support-match`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body),
    })

    const data = await upstream.json()
    return res.status(upstream.status).json(data)
  } catch (e) {
    console.error('Backend proxy error:', e)
    return res.status(502).json({ error: { code: 'BACKEND_ERROR', message: '백엔드 서버에 연결하지 못했어요.' } })
  }
}

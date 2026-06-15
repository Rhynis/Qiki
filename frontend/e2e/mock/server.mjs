// Mock HTTP server for Next SSR fetches (the products list/detail server
// components read BACKEND_URL). Client-side calls are mocked via page.route in
// the Playwright fixture; both share the resolver in ./api.mjs.
import { createServer } from 'node:http'
import { resolveApi } from './api.mjs'

const PORT = Number(process.env.MOCK_PORT ?? 8099)

function readBody(req) {
  return new Promise((resolve) => {
    let data = ''
    req.on('data', (chunk) => (data += chunk))
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : {})
      } catch {
        resolve({})
      }
    })
  })
}

const server = createServer(async (req, res) => {
  const method = req.method ?? 'GET'
  const url = new URL(req.url ?? '/', `http://localhost:${PORT}`)
  if (method === 'OPTIONS') {
    res.writeHead(204, { 'Access-Control-Allow-Origin': '*' })
    return res.end()
  }
  const body = method === 'GET' || method === 'DELETE' ? {} : await readBody(req)
  const { status, body: payload } = resolveApi({
    method,
    path: url.pathname,
    query: url.searchParams,
    body,
    cookie: req.headers.cookie,
  })
  res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
  res.end(payload === undefined ? '' : JSON.stringify(payload))
})

server.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`[mock-api] listening on http://localhost:${PORT}`)
})

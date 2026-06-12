import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { config as middlewareConfig } from '@/middleware'

describe('same-origin API proxy', () => {
  it('rewrites same-origin API requests to the backend origin', async () => {
    const nextConfig = readFileSync(join(process.cwd(), 'next.config.mjs'), 'utf8')

    expect(nextConfig).toContain("source: '/api/:path*'")
    expect(nextConfig).toContain('destination: `${backendUrl}/api/:path*`')
  })

  it('does not run auth middleware for proxied API requests', () => {
    expect(middlewareConfig.matcher[0]).toContain('(?!api|')
  })
})

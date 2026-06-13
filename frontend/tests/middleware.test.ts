import { NextRequest } from 'next/server'
import { describe, expect, it } from 'vitest'
import { middleware } from '@/middleware'

function token(payload: Record<string, unknown>) {
  return `header.${Buffer.from(JSON.stringify(payload)).toString('base64url')}.signature`
}

function request(pathname: string, cookies: Record<string, string> = {}) {
  const req = new NextRequest(new URL(`http://localhost${pathname}`))
  for (const [name, value] of Object.entries(cookies)) {
    req.cookies.set(name, value)
  }
  return req
}

function futureExp() {
  return Math.floor(Date.now() / 1000) + 3600
}

function pastExp() {
  return Math.floor(Date.now() / 1000) - 3600
}

describe('auth middleware session persistence', () => {
  it.each(['/cart', '/checkout'])('allows guests to visit %s', (pathname) => {
    const response = middleware(request(pathname))

    expect(response.headers.get('location')).toBeNull()
  })

  it('allows protected routes with expired access and valid refresh cookies', () => {
    const response = middleware(
      request('/account', {
        gasbot_access_token: token({ exp: pastExp(), role: 'customer' }),
        gasbot_refresh_token: token({ exp: futureExp(), type: 'refresh' }),
      })
    )

    expect(response.headers.get('location')).toBeNull()
  })

  it('redirects protected routes when both cookies are invalid', () => {
    const response = middleware(
      request('/account', {
        gasbot_access_token: token({ exp: pastExp(), role: 'customer' }),
        gasbot_refresh_token: token({ exp: pastExp(), type: 'refresh' }),
      })
    )

    expect(response.headers.get('location')).toBe('http://localhost/login?redirectTo=%2Faccount')
  })

  it('lets the client admin guard handle role checks when only refresh is valid', () => {
    const response = middleware(
      request('/admin', {
        gasbot_access_token: token({ exp: pastExp(), role: 'customer' }),
        gasbot_refresh_token: token({ exp: futureExp(), type: 'refresh' }),
      })
    )

    expect(response.headers.get('location')).toBeNull()
  })

  it('redirects non-admin users when a valid access token proves the role', () => {
    const response = middleware(
      request('/admin', {
        gasbot_access_token: token({ exp: futureExp(), role: 'customer' }),
      })
    )

    expect(response.headers.get('location')).toBe('http://localhost/')
  })
})

import { type NextRequest, NextResponse } from 'next/server'

interface TokenPayload {
  role?: string
  exp?: number
}

function parsePayload(token: string | undefined): TokenPayload | null {
  if (!token) {
    return null
  }
  try {
    const payload = token.split('.')[1]
    if (!payload) {
      return null
    }
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(normalized)) as TokenPayload
  } catch {
    return null
  }
}

function isTokenPayloadValid(payload: TokenPayload | null): boolean {
  return typeof payload?.exp === 'number' && payload.exp * 1000 > Date.now()
}

/** Next.js middleware for authentication and route protection. */
export function middleware(request: NextRequest) {
  const response = NextResponse.next()
  const pathname = request.nextUrl.pathname
  const accessToken = request.cookies.get('gasbot_access_token')?.value
  const refreshToken = request.cookies.get('gasbot_refresh_token')?.value
  const accessPayload = parsePayload(accessToken)
  const refreshPayload = parsePayload(refreshToken)
  const hasValidAccessToken = isTokenPayloadValid(accessPayload)
  const hasValidRefreshToken = isTokenPayloadValid(refreshPayload)
  const isAuthenticated = hasValidAccessToken || hasValidRefreshToken

  const publicRoutes = [
    '/',
    '/products',
    '/cart',
    '/checkout',
    '/track',
    '/cam-nang',
    '/login',
    '/register',
    '/forgot-password',
    '/reset-password',
  ]
  const isPublic = publicRoutes.some(
    (route) => pathname === route || pathname.startsWith(route + '/')
  )

  if (pathname.startsWith('/admin')) {
    if (!isAuthenticated) {
      const url = request.nextUrl.clone()
      url.pathname = '/login'
      url.searchParams.set('redirectTo', pathname)
      return NextResponse.redirect(url)
    }
    if (hasValidAccessToken && accessPayload?.role !== 'admin') {
      const url = request.nextUrl.clone()
      url.pathname = '/'
      return NextResponse.redirect(url)
    }
  }

  if (!isPublic && !isAuthenticated) {
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    url.searchParams.set('redirectTo', pathname)
    return NextResponse.redirect(url)
  }

  return response
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}

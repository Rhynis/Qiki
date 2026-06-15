import { type BrowserContext, type Page, expect } from '@playwright/test'

/**
 * Mint an unsigned JWT whose base64 payload carries the role + a far-future exp.
 * The app middleware only base64-decodes the payload (no signature check) and the
 * mock API decodes the same cookie, so this is enough to drive logged-in journeys.
 */
export function mintToken(role: 'customer' | 'admin'): string {
  const payload = {
    sub: role === 'admin' ? 'admin-1' : 'user-1',
    role,
    email: role === 'admin' ? 'admin@example.com' : 'customer@example.com',
    exp: Math.floor(Date.now() / 1000) + 60 * 60,
  }
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url')
  return `header.${body}.signature`
}

/** Seed the auth cookie so middleware + the mock /auth/me treat the session as logged in. */
export async function loginAs(context: BrowserContext, role: 'customer' | 'admin'): Promise<void> {
  await context.addCookies([
    {
      name: 'gasbot_access_token',
      value: mintToken(role),
      domain: 'localhost',
      path: '/',
      httpOnly: false,
      sameSite: 'Lax',
    },
  ])
}

/**
 * Assert the page has no horizontal overflow: the document is not wider than the
 * viewport (allowing 1px for sub-pixel rounding). The core mobile-layout guard.
 */
export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement
    return { scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth }
  })
  expect(
    overflow.scrollWidth,
    `horizontal overflow: scrollWidth ${overflow.scrollWidth} > clientWidth ${overflow.clientWidth}`
  ).toBeLessThanOrEqual(overflow.clientWidth + 1)
}

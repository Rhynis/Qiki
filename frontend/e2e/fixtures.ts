import { test as base, expect } from '@playwright/test'
import { resolveApi } from './mock/api.mjs'

/**
 * Base test that intercepts every client-side `/api/v1/*` call with the shared
 * deterministic resolver. This bypasses the Next `/api/*` rewrite proxy (which
 * 500s on POST bodies) so journeys never depend on a live backend.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route('**/api/v1/**', async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      let body: unknown = {}
      if (request.method() !== 'GET') {
        try {
          body = request.postDataJSON() ?? {}
        } catch {
          body = {}
        }
      }
      // Read the auth cookie from the context jar (reliable on all browsers;
      // WebKit does not always expose it on the intercepted request headers).
      const cookies = await page.context().cookies()
      const cookie = cookies.map((c) => `${c.name}=${c.value}`).join('; ')
      const { status, body: payload } = resolveApi({
        method: request.method(),
        path: url.pathname,
        query: url.searchParams,
        body,
        cookie,
      })
      await route.fulfill({
        status,
        contentType: 'application/json',
        body: payload === undefined ? '' : JSON.stringify(payload),
      })
    })
    await use(page)
  },
})

export { expect }

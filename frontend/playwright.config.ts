import { defineConfig, devices } from '@playwright/test'

// Isolated ports so the E2E run never clashes with a `next dev` server.
const WEB_PORT = 3100
const MOCK_PORT = 8099
const BASE_URL = `http://localhost:${WEB_PORT}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['list']] : 'list',
  timeout: 60_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    {
      // Real iPhone UA + viewport + touch.
      name: 'Mobile Safari',
      use: { ...devices['iPhone 14'] },
      // Admin tables are intentionally horizontally scrollable — desktop only.
      testIgnore: /admin\.spec\.ts/,
    },
    {
      // Real Pixel UA + viewport + touch.
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 7'] },
      testIgnore: /admin\.spec\.ts/,
    },
  ],

  // Start the mock API first, then the Next app pointed at it via BACKEND_URL
  // (covers both SSR fetches and the `/api/*` rewrite). Requires `npm run build`.
  webServer: [
    {
      command: 'node e2e/mock/server.mjs',
      port: MOCK_PORT,
      reuseExistingServer: false,
      env: { MOCK_PORT: String(MOCK_PORT) },
    },
    {
      // Inline BACKEND_URL so both the SSR fetch and the /api rewrite hit the mock.
      command: `BACKEND_URL=http://localhost:${MOCK_PORT} npm run start -- -p ${WEB_PORT}`,
      url: BASE_URL,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { BACKEND_URL: `http://localhost:${MOCK_PORT}` },
    },
  ],
})

import { defineConfig, devices } from '@playwright/test'

/**
 * Browser verification for the explicit demo mode. Uses the locally installed
 * Google Chrome channel so no browser binary download is required, and starts
 * the Vite dev server with `VITE_DATA_MODE=demo` on a dedicated port. API-mode
 * coverage lives in `playwright.api.config.ts`.
 */

// Overridable because Windows can reserve a dynamic port range (Hyper-V/WSL),
// in which case binding the default port fails with `EACCES`.
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 4173)
const WEB_ORIGIN = `http://127.0.0.1:${WEB_PORT}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [['list']],
  use: {
    baseURL: WEB_ORIGIN,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chrome',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    },
  ],
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
    url: WEB_ORIGIN,
    reuseExistingServer: true,
    timeout: 120_000,
    env: { VITE_DATA_MODE: 'demo' },
  },
})

import { defineConfig, devices } from '@playwright/test'

/**
 * API-mode browser verification.
 *
 * Starts the FastAPI backend against a disposable `*_e2e` PostgreSQL database
 * (recreated and seeded by `backend/scripts/e2e_prepare.py`) and the Vite dev
 * server configured with `VITE_DATA_MODE=api`. Demo mode is never used.
 */

// Overridable because Windows can reserve a dynamic port range (Hyper-V/WSL),
// in which case binding the default port fails with `EACCES`.
const API_PORT = Number(process.env.E2E_API_PORT ?? 8010)
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 4174)
const API_ORIGIN = `http://127.0.0.1:${API_PORT}`

const E2E_PASSWORD =
  process.env.E2E_ACCOUNT_PASSWORD ?? 'E2eTicketflow!123'

const DATABASE_URL =
  process.env.E2E_DATABASE_URL ??
  'postgresql+psycopg://ticketflow:ticketflow_local_dev_only@127.0.0.1:5432/ticketflow_e2e'

export default defineConfig({
  testDir: './e2e-api',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chrome',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    },
  ],
  webServer: [
    {
      command: 'node scripts/e2e-api-server.mjs',
      url: `${API_ORIGIN}/api/v1/health/live`,
      reuseExistingServer: false,
      timeout: 240_000,
      env: {
        DATABASE_URL,
        APP_ENV: 'development',
        JWT_SECRET: 'e2e-only-jwt-secret-not-for-production-0000',
        CORS_ORIGINS: `http://127.0.0.1:${WEB_PORT}`,
        E2E_ACCOUNT_PASSWORD: E2E_PASSWORD,
        E2E_API_PORT: String(API_PORT),
        E2E_PYTHON: process.env.E2E_PYTHON ?? '',
      },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        VITE_DATA_MODE: 'api',
        VITE_API_BASE_URL: `${API_ORIGIN}/api/v1`,
      },
    },
  ],
})

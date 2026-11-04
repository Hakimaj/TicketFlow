/**
 * Data-source configuration.
 *
 * The application talks to the real TicketFlow API by default. The in-memory
 * demonstration dataset is only used when `VITE_DATA_MODE=demo` is set
 * explicitly, and the shell then shows a visible demo indicator so fixture
 * data is never presented as backend data by accident.
 */

export type DataMode = 'api' | 'demo'

/** Default backend origin used by `npm run dev` (FastAPI on port 8000). */
export const DEV_API_BASE_URL = 'http://127.0.0.1:8000/api/v1'

/**
 * Resolves the data mode from a raw environment value.
 *
 * Anything other than an explicit `demo` (case-insensitive, trimmed) selects
 * API mode: an unset variable must never silently fall back to fixtures.
 */
export function resolveDataMode(value: string | undefined): DataMode {
  return value?.trim().toLowerCase() === 'demo' ? 'demo' : 'api'
}

/**
 * Resolves the API origin. Relative `VITE_API_BASE_URL` values are allowed so a
 * production build can be served next to the API on the same origin.
 */
export function resolveApiBaseUrl(
  value: string | undefined,
  isProduction: boolean,
): string {
  const trimmed = value?.trim()
  if (trimmed) return trimmed.replace(/\/+$/, '')
  return isProduction ? '/api/v1' : DEV_API_BASE_URL
}

export const DATA_MODE: DataMode = resolveDataMode(import.meta.env.VITE_DATA_MODE)

export const API_BASE_URL: string = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
  Boolean(import.meta.env.PROD),
)

export const isDemoMode = DATA_MODE === 'demo'

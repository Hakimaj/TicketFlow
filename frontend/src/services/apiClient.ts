/**
 * Placeholder HTTP client for a future backend (Phase 2+).
 *
 * Phase 1 runs entirely on the demonstration dataset, so nothing imports
 * this module yet. It exists to document where real data access will attach
 * and to keep the environment configuration (`VITE_API_BASE_URL`) honest:
 * no fake endpoints, no pretend connectivity.
 */

/** Base URL for the future API, configured via non-secret env vars only. */
export const API_BASE_URL: string | undefined = import.meta.env.VITE_API_BASE_URL

export const isBackendConfigured = (): boolean => Boolean(API_BASE_URL)

/**
 * Reserved for Phase 2. A thin wrapper around fetch with JSON handling and
 * typed errors will live here once a real API exists.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error(
      'TicketFlow API is not configured yet. Phase 1 uses the demo dataset.',
    )
  }
  const response = await fetch(`${API_BASE_URL}${path}`, init)
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`)
  }
  return (await response.json()) as T
}

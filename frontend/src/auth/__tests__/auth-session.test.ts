import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Session behaviour tests. No token is ever written to storage: these tests
 * assert the access token only lives in the api-client module and that a 401
 * triggers exactly one shared refresh attempt before the request is retried.
 */

const BASE = 'http://api.test/api/v1'
const PROFILE = {
  id: 'acc-1',
  email: 'reviewer@ticketflow.test',
  display_name: 'Abebe Kebede',
  role: 'reviewer',
  agent_id: 'AG-01',
  agent_name: 'Abebe Kebede',
  permissions: ['tickets:read', 'replies:review'],
}

type ApiClient = typeof import('@/services/apiClient')
type AuthService = typeof import('@/services/authService')

let api: ApiClient
let auth: AuthService
let calls: Array<{ url: string; method: string; credentials?: RequestCredentials }>
let handler: (url: string, init: RequestInit) => Response

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeAll(async () => {
  vi.stubEnv('VITE_API_BASE_URL', BASE)
  vi.resetModules()
  api = await import('@/services/apiClient')
  auth = await import('@/services/authService')
})

beforeEach(() => {
  calls = []
  api.setRefreshHandler(null)
  api.setUnauthorizedHandler(null)
  api.setAccessToken(null)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input)
      calls.push({
        url,
        method: init.method ?? 'GET',
        credentials: init.credentials,
      })
      return handler(url, init)
    }),
  )
})

describe('sign-in and sign-out', () => {
  it('keeps the access token in memory and sends the login payload', async () => {
    handler = () =>
      json({
        access_token: 'access-1',
        token_type: 'bearer',
        expires_in: 900,
        user: PROFILE,
      })

    const user = await auth.signInWithPassword(
      'reviewer@ticketflow.test',
      'TicketflowTest!123',
    )

    expect(user).toMatchObject({ role: 'reviewer', agent_id: 'AG-01' })
    expect(api.getAccessToken()).toBe('access-1')
    expect(calls[0].url).toBe(`${BASE}/auth/login`)
    expect(calls[0].method).toBe('POST')
    expect(calls[0].credentials).toBe('include')

    // Nothing is persisted to web storage when a browser provides it.
    const scope = globalThis as {
      localStorage?: Storage
      sessionStorage?: Storage
    }
    expect(scope.localStorage?.length ?? 0).toBe(0)
    expect(scope.sessionStorage?.length ?? 0).toBe(0)
  })

  it('restores the session from the refresh cookie', async () => {
    handler = () =>
      json({
        access_token: 'access-2',
        token_type: 'bearer',
        expires_in: 900,
        user: PROFILE,
      })

    const user = await auth.restoreSession()

    expect(calls[0].url).toBe(`${BASE}/auth/refresh`)
    expect(calls[0].method).toBe('POST')
    expect(calls[0].credentials).toBe('include')
    expect(user.email).toBe('reviewer@ticketflow.test')
    expect(api.getAccessToken()).toBe('access-2')
  })

  it('clears the local token even if logout fails', async () => {
    api.setAccessToken('access-1')
    handler = () => json({ error: { code: 'internal_error', message: 'down' } }, 500)

    await expect(auth.endSession()).rejects.toBeTruthy()
    expect(api.getAccessToken()).toBeNull()
    expect(calls[0].url).toBe(`${BASE}/auth/logout`)
  })
})

describe('401 handling', () => {
  it('refreshes once and retries the original request with the new token', async () => {
    api.setAccessToken('expired-token')
    api.setRefreshHandler(async () => {
      await auth.restoreSession()
    })

    handler = (url, init) => {
      if (url.endsWith('/auth/refresh')) {
        return json({
          access_token: 'fresh-token',
          token_type: 'bearer',
          expires_in: 900,
          user: PROFILE,
        })
      }
      const headers = new Headers(init.headers)
      return headers.get('Authorization') === 'Bearer fresh-token'
        ? json({ items: [], pagination: { page: 1, page_size: 20, total: 0, page_count: 1 } })
        : json({ error: { code: 'not_authenticated', message: 'expired' } }, 401)
    }

    const result = await api.request<{ items: unknown[] }>('/tickets')

    expect(result.items).toEqual([])
    expect(calls.map((call) => new URL(call.url).pathname)).toEqual([
      '/api/v1/tickets',
      '/api/v1/auth/refresh',
      '/api/v1/tickets',
    ])
  })

  it('notifies the auth layer and clears the token when refresh fails', async () => {
    api.setAccessToken('expired-token')
    const onUnauthorized = vi.fn()
    api.setUnauthorizedHandler(onUnauthorized)
    api.setRefreshHandler(async () => {
      await auth.restoreSession()
    })

    handler = (url) =>
      url.endsWith('/auth/refresh')
        ? json({ error: { code: 'refresh_invalid', message: 'expired' } }, 401)
        : json({ error: { code: 'not_authenticated', message: 'expired' } }, 401)

    await expect(api.request('/tickets')).rejects.toMatchObject({
      status: 401,
    })

    expect(onUnauthorized).toHaveBeenCalledTimes(1)
    expect(api.getAccessToken()).toBeNull()
    // No retry loop: exactly one original request and one refresh attempt.
    expect(calls).toHaveLength(2)
  })
})

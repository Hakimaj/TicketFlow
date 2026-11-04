import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import type * as AccountModule from '../accountService'

/**
 * Contract tests for the administrator account service.
 *
 * `fetch` is stubbed so the exact paths, query parameters and snake_case bodies
 * are asserted; the response mapping must never invent or leak credentials.
 */

const BASE = 'http://api.test/api/v1'

let accountApi: typeof AccountModule
let calls: Array<{ url: string; method: string; body: unknown }>
let handler: (url: string, init: RequestInit) => Response

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function account(overrides: Record<string, unknown> = {}) {
  return {
    id: '8b6f2f7e-0000-4000-8000-000000000001',
    email: 'provisioned@ticketflow.test',
    display_name: 'Provisioned Agent',
    role: 'agent',
    is_active: true,
    must_change_password: true,
    agent_id: 'AG-05',
    agent_name: 'Yonas Abate',
    created_at: '2026-10-27T09:00:00.000Z',
    updated_at: '2026-10-27T09:00:00.000Z',
    ...overrides,
  }
}

beforeAll(async () => {
  vi.stubEnv('VITE_API_BASE_URL', BASE)
  vi.resetModules()
  accountApi = await import('../accountService')
})

beforeEach(() => {
  calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input)
      calls.push({
        url,
        method: init.method ?? 'GET',
        body: init.body ? JSON.parse(String(init.body)) : undefined,
      })
      return handler(url, init)
    }),
  )
})

describe('account administration contract', () => {
  it('lists accounts with server-side filters and maps the response', async () => {
    handler = () =>
      json({
        items: [account()],
        pagination: { page: 1, page_size: 50, total: 1, page_count: 1 },
      })

    const result = await accountApi.listAccounts({
      search: 'provisioned',
      role: 'agent',
      isActive: true,
      page: 1,
      pageSize: 50,
    })

    const url = new URL(calls[0].url)
    expect(url.origin + url.pathname).toBe(`${BASE}/accounts`)
    expect(url.searchParams.get('search')).toBe('provisioned')
    expect(url.searchParams.get('role')).toBe('agent')
    expect(url.searchParams.get('is_active')).toBe('true')
    expect(url.searchParams.get('page_size')).toBe('50')

    expect(result.pagination.total).toBe(1)
    expect(result.items[0]).toMatchObject({
      display_name: 'Provisioned Agent',
      must_change_password: true,
      agent_name: 'Yonas Abate',
    })
  })

  it('omits empty filters instead of sending nulls', async () => {
    handler = () =>
      json({
        items: [],
        pagination: { page: 1, page_size: 50, total: 0, page_count: 0 },
      })

    await accountApi.listAccounts({ search: '   ', role: null, isActive: null })

    const url = new URL(calls[0].url)
    expect(url.search).toBe('')
  })

  it('creates an account with the documented snake_case body', async () => {
    handler = () => json(account(), 201)

    const created = await accountApi.createAccount({
      email: 'provisioned@ticketflow.test',
      displayName: 'Provisioned Agent',
      role: 'agent',
      password: 'Provisioned!Passw0rd-2026',
      agentId: 'AG-05',
      isActive: true,
    })

    expect(calls[0].method).toBe('POST')
    expect(new URL(calls[0].url).pathname).toBe('/api/v1/accounts')
    expect(calls[0].body).toEqual({
      email: 'provisioned@ticketflow.test',
      display_name: 'Provisioned Agent',
      role: 'agent',
      password: 'Provisioned!Passw0rd-2026',
      agent_id: 'AG-05',
      is_active: true,
    })
    // The response projection carries no password or session material.
    expect(Object.keys(created)).not.toContain('password')
    expect(created.must_change_password).toBe(true)
  })

  it('sends only the provided update fields, including an explicit unlink', async () => {
    handler = () => json(account({ agent_id: null, agent_name: null }))

    const updated = await accountApi.updateAccount(account().id, {
      agent_id: null,
    })

    expect(calls[0].method).toBe('PATCH')
    expect(new URL(calls[0].url).pathname).toBe(
      `/api/v1/accounts/${account().id}`,
    )
    expect(calls[0].body).toEqual({
      display_name: undefined,
      role: undefined,
      agent_id: null,
      is_active: undefined,
    })
    expect(updated.agent_id).toBeNull()
    expect(updated.agent_name).toBeNull()
  })

  it('maps a duplicate account rejection to a safe message', async () => {
    handler = () =>
      json(
        {
          error: {
            code: 'account_exists',
            message: 'An account with provisioned@ticketflow.test already exists.',
          },
        },
        409,
      )

    await expect(
      accountApi.createAccount({
        email: 'provisioned@ticketflow.test',
        displayName: 'Provisioned Agent',
        role: 'agent',
        password: 'Provisioned!Passw0rd-2026',
      }),
    ).rejects.toMatchObject({
      status: 409,
      code: 'account_exists',
      message: 'An account with that email already exists.',
    })
  })
})

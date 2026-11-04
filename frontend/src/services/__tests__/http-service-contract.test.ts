import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import type { HttpTicketService as HttpTicketServiceType } from '../httpTicketService'
import type { ApiClientError } from '../apiClient'

/**
 * Contract tests for the HTTP service. `fetch` is stubbed and every request is
 * recorded so the exact backend paths, query parameters and bodies are
 * asserted — the defects this suite targets were URL/body mismatches that
 * typechecking cannot catch.
 */

const BASE = 'http://api.test/api/v1'

let service: HttpTicketServiceType
let calls: Array<{ url: string; method: string; body: unknown; headers: Headers }>
let handler: (url: string, init: RequestInit) => Response

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function ticketSummary(overrides: Record<string, unknown> = {}) {
  return {
    id: 'TF-1046',
    subject: 'Invoice question',
    requester_name: 'Dawit Alemu',
    channel: 'email',
    category: 'billing',
    priority: 'high',
    status: 'open',
    assigned_team: 'billing_team',
    assigned_agent_id: 'AG-02',
    assigned_agent_name: 'Hana Tesfaye',
    version: 3,
    created_at: '2026-10-20T08:00:00Z',
    updated_at: '2026-10-21T08:00:00Z',
    ...overrides,
  }
}

function ticketDetail(overrides: Record<string, unknown> = {}) {
  return {
    ...ticketSummary(),
    description: 'The VAT line is wrong.',
    requester: { id: 'REQ-1', name: 'Dawit Alemu', email: 'dawit@example.test' },
    due_at: null,
    suggested_category: null,
    suggested_priority: null,
    review_note: null,
    ...overrides,
  }
}

function replySummary(overrides: Record<string, unknown> = {}) {
  return {
    id: 'REP-1',
    ticket_id: 'TF-1046',
    author: { id: 'AG-03', name: 'Dawit Mengistu' },
    body: 'Dear customer,',
    state: 'draft',
    version: 1,
    submitted_at: null,
    reviewed_at: null,
    reviewer_id: null,
    reviewer_name: null,
    reviewer_feedback: null,
    sent_at: null,
    sent_by_actor_name: null,
    created_at: '2026-10-20T08:00:00Z',
    updated_at: '2026-10-20T08:00:00Z',
    ...overrides,
  }
}

beforeAll(async () => {
  vi.stubEnv('VITE_API_BASE_URL', BASE)
  vi.resetModules()
  const module = await import('../httpTicketService')
  service = new module.HttpTicketService()
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
        headers: new Headers(init.headers),
      })
      return handler(url, init)
    }),
  )
})

describe('ticket queries and triage mutations', () => {
  it('maps a filtered, sorted ticket page', async () => {
    handler = () =>
      json({
        items: [ticketSummary()],
        pagination: { page: 2, page_size: 25, total: 42, page_count: 2 },
      })

    const page = await service.listTickets({
      page: 2,
      pageSize: 25,
      statuses: ['open', 'pending'],
      priorities: ['high'],
      search: 'invoice',
      sortBy: 'priority',
      sortDir: 'asc',
    })

    expect(calls).toHaveLength(1)
    const url = new URL(calls[0].url)
    expect(url.origin + url.pathname).toBe(`${BASE}/tickets`)
    expect(url.searchParams.getAll('status')).toEqual(['open', 'pending'])
    expect(url.searchParams.get('priority')).toBe('high')
    expect(url.searchParams.get('search')).toBe('invoice')
    expect(url.searchParams.get('page')).toBe('2')
    expect(url.searchParams.get('page_size')).toBe('25')
    expect(url.searchParams.get('sort_by')).toBe('priority')
    expect(url.searchParams.get('sort_dir')).toBe('asc')

    expect(page.total).toBe(42)
    expect(page.pageCount).toBe(2)
    expect(page.items[0]).toMatchObject({
      id: 'TF-1046',
      requesterName: 'Dawit Alemu',
      assignedAgentId: 'AG-02',
      category: 'billing',
      priority: 'high',
    })
  })

  it('uses the dedicated status, priority, category and assignment paths', async () => {
    handler = () => json(ticketDetail())

    const options = { expectedVersion: 3 }
    await service.updateStatus('TF-1046', 'open', undefined, options)
    await service.updatePriority('TF-1046', 'low', undefined, options)
    await service.updateCategory('TF-1046', 'general', undefined, options)
    await service.assignTicket('TF-1046', 'AG-03', undefined, options)

    expect(calls.map((call) => [call.method, new URL(call.url).pathname])).toEqual([
      ['PATCH', '/api/v1/tickets/TF-1046/status'],
      ['PATCH', '/api/v1/tickets/TF-1046/priority'],
      ['PATCH', '/api/v1/tickets/TF-1046/category'],
      ['PATCH', '/api/v1/tickets/TF-1046/assignment'],
    ])
    expect(calls.map((call) => call.body)).toEqual([
      { status: 'open', expected_version: 3 },
      { priority: 'low', expected_version: 3 },
      { category: 'general', expected_version: 3 },
      { agent_id: 'AG-03', expected_version: 3 },
    ])
  })

  it('refuses a triage mutation without the version it read', async () => {
    handler = () => json(ticketDetail())

    await expect(service.updateStatus('TF-1046', 'open')).rejects.toMatchObject({
      code: 'missing_ticket_version',
    })
    await expect(
      service.assignTicket('TF-1046', null, undefined, { expectedVersion: 0 }),
    ).rejects.toMatchObject({ code: 'missing_ticket_version' })
    // No request may reach the API without a precondition.
    expect(calls).toHaveLength(0)
  })

  it('surfaces a stale version as a conflict without retrying', async () => {
    handler = () =>
      json(
        {
          error: {
            code: 'ticket_version_conflict',
            message: 'Ticket TF-1046 changed since you loaded it.',
            details: [
              {
                field: 'expected_version',
                message: 'Expected version 3 but the ticket is already at version 4.',
                expected_version: 3,
                current_version: 4,
              },
            ],
          },
        },
        409,
      )

    await expect(
      service.updateStatus('TF-1046', 'pending', undefined, { expectedVersion: 3 }),
    ).rejects.toMatchObject({
      status: 409,
      code: 'ticket_version_conflict',
    })
    // Exactly one attempt: a stale mutation is never replayed automatically.
    expect(calls).toHaveLength(1)
  })

  it('derives a timeline item from the notes endpoint', async () => {
    handler = () =>
      json({
        id: 'note-1',
        ticket_id: 'TF-1046',
        content: 'Escalated to billing.',
        author: { id: 'AG-03', name: 'Dawit Mengistu' },
        created_at: '2026-10-21T09:00:00Z',
        updated_at: '2026-10-21T09:00:00Z',
      })

    const activity = await service.addInternalNote('TF-1046', 'Escalated to billing.')

    expect(calls[0].url).toBe(`${BASE}/tickets/TF-1046/notes`)
    expect(calls[0].method).toBe('POST')
    expect(calls[0].body).toEqual({ content: 'Escalated to billing.' })
    expect(activity).toMatchObject({
      ticketId: 'TF-1046',
      action: 'note_added',
      actorName: 'Dawit Mengistu',
      isInternalNote: true,
    })
  })

  it('reads ticket activity as a plain array and joins note bodies', async () => {
    handler = (url) => {
      if (url.includes('/notes')) {
        return json({
          items: [
            {
              id: 'note-1',
              ticket_id: 'TF-1046',
              content: 'Escalated to billing.',
              author: { id: 'AG-03', name: 'Dawit Mengistu' },
              created_at: '2026-10-21T09:00:00Z',
              updated_at: '2026-10-21T09:00:00Z',
            },
          ],
          pagination: { page: 1, page_size: 100, total: 1, page_count: 1 },
        })
      }
      return json([
        {
          id: 'ACT-3',
          ticket_id: 'TF-1046',
          reply_id: null,
          reply_version: null,
          note_id: 'note-1',
          actor_id: 'AG-03',
          actor_name: 'Dawit Mengistu',
          actor_type: 'agent',
          action: 'note_added',
          summary: 'Internal note added to the ticket.',
          is_internal_note: true,
          created_at: '2026-10-21T09:00:00Z',
        },
        {
          id: 'ACT-2',
          ticket_id: 'TF-1046',
          reply_id: null,
          reply_version: null,
          note_id: null,
          actor_id: 'AG-03',
          actor_name: 'Dawit Mengistu',
          actor_type: 'agent',
          action: 'status_changed',
          summary: 'Status changed to Open.',
          is_internal_note: false,
          created_at: '2026-10-21T10:00:00Z',
        },
      ])
    }

    const activities = await service.getTicketActivities('TF-1046')

    expect(calls.map((call) => new URL(call.url).pathname)).toEqual([
      '/api/v1/tickets/TF-1046/activities',
      '/api/v1/tickets/TF-1046/notes',
    ])
    expect(activities.map((item) => item.id)).toEqual(['ACT-3', 'ACT-2'])
    // The note body is joined from the staff-only notes resource.
    expect(activities[0].detail).toBe('Escalated to billing.')
    expect(activities[1].actorName).toBe('Dawit Mengistu')
  })

  it('fills every status count for the dashboard summary', async () => {
    handler = (url) => {
      if (url.includes('/dashboard/summary')) {
        return json({
          generated_at: '2026-10-21T12:00:00Z',
          total_tickets: 10,
          active_tickets: 7,
          unassigned_tickets: 2,
          urgent_high_tickets: 3,
          needs_review_tickets: 1,
          pending_reply_approvals: 2,
          status_counts: [
            { status: 'open', count: 4 },
            { status: 'pending', count: 3 },
          ],
          category_counts: [],
          priority_counts: [],
          received_trend: [],
          priority_summary: null,
          agent_workload: null,
        })
      }
      return json({ items: [], pagination: { page: 1, page_size: 100, total: 0, page_count: 1 } })
    }

    const stats = await service.getDashboardStats(7)

    expect(stats.statusCounts.open).toBe(4)
    expect(stats.statusCounts.pending).toBe(3)
    expect(stats.statusCounts.closed).toBe(0)
    expect(stats.statusCounts.new).toBe(0)
    expect(stats.pendingApprovals).toBe(2)
    expect(stats.needsReviewTickets).toBe(1)
  })
})

describe('cross-resource API responses', () => {
  it('reads pending replies from the reply+ticket pair response', async () => {
    handler = () =>
      json({
        items: [
          {
            reply: replySummary({ state: 'pending_approval' }),
            ticket: {
              id: 'TF-1046',
              subject: 'Invoice question',
              category: 'billing',
              priority: 'high',
              status: 'open',
              requester_name: 'Dawit Alemu',
              created_at: '2026-10-20T08:00:00Z',
            },
          },
        ],
        pagination: { page: 1, page_size: 100, total: 1, page_count: 1 },
      })

    const pending = await service.listPendingReplies()

    expect(new URL(calls[0].url).pathname).toBe('/api/v1/replies')
    expect(pending).toHaveLength(1)
    expect(pending[0]).toMatchObject({
      id: 'REP-1',
      ticketId: 'TF-1046',
      state: 'pending_approval',
    })
  })

  it('sends action/date filters to the audit API and enforces them locally', async () => {
    const now = Date.now()
    handler = () =>
      json({
        items: [
          {
            id: 'ACT-NEW',
            ticket_id: 'TF-1046',
            reply_id: 'REP-1',
            reply_version: 1,
            note_id: null,
            actor_id: 'AG-01',
            actor_name: 'Abebe Kebede',
            actor_type: 'agent',
            action: 'reply_approved',
            summary: 'Customer reply approved for demo sending.',
            is_internal_note: false,
            created_at: new Date(now - 86_400_000).toISOString(),
          },
          {
            id: 'ACT-OLD',
            ticket_id: 'TF-1046',
            reply_id: null,
            reply_version: null,
            note_id: null,
            actor_id: 'AG-03',
            actor_name: 'Dawit Mengistu',
            actor_type: 'agent',
            action: 'note_added',
            summary: 'Internal note added to the ticket.',
            is_internal_note: true,
            created_at: new Date(now - 30 * 86_400_000).toISOString(),
          },
        ],
        pagination: { page: 1, page_size: 100, total: 2, page_count: 1 },
      })

    const page = await service.listActivityLog({
      actions: ['reply_approved'],
      range: 7,
      page: 1,
      pageSize: 20,
    })

    const url = new URL(calls[0].url)
    expect(url.searchParams.getAll('action')).toEqual(['reply_approved'])
    expect(url.searchParams.get('start')).toBeTruthy()
    expect(page.items.map((entry) => entry.id)).toEqual(['ACT-NEW'])
  })
})

describe('reply workflow', () => {
  it('approves the exact version returned by the server', async () => {
    handler = (url, init) => {
      if (url.endsWith('/replies/REP-1') && (init.method ?? 'GET') === 'GET') {
        return json({ ...replySummary(), version: 3 })
      }
      return json(replySummary({ state: 'approved', version: 3, reviewed_at: '2026-10-21T12:00:00Z' }))
    }

    const approved = await service.approveReply('REP-1')

    expect(calls.map((call) => [call.method, new URL(call.url).pathname])).toEqual([
      ['GET', '/api/v1/replies/REP-1'],
      ['POST', '/api/v1/replies/REP-1/approve'],
    ])
    expect(calls[1].body).toEqual({ version: 3 })
    expect(approved.state).toBe('approved')
  })

  it('falls back to the active draft when creation reports an existing reply', async () => {
    handler = (_url, init) => {
      const method = init.method ?? 'GET'
      if (method === 'POST') {
        return json(
          { error: { code: 'reply_already_exists', message: 'exists' } },
          409,
        )
      }
      if (method === 'GET') {
        return json({
          items: [
            replySummary({ state: 'sent', id: 'REP-OLD' }),
            replySummary({ id: 'REP-2' }),
          ],
          pagination: { page: 1, page_size: 100, total: 2, page_count: 1 },
        })
      }
      return json(replySummary({ id: 'REP-2', body: 'Updated text.' }))
    }

    const saved = await service.saveReplyDraft('TF-1046', 'Updated text.')

    expect(calls.map((call) => [call.method, new URL(call.url).pathname])).toEqual([
      ['POST', '/api/v1/tickets/TF-1046/replies'],
      ['GET', '/api/v1/tickets/TF-1046/replies'],
      ['PATCH', '/api/v1/replies/REP-2'],
    ])
    expect(calls[2].body).toEqual({ body: 'Updated text.' })
    expect(saved.id).toBe('REP-2')
  })

  it('uses the send-demo endpoint and returns the persisted reply', async () => {
    handler = () =>
      json({
        reply: replySummary({
          state: 'sent',
          sent_at: '2026-10-21T12:30:00Z',
          sent_by_actor_name: 'Abebe Kebede',
        }),
        delivery: 'demo_marked_sent',
        notice: 'No customer message was delivered.',
      })

    const sent = await service.markReplySent('REP-1')

    expect(new URL(calls[0].url).pathname).toBe('/api/v1/replies/REP-1/send-demo')
    expect(sent.state).toBe('sent')
    expect(sent.sentByActorName).toBe('Abebe Kebede')
  })

  it('maps server errors into ApiClientError with a useful message', async () => {
    handler = () =>
      json(
        { error: { code: 'forbidden', message: 'Nope.' } },
        403,
      )

    await expect(service.approveReply('REP-1')).rejects.toMatchObject({
      code: 'forbidden',
      status: 403,
      message: 'You do not have permission to perform this action.',
    } satisfies Partial<ApiClientError>)
  })
})

describe('staff intake', () => {
  const intake = {
    subject: 'Refund for order ET-99120 has not arrived',
    description: 'The return was collected two weeks ago and no refund arrived.',
    category: 'billing' as const,
    priority: 'high' as const,
    channel: 'email' as const,
    requesterName: 'Marta Alemu',
    requesterEmail: 'Marta.Alemu@Example.com',
  }

  it('posts the intake payload to the tickets collection', async () => {
    handler = () =>
      json(ticketDetail({ id: 'TF-1052', status: 'new', version: 1 }), 201)

    const created = await service.createTicket(intake)

    expect(calls).toHaveLength(1)
    expect(calls[0].method).toBe('POST')
    expect(new URL(calls[0].url).pathname).toBe('/api/v1/tickets')
    // No actor, status or version field: the server owns those.
    expect(calls[0].body).toEqual({
      subject: intake.subject,
      description: intake.description,
      category: 'billing',
      priority: 'high',
      channel: 'email',
      requester_name: 'Marta Alemu',
      requester_email: 'Marta.Alemu@Example.com',
    })
    expect(created).toMatchObject({
      id: 'TF-1052',
      status: 'new',
      version: 1,
      requesterEmail: 'dawit@example.test',
    })
  })

  it('notifies sibling views only after the API confirms creation', async () => {
    let notified = 0
    const unsubscribe = service.subscribe(() => {
      notified += 1
    })

    handler = () => json(ticketDetail({ id: 'TF-1053', version: 1 }), 201)
    await service.createTicket(intake)
    expect(notified).toBe(1)

    handler = () =>
      json(
        {
          error: {
            code: 'validation_error',
            message: 'Request validation failed.',
            details: [{ field: 'subject', message: 'String should have at least 3 characters' }],
          },
        },
        422,
      )
    await expect(service.createTicket(intake)).rejects.toMatchObject({
      status: 422,
      code: 'validation_error',
    })
    expect(notified).toBe(1)

    unsubscribe()
  })

  it('reports an unavailable API instead of returning fixture data', async () => {
    handler = () => {
      throw new TypeError('Failed to fetch')
    }

    await expect(service.createTicket(intake)).rejects.toBeInstanceOf(Error)
  })
})
